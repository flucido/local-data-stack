"""
modal_train_slm.py — Regime A Native bfloat16 Full Fine-Tuning (FFT) + Execution-Guided GRPO
for `LiquidAI/LFM3-1.7B` on Modal `A100-80GB`.

Follows all operational rules from `hackathonDocs/TRAINING_PLAYBOOK.md` and the Product Spec:
  1. Deploy via `modal deploy training/modal_train_slm.py` and trigger via `.spawn()` (never `modal run`).
  2. Native `torch.bfloat16` 100% Full Fine-Tuning (no 4-bit QLoRA quantization noise on LFM3's
     13 width-7 gated short-convolution LIV blocks + 11 GQA attention layers).
  3. Exact turn-level completion-only loss masking:
       - `system`, `user`, `tool`, and Split B erroneous SQL turns (`loss_mask=False`) -> `labels = -100`
       - Valid Hop 1/1b (`execute_duckdb_query`) and Hop 2 (`render_workspace_ui`) turns -> `labels = input_ids`
  4. Stage 2 Execution-Guided GRPO alignment pass using `training/reward_fn.py` against the
     seeded DuckDB warehouse (`G=4` rollouts per prompt, group-normalized policy gradient).
  5. `save_strategy="no"` during Trainer loop; saves final checkpoint to `/tmp`, copies via
     `shutil` to `/vol/checkpoints/lfm3-1.7b-two-hop-bf16`, commits volume, and uploads to
     Hugging Face Hub (`KDDSTLC/lfed-lfm3-1.7b-two-hop-bf16`).
"""

from __future__ import annotations

import json
import os
import random
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import modal

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BASE_MODEL_ID = "LiquidAI/LFM3-1.7B"
HF_DATASET_REPO = "KDDSTLC/lfed-lfm3-two-hop-trajectories"
HF_BF16_MODEL_REPO = "KDDSTLC/lfed-lfm3-1.7b-two-hop-bf16"
MODAL_VOLUME_NAME = "lfed-training-data"

app = modal.App("lfed-lfm3-trainer")
volume = modal.Volume.from_name(MODAL_VOLUME_NAME, create_if_missing=True)

train_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "torch>=2.5.0",
        "transformers>=5.12.0",
        "accelerate>=1.2.0",
        "datasets>=3.2.0",
        "huggingface_hub>=0.28.0",
        "safetensors>=0.4.5",
        "sentencepiece>=0.2.0",
        "protobuf>=4.25.0",
        "triton>=3.1.0",
        "duckdb>=1.1.0",
        "pandas>=2.2.0",
        "numpy>=1.26.0",
    )
    .add_local_dir(
        str(PROJECT_ROOT / "training"),
        remote_path="/root/project/training",
        ignore=["*.jsonl", "__pycache__", "*.pyc"],
    )
    .add_local_dir(
        str(PROJECT_ROOT / "nl_query"),
        remote_path="/root/project/nl_query",
        ignore=["*.jsonl", "__pycache__", "*.pyc", ".coverage"],
    )
)


def tokenize_trajectory_with_loss_mask(
    messages: list[dict[str, Any]],
    tokenizer: Any,
    max_length: int = 3072,
) -> dict[str, list[int]] | None:
    """Tokenize a multi-turn ChatML trajectory with exact completion-only loss masking.

    Only assistant turns with `loss_mask=True` contribute to cross-entropy loss (`labels = input_ids`).
    All `system`, `user`, `tool`, and erroneous Split B assistant turns (`loss_mask=False`) are
    masked with `-100`.
    """
    input_ids: list[int] = []
    labels: list[int] = []

    bos_id = getattr(tokenizer, "bos_token_id", None)
    if bos_id is not None:
        input_ids.append(int(bos_id))
        labels.append(-100)

    has_active_labels = False

    for msg in messages:
        role = msg["role"]
        content = msg["content"].strip()
        train_turn = bool(msg.get("loss_mask", role == "assistant"))

        header_str = f"<|im_start|>{role}\n"
        body_str = f"{content}<|im_end|>\n"

        header_ids = tokenizer.encode(header_str, add_special_tokens=False)
        body_ids = tokenizer.encode(body_str, add_special_tokens=False)

        input_ids.extend(header_ids)
        labels.extend([-100] * len(header_ids))

        input_ids.extend(body_ids)
        if role == "assistant" and train_turn:
            labels.extend(body_ids)
            has_active_labels = True
        else:
            labels.extend([-100] * len(body_ids))

    if not has_active_labels:
        return None

    if len(input_ids) > max_length:
        input_ids = input_ids[:max_length]
        labels = labels[:max_length]
        if all(x == -100 for x in labels):
            return None

    return {
        "input_ids": input_ids,
        "labels": labels,
        "attention_mask": [1] * len(input_ids),
    }


