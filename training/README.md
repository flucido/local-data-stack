# Training the LFED NL→SQL Adapter

This directory holds two model tracks:

- **LFM3 two-hop (desktop, current):** verified multi-turn trajectories, bf16
  full fine-tuning plus GRPO, and a Q8_0 GGUF for the desktop host. See
  [Phase 2](#phase-2-sovereign-two-hop-slm-pipeline-liquidailfm3-17b) below.
- **Qwen r=64 (legacy Gradio, single-hop):** synthetic NL→SQL pairs and the
  warehouse adapter published at
  [KDDSTLC/lfed-qwen2.5-coder-14b-sql-lora-warehouse-r64](https://huggingface.co/KDDSTLC/lfed-qwen2.5-coder-14b-sql-lora-warehouse-r64).
  The intermediate dataset is the 25,886-pair set at
  [KDDSTLC/lfed-training-data](https://huggingface.co/datasets/KDDSTLC/lfed-training-data).

The full Local Data Stack README at the repository root documents how these
artifacts fit alongside the warehouse, dashboards, desktop app, and hosted interface.

## What lives here

| Path | Purpose |
| --- | --- |
| `training_schema.json` | Curated warehouse schema used as the prompt context for pair generation. |
| `generate_pairs.py` | Legacy single-hop NL→SQL pair generator. Uses DuckDB and a model to draft questions and SQL, then executes every candidate query against the real warehouse before emitting it. |
| `modal_generate.py` | Two-hop trajectory builder: seeded DuckDB execution, golden/self-healing/follow-up splits, and optional dataset publication. No vLLM or 72B model is used. |
| `modal_train_slm.py` | LFM3 bf16 full fine-tuning plus execution-guided GRPO on Modal A100-80GB. |
| `modal_export_gguf.py` | LFM3 GGUF export: converts bf16 to f16, computes `llama-imatrix`, quantizes to Q8_0, and publishes to the Hub. |
| `reward_fn.py` | Verifiable DuckDB execution-guided reward used by GRPO. |

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

`modal_generate.py` builds verified two-hop trajectories and mounts the
`lfed-training-data` Modal volume so the resulting JSONL survives across runs.
It executes each candidate SQL against seeded DuckDB warehouses.

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

## Exporting the LFM3 Q8_0 GGUF

The desktop app loads a calibrated Q8_0 GGUF. `modal_export_gguf.py` runs in
its own Modal container, downloads the bf16 checkpoint from the Hub (or reads
it from the `lfed-training-data` volume), converts it to f16 GGUF, computes an
importance matrix with `llama-imatrix`, quantizes to Q8_0, and publishes the
result to `KDDSTLC/lfed-lfm3-1.7b-two-hop-gguf`.

Prerequisites:

- Modal CLI authenticated.
- Hugging Face secret `huggingface-secret` with `HF_TOKEN`.
- The bf16 checkpoint published at
  `KDDSTLC/lfed-lfm3-1.7b-two-hop-bf16`, or present in the training volume.

Run:

```bash
modal run training/modal_export_gguf.py
modal volume get lfed-gguf-export /gguf/lfed-lfm3-1.7b-two-hop-Q8_0.gguf models/
```

The local legacy Qwen Q4_K_M file in `models/` is a separate artifact and is
not produced by this job.

## What this pipeline is and is not

This pipeline reproduces an existing research-grade adapter for technical
re-evaluation. It is not a turnkey district-deployment tool:

- Generated pairs are synthetic and reflect one curated schema slice; they do
  not encode Aeries or CDE district secrets.
- LoRA training remains a domain-specific extension of Qwen2.5-Coder-14B; the
  base model's general code-completion behavior is preserved.
- The current repository evidence is a working legacy adapter, a 20-prompt
  development set, and a 30-prompt two-hop holdout; production benchmarks,
  accuracy numbers, and multi-model comparisons are planned research.

See the case-study participation section of the repository README for how
collaborators and supervised district partners can extend this work.

## Phase 2: Sovereign Two-Hop SLM Pipeline (`LiquidAI/LFM3-1.7B`)

The next-generation local-first desktop architecture executes a two-hop tool-calling protocol (`execute_duckdb_query` → in-process DuckDB execution + `Candidate bindings` self-healing → `render_workspace_ui`):

- **Model Checkpoint**: [`KDDSTLC/lfed-lfm3-1.7b-two-hop-bf16`](https://huggingface.co/KDDSTLC/lfed-lfm3-1.7b-two-hop-bf16) (Native `bfloat16` 100% Full Fine-Tuning + execution-guided GRPO on Modal A100-80GB).
- **Quantized GGUF**: [`KDDSTLC/lfed-lfm3-1.7b-two-hop-gguf`](https://huggingface.co/KDDSTLC/lfed-lfm3-1.7b-two-hop-gguf) (`lfed-lfm3-1.7b-two-hop-Q8_0.gguf`, ~1.8 GB, calibrated via `llama-imatrix`).
- **Dataset**: [`KDDSTLC/lfed-lfm3-two-hop-trajectories`](https://huggingface.co/datasets/KDDSTLC/lfed-lfm3-two-hop-trajectories) (3,000 multi-turn K-12 trajectories: 2,100 golden, 450 self-healing SQL recovery, 450 two-turn refinement).

### Pipeline Modules

| File | Purpose |
| :--- | :--- |
| `schema_pruner.py` | Deterministic BM25 + 1-hop FK join pruner selecting the top-5 K-12 warehouse tables (<800 tokens). |
| `gbnf_compiler.py` | Static `hop1_sql.gbnf` grammar and dynamic `compile_hop2_gbnf(columns)` schema compiler. |
| `modal_generate.py` | Multi-turn Two-Hop dataset generator with seeded DuckDB execution and self-healing error injection. |
| `modal_train_slm.py` | Modal A100 training script running 3 epochs SFT with completion-only loss masking + execution-guided GRPO. |
| `modal_export_gguf.py` | Isolated Modal job converting bf16 to f16 GGUF, computing `llama-imatrix`, and quantizing to `Q8_0`. |
| `reward_fn.py` | Verifiable reward: valid Hop 1 JSON and execution score positively, exact result-set match adds the largest bonus, and malformed or failing SQL is penalized. |
| `eval_holdout_local.py` | Local private evaluation runner for testing the fine-tuned model against held-out K-12 questions. |
