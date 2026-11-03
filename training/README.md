# Training the LFED NL→SQL Adapter

This directory contains the local-first K-12 NL→SQL adapter training pipeline. The
default output is the r=64 warehouse adapter published at
[KDDSTLC/lfed-qwen2.5-coder-14b-sql-lora-warehouse-r64](https://huggingface.co/KDDSTLC/lfed-qwen2.5-coder-14b-sql-lora-warehouse-r64).
The intermediate dataset that produced it is the synthetic 25,886-pair set at
[KDDSTLC/lfed-training-data](https://huggingface.co/datasets/KDDSTLC/lfed-training-data).

The full Local Data Stack README at the repository root documents how this adapter
fits alongside the warehouse, dashboards, and hosted interface.

## What lives here

| Path | Purpose |
| --- | --- |
| `training_schema.json` | Curated warehouse schema used as the prompt context for pair generation. |
| `generate_pairs.py` | Local NL→SQL pair generator. Uses DuckDB and a strong instruction-tuned model to draft questions and SQL, then executes every candidate query against the real warehouse before emitting it. |
| `modal_generate.py` | Modal A100 runner that calls Qwen2.5-72B-Instruct-AWQ via vLLM to mass-generate validated pairs. |
| `modal_export_gguf.py` | Modal job that merges the LoRA adapter into the fp16 base, converts to GGUF, quantizes to Q4_K_M, and writes the result to the `lfed-gguf-export` Modal volume. |

The Modal scripts are the production path; the local script is useful for
smoke-testing the pipeline against a smaller schema slice without GPU cost.

## Local pair-generation flow

`generate_pairs.py` reads the curated schema from `training_schema.json`, opens
the warehouse at `oss_framework/data/analytics.duckdb` read-only, and asks a
local model to author NL→SQL pairs. Every generated SQL is executed against
the warehouse before it is written; failed or non-deterministic SQL is
discarded so the dataset only contains executable pairs.

```bash
# Smoke-test with 100 pairs and a dry-run; no LLM call, no writes
uv run python training/generate_pairs.py --n 100 --output training/pairs.jsonl --dry-run

# Produce 5,000 validated pairs locally
uv run python training/generate_pairs.py --n 5000 --output training/pairs.jsonl
```

The script depends on the warehouse existing and on a generation backend being
configured. Pair quality and execution latency scale with the model chosen.

## Modal pair-generation flow

`modal_generate.py` runs the same validated-pair pipeline on a Modal A100
container. It mounts a `lfed-training-data` Modal volume so the resulting JSONL
survives across runs.

Prerequisites:

- Modal CLI authenticated (`modal profile list` shows your workspace).
- A Modal volume named `lfed-training-data` (the script creates it if missing).
- Optional Hugging Face secret named `huggingface-secret` with `HF_TOKEN` if
  the generation model is gated.

Run:

```bash
# Fire-and-forget; check modal app logs for the run
modal run --detach training/modal_generate.py
```

The volume persists pairs between runs; delete it to start fresh.

## Exporting a GGUF copy

Apple Silicon users need the LoRA merged into a GGUF so llama.cpp can load it
without a separate adapter file. `modal_export_gguf.py` does that conversion
and writes the output to the Modal volume `lfed-gguf-export` rather than the
Hub.

Prerequisites:

- Modal CLI authenticated.
- Hugging Face secret `huggingface-secret` with `HF_TOKEN` (used to fetch the
  fp16 base model).
- The r=64 adapter materialized locally under `models/lora-warehouse-r64/`
  (download from the Hub first; see [`models/README.md`](../models/README.md)).

Run and retrieve:

```bash
modal run training/modal_export_gguf.py
modal volume get lfed-gguf-export /gguf/<output-filename>.gguf models/
```

Move the downloaded artifact to
`models/lfed-qwen2.5-coder-14b-sql-warehouse-r64-Q4_K_M.gguf` so the local
Apple Silicon / CPU backend picks it up automatically (see
[`README.md`](../README.md)).

## What this pipeline is and is not

This pipeline reproduces an existing research-grade adapter for technical
re-evaluation. It is not a turnkey district-deployment tool:

- Generated pairs are synthetic and reflect one curated schema slice; they do
  not encode Aeries or CDE district secrets.
- LoRA training remains a domain-specific extension of Qwen2.5-Coder-14B; the
  base model's general code-completion behavior is preserved.
- The current repository evidence is a working adapter and a 20-prompt
  development evaluation set; production benchmarks, accuracy numbers, and
  multi-model comparisons are planned research.

See the case-study participation section of the repository README for how
collaborators and supervised district partners can extend this work.

## Phase 2: Sovereign Two-Hop SLM Pipeline (`LiquidAI/LFM3-1.7B`)

The next-generation local-first desktop architecture executes a two-hop tool-calling protocol (`execute_duckdb_query` → in-process DuckDB execution + `Candidate bindings` self-healing → `render_workspace_ui`):

- **Model Checkpoint**: [`KDDSTLC/lfed-lfm3-1.7b-two-hop-bf16`](https://huggingface.co/KDDSTLC/lfed-lfm3-1.7b-two-hop-bf16) (Native `bfloat16` 100% Full Fine-Tuning + execution-guided GRPO on Modal A100-80GB).
- **Quantized GGUF**: [`KDDSTLC/lfed-lfm3-1.7b-two-hop-gguf`](https://huggingface.co/KDDSTLC/lfed-lfm3-1.7b-two-hop-gguf) (`lfed-lfm3-1.7b-two-hop-Q8_0.gguf`, 1.76 GB, calibrated via `llama-imatrix`).
- **Dataset**: [`KDDSTLC/lfed-lfm3-two-hop-trajectories`](https://huggingface.co/datasets/KDDSTLC/lfed-lfm3-two-hop-trajectories) (3,000 multi-turn K-12 trajectories: 2,100 Golden, 450 Self-Healing SQL Recovery, 450 2-Turn Refinement).

### Pipeline Modules

| File | Purpose |
| :--- | :--- |
| `schema_pruner.py` | Deterministic BM25 + 1-hop FK join pruner selecting the top-5 K-12 warehouse tables (<800 tokens). |
| `gbnf_compiler.py` | Static `hop1_sql.gbnf` grammar and dynamic `compile_hop2_gbnf(columns)` schema compiler. |
| `modal_generate.py` | Multi-turn Two-Hop dataset generator with seeded DuckDB execution and self-healing error injection. |
| `modal_train_slm.py` | Modal A100 training script running 3 epochs SFT with completion-only loss masking + execution-guided GRPO. |
| `modal_export_gguf.py` | Isolated Modal job converting bf16 to f16 GGUF, computing `llama-imatrix`, and quantizing to `Q8_0`. |
| `reward_fn.py` | Verifiable DuckDB execution-guided reward function (+2.0 execution hit, -1.0 syntax error). |
| `eval_holdout_local.py` | Local private evaluation runner for testing the fine-tuned model against held-out K-12 questions. |