@dataclass
class CompletionOnlyPadCollator:
    """Right-pads `input_ids`, `attention_mask`, and `labels` (padded with `-100`) to batch max length."""

    pad_token_id: int

    def __call__(self, features: list[dict[str, list[int]]]) -> dict[str, Any]:
        import torch

        max_len = max(len(f["input_ids"]) for f in features)
        batch_input_ids = []
        batch_labels = []
        batch_mask = []

        for f in features:
            pad_len = max_len - len(f["input_ids"])
            batch_input_ids.append(f["input_ids"] + [self.pad_token_id] * pad_len)
            batch_labels.append(f["labels"] + [-100] * pad_len)
            batch_mask.append(f["attention_mask"] + [0] * pad_len)

        return {
            "input_ids": torch.tensor(batch_input_ids, dtype=torch.long),
            "labels": torch.tensor(batch_labels, dtype=torch.long),
            "attention_mask": torch.tensor(batch_mask, dtype=torch.long),
        }


def run_execution_guided_grpo_pass(
    model: Any,
    tokenizer: Any,
    trajectories: list[dict[str, Any]],
    num_prompts: int = 96,
    group_size: int = 4,
    lr: float = 5e-6,
    max_new_tokens: int = 220,
) -> dict[str, float]:
    """Run Stage 2 execution-guided GRPO alignment over Hop 1 and Hop 2 prompts using `reward_fn.py`.

    For each prompt:
      1. Sample `G=4` completions from the policy model (`temperature=0.7, top_p=0.95`).
      2. Score each completion with `score_hop1_completion` (real DuckDB execution + gold EX match)
         or `score_hop2_completion` (column binding + semantic chart appropriateness).
      3. Compute group-relative advantages `A_i = (R_i - mean(R)) / (std(R) + 1e-4)`.
      4. Update policy weights when reward variance > 0.
    """
    import torch

    from training.reward_fn import get_reward_conn, score_hop1_completion, score_hop2_completion

    conn = get_reward_conn()
    device = next(model.parameters()).device
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)

    rng = random.Random(42)
    sampled = rng.sample(trajectories, min(num_prompts, len(trajectories)))

    im_end_id = tokenizer.convert_tokens_to_ids("<|im_end|>")
    eos_ids = [
        tid for tid in [im_end_id, tokenizer.eos_token_id] if isinstance(tid, int) and tid >= 0
    ]

    total_reward = 0.0
    total_rollouts = 0
    updated_groups = 0

    for step_idx, item in enumerate(sampled, 1):
        msgs = item["messages"]
        # Alternate between Hop 1 SQL prompts and Hop 2 UI prompts
        use_hop2 = (step_idx % 2 == 0) and len(msgs) >= 5 and msgs[3]["role"] == "tool"
        if use_hop2 and '"status":"ok"' in msgs[3]["content"]:
            prefix_msgs = msgs[:4]
        else:
            prefix_msgs = msgs[:2]
            use_hop2 = False

        prompt_str = ""
        for m in prefix_msgs:
            prompt_str += f"<|im_start|>{m['role']}\n{m['content'].strip()}<|im_end|>\n"
        prompt_str += "<|im_start|>assistant\n"

        prompt_ids = tokenizer.encode(prompt_str, return_tensors="pt").to(device)
        prompt_len = prompt_ids.shape[1]

        # 1. Sample G rollouts
        model.eval()
        with torch.no_grad():
            gen_out = model.generate(
                input_ids=prompt_ids.repeat(group_size, 1),
                attention_mask=torch.ones(
                    (group_size, prompt_len), dtype=torch.long, device=device
                ),
                max_new_tokens=max_new_tokens,
                do_sample=True,
                temperature=0.7,
                top_p=0.95,
                pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id,
                eos_token_id=eos_ids if eos_ids else tokenizer.eos_token_id,
            )

        rewards: list[float] = []
        for g_idx in range(group_size):
            comp_ids = gen_out[g_idx, prompt_len:]
            comp_text = tokenizer.decode(comp_ids, skip_special_tokens=False)
            if "<|im_end|>" in comp_text:
                comp_text = comp_text.split("<|im_end|>")[0]
            if use_hop2:
                r = score_hop2_completion(comp_text, output_columns=item.get("output_columns", []))
            else:
                r = score_hop1_completion(comp_text, gold_sql=item.get("gold_sql"), conn=conn)
            rewards.append(r)
            total_reward += r
            total_rollouts += 1

        r_tensor = torch.tensor(rewards, dtype=torch.float32, device=device)
        r_std = float(r_tensor.std().item())
        if r_std < 1e-4:
            continue

        advantages = (r_tensor - r_tensor.mean()) / (r_std + 1e-4)

        # 2. Policy gradient step on rollout completions weighted by group-relative advantage
        model.train()
        optimizer.zero_grad()
        pad_id = tokenizer.pad_token_id or tokenizer.eos_token_id or 0
        attn_mask = (gen_out != pad_id).long()
        outputs = model(input_ids=gen_out, attention_mask=attn_mask)
        logits = outputs.logits[:, prompt_len - 1 : -1, :]
        target_ids = gen_out[:, prompt_len:]
        target_mask = (target_ids != pad_id).float()

        log_probs = torch.log_softmax(logits.float(), dim=-1)
        token_log_probs = log_probs.gather(dim=-1, index=target_ids.unsqueeze(-1)).squeeze(-1)
        seq_log_probs = (token_log_probs * target_mask).sum(dim=-1) / target_mask.sum(dim=-1).clamp(
            min=1.0
        )

        pg_loss = -(advantages.detach() * seq_log_probs).mean()
        pg_loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        updated_groups += 1

        if step_idx % 16 == 0:
            avg_r = total_reward / max(1, total_rollouts)
            print(
                f"  [GRPO {step_idx}/{len(sampled)}] avg_reward={avg_r:.3f} "
                f"updated_groups={updated_groups} last_rewards={[round(x, 2) for x in rewards]}"
            )

    return {
        "grpo_avg_reward": round(total_reward / max(1, total_rollouts), 4),
        "grpo_updated_groups": updated_groups,
        "grpo_total_rollouts": total_rollouts,
    }


