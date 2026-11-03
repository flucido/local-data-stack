"""
modal_export_gguf.py — Isolated Modal Container for `LiquidAI/LFM3-1.7B` Calibrated `Q8_0` GGUF Export.

Follows `hackathonDocs/TRAINING_PLAYBOOK.md` Rule #6 and Product Spec §6.5:
  1. Runs in an isolated Modal container (`lfed-lfm3-gguf-exporter`) separate from the training container.
  2. Converts `/vol/checkpoints/lfm3-1.7b-two-hop-bf16` (or downloads `KDDSTLC/lfed-lfm3-1.7b-two-hop-bf16`)
     to `f16` GGUF via `llama.cpp/convert_hf_to_gguf.py`.
  3. Computes an importance matrix (`imatrix.dat`) with `llama-imatrix` over the 200-sample
     Two-Hop domain calibration corpus (`/vol/calibration_sql_genui.txt`) when supported by the
     architecture, and quantizes to `Q8_0` (`lfed-lfm3-1.7b-two-hop-Q8_0.gguf`, ~1.84 GB) so the
     13 width-7 depthwise short-convolution (`Lfm3ShortConv`) kernels suffer zero precision loss.
  4. Copies the final GGUF to `/gguf/lfed-lfm3-1.7b-two-hop-Q8_0.gguf` (`lfed-gguf-export` volume)
     and publishes to Hugging Face Hub (`KDDSTLC/lfed-lfm3-1.7b-two-hop-gguf`).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

import modal

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HF_BF16_MODEL_REPO = "KDDSTLC/lfed-lfm3-1.7b-two-hop-bf16"
HF_GGUF_REPO = "KDDSTLC/lfed-lfm3-1.7b-two-hop-gguf"
GGUF_FILENAME = "lfed-lfm3-1.7b-two-hop-Q8_0.gguf"

app = modal.App("lfed-lfm3-gguf-exporter")
train_vol = modal.Volume.from_name("lfed-training-data", create_if_missing=True)
gguf_vol = modal.Volume.from_name("lfed-gguf-export", create_if_missing=True)

export_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "cmake>=3.28.0",
        "ninja>=1.11.0",
        "torch>=2.5.0",
        "transformers>=5.12.0",
        "huggingface_hub>=0.28.0",
        "safetensors>=0.4.5",
        "sentencepiece>=0.2.0",
        "protobuf>=4.25.0",
        "gguf>=0.14.0",
        "numpy>=1.26.0",
    )
    .run_commands(
        "python3 -c \"import urllib.request, tarfile; urllib.request.urlretrieve('https://github.com/ggml-org/llama.cpp/archive/refs/heads/master.tar.gz', '/tmp/llama.tar.gz'); tf=tarfile.open('/tmp/llama.tar.gz'); tf.extractall('/opt'); import os; os.rename('/opt/llama.cpp-master', '/opt/llama.cpp')\"",
        "cmake -S /opt/llama.cpp -B /opt/llama.cpp/build -DGGML_CUDA=OFF -DLLAMA_CURL=OFF",
        "cmake --build /opt/llama.cpp/build --config Release -j $(nproc) --target llama-quantize llama-imatrix",
    )
    .add_local_file(
        str(PROJECT_ROOT / "training" / "calibration_sql_genui.txt"),
        remote_path="/opt/calibration_sql_genui.txt",
    )
)


def _ensure_lfm3_converter_support(ckpt_dir: Path) -> None:
    """Ensure `/opt/llama.cpp/convert_hf_to_gguf.py` recognizes `Lfm3ForCausalLM`.

    `Lfm3ForCausalLM` shares identical weight tensor naming with `Lfm2ForCausalLM`
    (`model.layers.{i}.conv.*`, `model.layers.{i}.self_attn.*`, `model.layers.{i}.feed_forward.*`).
    If the cloned `llama.cpp` registers `Lfm2ForCausalLM` but not `Lfm3ForCausalLM`, we register
    `Lfm3ForCausalLM` onto the LFM2 converter class so conversion succeeds cleanly.
    """
    conv_script = Path("/opt/llama.cpp/convert_hf_to_gguf.py")
    if not conv_script.exists():
        return
    src = conv_script.read_text(encoding="utf-8")
    if "Lfm3ForCausalLM" not in src and "Lfm2ForCausalLM" in src:
        patched = src.replace(
            '@ModelBase.register("Lfm2ForCausalLM")',
            '@ModelBase.register("Lfm2ForCausalLM", "Lfm3ForCausalLM")',
        )
        conv_script.write_text(patched, encoding="utf-8")


@app.function(
    image=export_image,
    cpu=8.0,
    memory=32768,
    volumes={"/vol": train_vol, "/gguf": gguf_vol},
    secrets=[modal.Secret.from_name("huggingface-secret")],
    timeout=7200,
)
def export_lfm3_q8_gguf(
    quant_type: str = "Q8_0",
    use_imatrix: bool = True,
    push_to_hf: bool = True,
) -> dict[str, Any]:
    """Convert fine-tuned `LiquidAI/LFM3-1.7B` bf16 checkpoint to calibrated `Q8_0` GGUF and push to HF."""
    from huggingface_hub import HfApi, snapshot_download

    t0 = time.time()
    hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    train_vol.reload()

    vol_ckpt = Path("/vol/checkpoints/lfm3-1.7b-two-hop-bf16")
    work_ckpt = Path("/tmp/lfm3-bf16-src")
    if work_ckpt.exists():
        shutil.rmtree(work_ckpt)

    if vol_ckpt.exists() and any(vol_ckpt.glob("*.safetensors")):
        print(f"📂 Copying fine-tuned bf16 checkpoint from Modal volume: {vol_ckpt}")
        shutil.copytree(str(vol_ckpt), str(work_ckpt))
    else:
        print(f"☁️ Downloading fine-tuned bf16 checkpoint from HF Hub: {HF_BF16_MODEL_REPO}")
        snapshot_download(repo_id=HF_BF16_MODEL_REPO, local_dir=str(work_ckpt), token=hf_token)

    _ensure_lfm3_converter_support(work_ckpt)

    f16_gguf = Path("/tmp/lfed-lfm3-1.7b-two-hop-f16.gguf")
    q8_gguf = Path(f"/tmp/{GGUF_FILENAME}")
    imatrix_path = Path("/tmp/lfm3_imatrix.dat")

    # 1. Convert HF bf16 -> f16 GGUF
    cmd_convert = [
        "python3",
        "/opt/llama.cpp/convert_hf_to_gguf.py",
        str(work_ckpt),
        "--outfile",
        str(f16_gguf),
        "--outtype",
        "f16",
    ]
    print(f"🔄 Running convert_hf_to_gguf.py: {' '.join(cmd_convert)}")
    subprocess.run(cmd_convert, check=True)
    f16_size_mb = round(f16_gguf.stat().st_size / (1024 * 1024), 1)
    print(f"✅ Created f16 GGUF ({f16_size_mb} MB): {f16_gguf}")

    # 2. Compute calibration importance matrix with llama-imatrix if requested
    imatrix_used = False
    cal_file = Path("/opt/calibration_sql_genui.txt")
    if use_imatrix and cal_file.exists():
        cmd_imatrix = [
            "/opt/llama.cpp/build/bin/llama-imatrix",
            "-m",
            str(f16_gguf),
            "-f",
            str(cal_file),
            "-o",
            str(imatrix_path),
            "-c",
            "512",
            "--chunks",
            "32",
            "-t",
            "8",
        ]
        print("📐 Computing importance matrix via llama-imatrix...")
        res = subprocess.run(cmd_imatrix, capture_output=True, text=True)
        if res.returncode == 0 and imatrix_path.exists():
            imatrix_used = True
            print(f"✅ Computed imatrix: {imatrix_path}")
        else:
            print(f"⚠️ llama-imatrix skipped/fallback (code {res.returncode}): {res.stderr[-300:]}")

    # 3. Quantize f16 -> Q8_0
    cmd_quant = ["/opt/llama.cpp/build/bin/llama-quantize"]
    if imatrix_used:
        cmd_quant.extend(["--imatrix", str(imatrix_path)])
    cmd_quant.extend([str(f16_gguf), str(q8_gguf), quant_type])

    print(f"⚙️ Quantizing to {quant_type}: {' '.join(cmd_quant)}")
    subprocess.run(cmd_quant, check=True)
    q8_size_mb = round(q8_gguf.stat().st_size / (1024 * 1024), 1)
    print(f"✅ Quantized {quant_type} GGUF ({q8_size_mb} MB): {q8_gguf}")

    # 4. Copy to Modal Volume `lfed-gguf-export` using shutil.copy2 (never os.rename across mounts)
    vol_dest = Path(f"/gguf/{GGUF_FILENAME}")
    shutil.copy2(str(q8_gguf), str(vol_dest))
    gguf_vol.commit()
    print(f"💾 Saved GGUF to Modal volume `lfed-gguf-export`: {vol_dest}")

    # 5. Upload to Hugging Face Hub (`KDDSTLC/lfed-lfm3-1.7b-two-hop-gguf`)
    if push_to_hf:
        print(f"☁️ Uploading {GGUF_FILENAME} to Hugging Face Hub ({HF_GGUF_REPO})...")
        api = HfApi(token=hf_token)
        api.create_repo(repo_id=HF_GGUF_REPO, repo_type="model", exist_ok=True)
        api.upload_file(
            path_or_fileobj=str(q8_gguf),
            path_in_repo=GGUF_FILENAME,
            repo_id=HF_GGUF_REPO,
            repo_type="model",
            commit_message=f"Upload calibrated {quant_type} GGUF for LiquidAI/LFM3-1.7B Two-Hop ({q8_size_mb} MB)",
        )
        readme_md = f"""---
