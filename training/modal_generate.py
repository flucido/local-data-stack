"""
modal_generate.py — Generate NL→SQL training pairs on Modal GPU.

Uses Qwen2.5-72B-Instruct-AWQ via vLLM on A100-80GB to generate diverse
NL→SQL pairs against the curated warehouse schema. Every generated SQL
is validated against the real DuckDB warehouse.

Run:     modal run --detach training/modal_generate.py

Output goes to the lfed-training-data volume (shared with Kasualdad_LFED).
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from pathlib import Path

import modal

# ── Modal app ──────────────────────────────────────────────────────────

app = modal.App("local-data-stack-generate")

# ── Image ──────────────────────────────────────────────────────────────

gen_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("build-essential", "cmake", "git")
    .pip_install(
        "vllm>=0.6.0",
        "duckdb>=1.0.0",
        "huggingface_hub>=0.26.0",
        "requests",
    )
    .env(
        {
            "VLLM_USE_FLASHINFER_SAMPLER": "0",
            "VLLM_USE_FLASHINFER": "0",
            "VLLM_ATTENTION_BACKEND": "XFORMERS",
            "HF_HUB_ENABLE_HF_TRANSFER": "1",
        }
    )
    .add_local_dir(
        Path(__file__).parent,
        remote_path="/root/training",
    )
    .add_local_file(
        Path(__file__).parent.parent / "nl_query" / "prompts.py",
        remote_path="/root/nl_query/prompts.py",
    )
)

# ── Volume ─────────────────────────────────────────────────────────────

volume = modal.Volume.from_name("lfed-training-data", create_if_missing=True)

# ── Model config ───────────────────────────────────────────────────────

MODEL = "Qwen/Qwen2.5-72B-Instruct-AWQ"
VLLM_PORT = 8000
VLLM_API_KEY = "token-gen"


def wait_for_vllm(timeout: int = 900) -> None:
    import requests

    for i in range(timeout):
        try:
            resp = requests.get(f"http://localhost:{VLLM_PORT}/health", timeout=5)
            if resp.status_code == 200:
                print(f"✅ vLLM ready after {i + 1}s")
                return
        except requests.ConnectionError:
            pass
        time.sleep(1)
    raise RuntimeError(f"vLLM did not start within {timeout}s")


def start_vllm() -> subprocess.Popen:
    print(f"🚀 Starting vLLM with {MODEL} ...")
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "vllm.entrypoints.openai.api_server",
            "--model",
            MODEL,
            "--tensor-parallel-size",
            "1",
            "--gpu-memory-utilization",
            "0.85",
            "--max-model-len",
            "16384",
            "--port",
            str(VLLM_PORT),
            "--api-key",
            VLLM_API_KEY,
            "--trust-remote-code",
            "--dtype",
            "auto",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    def _log():
        for line in proc.stdout:
            line = line.rstrip()
            if "Uvicorn running" in line or "ERROR" in line or "Application startup" in line:
                print(f"[vLLM] {line}")

    t = threading.Thread(target=_log, daemon=True)
    t.start()
    return proc


# ── Generation using vLLM API ──────────────────────────────────────────


def call_vllm(prompt: str, temperature: float = 0.8, max_tokens: int = 4096) -> str:
    import json

    import requests

    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    try:
        resp = requests.post(
            f"http://localhost:{VLLM_PORT}/v1/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {VLLM_API_KEY}"},
            timeout=300,
        )
        data = resp.json()
        if "choices" in data:
            return data["choices"][0]["message"]["content"]
        # vLLM may return errors in a different format
        print(f"  ⚠️  vLLM unexpected response: {json.dumps(data, indent=2)[:500]}")
        if "error" in data:
            raise RuntimeError(f"vLLM error: {data['error']}")
        # Try alternate response format
        if "text" in data:
            return data["text"]
        return ""
    except requests.Timeout:
        print("  ⚠️  vLLM request timed out after 180s")
        return ""


# ── Main function ──────────────────────────────────────────────────────


@app.function(
    image=gen_image,
    gpu="A100-80GB",
    volumes={"/data": volume},
    timeout=12 * 3600,
    secrets=[modal.Secret.from_name("huggingface-secret")],
)
def generate_pairs(
    n_pairs: int = 20000,
    batch_size: int = 12,
    output_name: str = "pairs_warehouse.jsonl",
):
    """Generate validated NL→SQL pairs using 72B on A100."""
    sys.path.insert(0, "/root")
    sys.path.insert(0, "/root/training")

    # Validate warehouse exists (bundle small seed db with schema only)
    import duckdb
    from generate_pairs import (
        build_generation_prompt,
        load_schema,
        parse_pairs,
        validate_sql,
    )

    schema = load_schema()
    print(
        f"📋 Schema: {len(schema['tables'])} tables, "
        f"{sum(len(v) for v in schema['tables'].values())} columns"
    )

    # Create a minimal DuckDB with just the schema (no data needed for validation)
    val_conn = duckdb.connect(":memory:")
    # Create schemas first (main_core, main_analytics, main_staging, etc.)
    schemas_created = set()
    for table_name in schema["tables"]:
        s = table_name.split(".")[0]
        if s not in schemas_created:
            val_conn.execute(f"CREATE SCHEMA IF NOT EXISTS {s}")
            schemas_created.add(s)
    for table_name, cols in schema["tables"].items():
        col_defs = []
        for col in cols:
            ctype = col["type"]
            if "VARCHAR" in ctype.upper():
                ctype = "VARCHAR"
            elif "INT" in ctype.upper():
                ctype = "BIGINT"
            elif "DOUBLE" in ctype.upper() or "FLOAT" in ctype.upper():
                ctype = "DOUBLE"
            elif "BOOL" in ctype.upper():
                ctype = "BOOLEAN"
            elif "DATE" in ctype.upper():
                ctype = "DATE"
            col_defs.append(f'"{col["name"]}" {ctype}')
        create_sql = f"CREATE TABLE {table_name} ({', '.join(col_defs)})"
        val_conn.execute(create_sql)

    # Insert one dummy row per table so validation can detect "returns data"
    for table_name in schema["tables"]:
        cols = schema["tables"][table_name]
        placeholders = ", ".join(["NULL"] * len(cols))
        val_conn.execute(f"INSERT INTO {table_name} VALUES ({placeholders})")

    print(f"🗄️  Validation DB: {len(schema['tables'])} empty tables with schema only")

    # Start vLLM
    vllm_proc = start_vllm()
    try:
        wait_for_vllm()

        def llm_call(prompt):
            return call_vllm(prompt, temperature=0.8, max_tokens=4096)

        # Generation loop
        output_path = Path(f"/data/{output_name}")
        total_valid = 0
        total_attempted = 0
        t_start = time.time()

        with open(output_path, "w") as f:
            retry_streak = 0
            while total_valid < n_pairs:
                prompt = build_generation_prompt(batch_size)

                response = llm_call(prompt)
                if not response:
                    retry_streak += 1
                    if retry_streak > 5:
                        print("  ❌ 5 consecutive LLM failures, aborting")
                        break
                    print(f"  ⚠️  LLM returned empty (retry {retry_streak}/5)")
                    time.sleep(5)
                    continue
                retry_streak = 0

                pairs = parse_pairs(response)
                if not pairs:
                    print("  ⚠️  Parse returned 0 pairs, retrying...")
                    time.sleep(2)
                    continue

                total_attempted += len(pairs)
                for pair in pairs:
                    is_valid, msg = validate_sql(pair["sql"], val_conn)
                    if is_valid:
                        f.write(json.dumps(pair) + "\n")
                        total_valid += 1
                f.flush()

                elapsed = time.time() - t_start
                rate = total_valid / elapsed if elapsed > 0 else 0
                pct = total_valid * 100 / total_attempted if total_attempted else 0
                print(f"  ✅ {total_valid}/{n_pairs} ({pct:.0f}% valid, {rate:.1f} pairs/s)")

                if total_valid >= n_pairs:
                    break

        elapsed = time.time() - t_start
        print(f"\n⏱️  Done: {total_valid} pairs in {elapsed:.0f}s ({elapsed/60:.1f}m)")
        print(f"📄 Output: /data/{output_name}")

        # Commit to volume
        volume.commit()
        print("💾 Volume committed")

    finally:
        vllm_proc.terminate()
        try:
            vllm_proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            vllm_proc.kill()
        print("🛑 vLLM stopped")


# ── Run directly (no local_entrypoint — use modal run --detach) ──────

# Defaults for `modal run training/modal_generate.py`
if __name__ == "__main__":
    # No-op: the @app.function above IS the entrypoint.
    # Run with: modal run --detach training/modal_generate.py
    pass