@app.function(
    image=train_image,
    gpu="A100-80GB",
    volumes={"/vol": volume},
    secrets=[modal.Secret.from_name("huggingface-secret")],
    timeout=14400,
)
def train_lfm3_two_hop(
    num_epochs: float = 3.0,
    learning_rate: float = 2e-5,
    max_seq_length: int = 3072,
    grpo_prompts: int = 96,
    push_to_hf: bool = True,
) -> dict[str, Any]:
    """Run Regime A native bfloat16 Full Fine-Tuning + Execution-Guided GRPO on `LiquidAI/LFM3-1.7B`."""
    import torch
    from datasets import Dataset
    from huggingface_hub import HfApi, snapshot_download
    from transformers import AutoModelForCausalLM, AutoTokenizer, Trainer, TrainingArguments

    if "/root/project" not in sys.path:
        sys.path.insert(0, "/root/project")
    if "/root/project/nl_query" not in sys.path:
        sys.path.insert(0, "/root/project/nl_query")

    t0 = time.time()
    hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")

    print(f"🚀 Loading {BASE_MODEL_ID} in native bfloat16 (Regime A: 100% Full Fine-Tuning)...")
    base_snapshot_dir = snapshot_download(repo_id=BASE_MODEL_ID, token=hf_token)

    tokenizer = AutoTokenizer.from_pretrained(
        base_snapshot_dir,
        trust_remote_code=True,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        base_snapshot_dir,
        dtype=torch.bfloat16,
        trust_remote_code=True,
        device_map="cuda:0",
    )
    model.config.use_cache = False
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})

    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(
        f"✅ Model loaded on {torch.cuda.get_device_name(0)}: {trainable_params:,}/{total_params:,} trainable params (100% FFT)"
    )

    # 1. Load 3,000 verified multi-turn Two-Hop trajectories
    volume.reload()
    dataset_path = Path("/vol/lfm3_two_hop_3k.jsonl")
    if not dataset_path.exists():
        raise FileNotFoundError(f"Expected training dataset at {dataset_path}")

    raw_rows: list[dict[str, Any]] = []
    with dataset_path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                raw_rows.append(json.loads(line))

    print(f"📚 Tokenizing {len(raw_rows)} trajectories with completion-only loss masking...")
    tokenized_samples: list[dict[str, list[int]]] = []
    for row in raw_rows:
        tok = tokenize_trajectory_with_loss_mask(
            row["messages"], tokenizer=tokenizer, max_length=max_seq_length
        )
        if tok is not None:
            tokenized_samples.append(tok)

    # Split 95% train / 5% eval
    split_idx = int(len(tokenized_samples) * 0.95)
    train_ds = Dataset.from_list(tokenized_samples[:split_idx])
    eval_ds = Dataset.from_list(tokenized_samples[split_idx:])
    print(f"📊 Tokenized dataset: {len(train_ds)} train / {len(eval_ds)} eval sequences")

    # 2. Stage 1: Native bfloat16 SFT (3 epochs, NEFTune=5.0, save_strategy="no")
    tmp_out_dir = "/tmp/lfm3_sft_work"
    total_steps = max(1, int((len(train_ds) / 32.0) * num_epochs))
    warmup_steps = max(5, int(total_steps * 0.05))
    training_args = TrainingArguments(
        output_dir=tmp_out_dir,
        num_train_epochs=num_epochs,
        per_device_train_batch_size=4,
        per_device_eval_batch_size=4,
        gradient_accumulation_steps=8,  # Effective batch size = 32
        learning_rate=learning_rate,
        lr_scheduler_type="cosine",
        warmup_steps=warmup_steps,
        weight_decay=0.05,
        bf16=True,
        optim="adamw_torch_fused",
        neftune_noise_alpha=5.0,
        logging_steps=15,
        eval_strategy="steps",
        eval_steps=75,
        save_strategy="no",  # Rule #3 from TRAINING_PLAYBOOK.md
        report_to="none",
        remove_unused_columns=False,
        dataloader_num_workers=2,
        seed=42,
    )

    collator = CompletionOnlyPadCollator(pad_token_id=int(tokenizer.pad_token_id))
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        data_collator=collator,
    )

    print("🔥 Starting Stage 1: Native bfloat16 Multi-Turn SFT...")
    train_result = trainer.train()
    eval_metrics = trainer.evaluate()
    sft_loss = float(train_result.training_loss)
    eval_loss = float(eval_metrics.get("eval_loss", 0.0))
    print(f"✅ Stage 1 SFT complete! train_loss={sft_loss:.4f}, eval_loss={eval_loss:.4f}")

    # 3. Stage 2: Execution-Guided GRPO Alignment Pass
    grpo_metrics: dict[str, float] = {}
    if grpo_prompts > 0:
        print(
            f"🎯 Starting Stage 2: Execution-Guided GRPO Alignment ({grpo_prompts} prompts, G=4)..."
        )
        grpo_metrics = run_execution_guided_grpo_pass(
            model=model,
            tokenizer=tokenizer,
            trajectories=raw_rows,
            num_prompts=grpo_prompts,
            group_size=4,
            lr=5e-6,
        )
        print(f"✅ Stage 2 GRPO complete: {grpo_metrics}")

    # 4. Save final bf16 weights + custom LFM3 modeling files to /tmp then copy to /vol (Rule #3)
    local_save_dir = Path("/tmp/lfm3-1.7b-two-hop-bf16")
    if local_save_dir.exists():
        shutil.rmtree(local_save_dir)
    local_save_dir.mkdir(parents=True, exist_ok=True)

    model.config.use_cache = True
    model.save_pretrained(str(local_save_dir), safe_serialization=True)
    tokenizer.save_pretrained(str(local_save_dir))

    # Copy custom remote-code Python files and jinja template from base snapshot so HF repo is self-contained
    for fname in os.listdir(base_snapshot_dir):
        if fname.endswith((".py", ".jinja")) or fname in (
            "special_tokens_map.json",
            "generation_config.json",
        ):
            src_f = Path(base_snapshot_dir) / fname
            dst_f = local_save_dir / fname
            if src_f.is_file() and not dst_f.exists():
                shutil.copy2(src_f, dst_f)

    vol_ckpt_dir = Path("/vol/checkpoints/lfm3-1.7b-two-hop-bf16")
    if vol_ckpt_dir.exists():
        shutil.rmtree(vol_ckpt_dir)
    vol_ckpt_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(str(local_save_dir), str(vol_ckpt_dir))
    volume.commit()
    print(f"💾 Committed bf16 checkpoint to Modal volume: {vol_ckpt_dir}")

    # 5. Push to Hugging Face Hub (`KDDSTLC/lfed-lfm3-1.7b-two-hop-bf16`)
    if push_to_hf:
        print(f"☁️ Uploading bf16 model to Hugging Face Hub ({HF_BF16_MODEL_REPO})...")
        api = HfApi(token=hf_token)
        api.create_repo(repo_id=HF_BF16_MODEL_REPO, repo_type="model", exist_ok=True)
        api.upload_folder(
            folder_path=str(local_save_dir),
            repo_id=HF_BF16_MODEL_REPO,
            repo_type="model",
            commit_message=f"Upload LiquidAI/LFM3-1.7B Two-Hop bf16 checkpoint (train_loss={sft_loss:.4f}, eval_loss={eval_loss:.4f})",
        )
        print(f"✅ Published bf16 model: https://huggingface.co/{HF_BF16_MODEL_REPO}")

    elapsed = round(time.time() - t0, 1)
    summary = {
        "base_model": BASE_MODEL_ID,
        "hf_bf16_repo": HF_BF16_MODEL_REPO,
        "volume_checkpoint": str(vol_ckpt_dir),
        "train_samples": len(train_ds),
        "eval_samples": len(eval_ds),
        "sft_train_loss": round(sft_loss, 4),
        "sft_eval_loss": round(eval_loss, 4),
        **grpo_metrics,
        "elapsed_sec": elapsed,
    }
    Path("/vol/checkpoints/lfm3_training_metrics.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    volume.commit()
    return summary