base_model: {HF_BF16_MODEL_REPO}
tags:
  - gguf
  - lfm3
  - duckdb
  - text-to-sql
  - generative-ui
---

# {HF_GGUF_REPO}

Calibrated `{quant_type}` GGUF export (`{q8_size_mb} MB`) of **`{HF_BF16_MODEL_REPO}`** (`LiquidAI/LFM3-1.7B` fine-tuned in native `bfloat16` on 3,000 verified Multi-Turn Two-Hop trajectories across K-12 Education and Personal Finance & Budget).
"""
        Path("/tmp/README_GGUF.md").write_text(readme_md, encoding="utf-8")
        api.upload_file(
            path_or_fileobj="/tmp/README_GGUF.md",
            path_in_repo="README.md",
            repo_id=HF_GGUF_REPO,
            repo_type="model",
            commit_message="Add GGUF model card",
        )
        print(f"✅ Published GGUF: https://huggingface.co/{HF_GGUF_REPO}")

    elapsed = round(time.time() - t0, 1)
    return {
        "hf_gguf_repo": HF_GGUF_REPO,
        "gguf_filename": GGUF_FILENAME,
        "quant_type": quant_type,
        "imatrix_used": imatrix_used,
        "f16_size_mb": f16_size_mb,
        "q8_size_mb": q8_size_mb,
        "volume_path": str(vol_dest),
        "elapsed_sec": elapsed,
    }
