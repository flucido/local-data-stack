# Sub-3B Two-Hop (DuckDB SQL + Generative UI) Modal Training Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and execute the Modal training, quantization, and evaluation pipeline for 1.2B–3B Small Language Models (`Qwen2.5-Coder-1.5B/3B`, `Qwen3-1.7B`, `LiquidAI/LFM2.5-1.2B`) that perform deterministic Two-Hop Text-to-SQL (`execute_duckdb_query`) and Generative UI layout selection (`render_workspace_ui`).

**Architecture:** This plan supersedes the v2 14B single-turn Unsloth QLoRA pipeline (`2026-06-23-new-model-integration.md`) and incorporates the four small-model architecture requirements from `docs/Local First Generative Ui Product Spec.md`:
1. **Native `bfloat16` Full Fine-Tuning (FFT) or High-Rank (`r=64`) DoRA on Modal (`A100-80GB` / `H100`)** using standard Hugging Face `transformers` + `trl` + `flash-attn` + `liger-kernel` (zero Unsloth, zero 4-bit QLoRA dequantization noise).
2. **High-Bitrate Calibrated GGUF Export (`Q8_0` for 1.2B–1.7B; `Q6_K` + `llama-imatrix` for 3B)** so sub-3B models retain `99.5%+` of their `bf16` SQL identifier accuracy inside a `~1.6–2.3 GB` desktop footprint.
3. **Top-K Schema Pruning (`k=5` tables) in Both Training & Inference Prompts**, pairing 1–2 gold tables with 3–4 BM25 hard-negative distractor tables so sub-3B attention heads are never diluted across 30+ tables.
4. **In-Process DuckDB Self-Healing (`Split B` error-recovery trajectories) + Dynamic Hop 2 Column-Enum GBNF**, guaranteeing 100% valid JSON and zero hallucinated column bindings.

**Tech Stack:** Python 3.12, DuckDB, Modal (`A100-80GB` / `H100`), PyTorch (`bfloat16`), Hugging Face (`transformers`, `trl`, `peft`, `datasets`), `flash-attn`, `liger-kernel`, `llama.cpp` (`convert_hf_to_gguf.py`, `llama-imatrix`, `llama-quantize`), `pydantic` / `jsonschema`.

---

## Global Operational Constraints (From `hackathonDocs/TRAINING_PLAYBOOK.md`)

- **NEVER use `modal run` for GPU jobs >60 seconds:** Local terminal timeouts cancel remote jobs. Always deploy (`modal deploy training/<script>.py`) and trigger via Python `modal.Function.from_name(...).spawn()`.
- **Seeded Validation Databases Only:** Never validate Hop 1/Hop 2 trajectories against `NULL`-only dummy tables. Mount seeded DuckDB warehouses (`oss_framework/data/analytics.duckdb` + seeded Personal Finance DuckDB) so `duckdb_result_summary` has real `row_count`, `min`/`max`, and `sample_rows`.
- **Bypass `SFTConfig` Pickle Crashes:** Set `save_strategy="no"` in `SFTConfig` and save final weights manually with `model.save_pretrained()` + `tokenizer.save_pretrained()`, using `shutil.move()` across volume mounts followed by `volume.commit()`.
- **Isolated Export Container:** Run GGUF conversion, `llama-imatrix` calibration, and quantization in a dedicated fresh Modal container (`training/modal_export_gguf.py`) rather than sharing GPU memory with training.

---

## File Structure & Responsibilities

| File | Action | Responsibility |
| :--- | :--- | :--- |
| `training/tool_contracts.py` | Create | Canonical Pydantic/JSON schemas for `execute_duckdb_query`, `duckdb_execution_error`, `duckdb_result_summary`, and `render_workspace_ui` (`KPIGrid`, `TimeSeriesChart`, `CategoryBarChart`, `BudgetVarianceChart`, `DataTable`, `FilterBar`). |
| `training/gbnf_compiler.py` | Create | Generates `hop1_sql.gbnf` and dynamically compiles `hop2_ui.gbnf` with exact DuckDB output column enums (`compile_hop2_gbnf(columns)`). |
| `training/schema_pruner.py` | Create | Deterministic BM25 + foreign-key graph pruner (`select_top_k_tables(question, schema, k=5, gold_tables=...)`) used during both synthetic data generation and runtime evaluation. |
| `training/generate_pairs.py` | Modify | Upgrade local generator from single-turn SQL to 2-hop multi-turn ChatML trajectories (Split A Golden 70%, Split B Self-Healing `BinderError` 15%, Split C Follow-up 15%) against seeded DuckDB tables. |
| `training/modal_generate.py` | Modify | Upgrade Modal `Qwen2.5-72B-Instruct-AWQ` generator to mount seeded DuckDB warehouses, apply Top-K schema pruning with hard-negative distractors, and emit 3,000 verified multi-turn trajectories. |
| `training/modal_train_slm.py` | Create | Modal `A100-80GB`/`H100` training app supporting Regime A (`bf16` Full Fine-Tuning for 1.2B–1.7B), Regime B (`bf16` `r=64` DoRA for 3B), completion-only loss masking, and optional 1-epoch `GRPOTrainer` alignment. |
| `training/modal_export_gguf.py` | Modify | Support both full `bf16` checkpoints and DoRA merges, generate a 200-prompt `imatrix.dat` via `llama-imatrix`, and quantize to **`Q8_0`** (1.2B–1.7B) or **`Q6_K`** (3B). |
| `nl_query/eval.py` | Modify | Upgrade evaluation harness to benchmark Top-K schema pruning, Hop 1 EX@1, Self-Healing EX@3 (up to 2 DuckDB error retries), Hop 2 dynamic GBNF UI validity/suitability, and end-to-end latency. |

---

## Task 1: Canonical Tool Contracts & Dynamic GBNF Compiler (Recommendation #4)

**Files:**
- Create: `training/tool_contracts.py`
- Create: `training/gbnf_compiler.py`
- Create: `nl_query/tests/test_gbnf_compiler.py`

- [ ] **Step 1: Define canonical tool & component schemas in `training/tool_contracts.py`**
  - Define `ExecuteDuckDBQueryArgs(explanation: str, sql: str)`.
  - Define `DuckDBResultSummary(status: Literal["ok"], query_id: str, row_count: int, columns: list[ColumnStats], sample_rows: list[list[Any]])`.
  - Define `DuckDBExecutionError(status: Literal["error"], error_type: str, message: str)`.
  - Define `RenderWorkspaceUIArgs(title: str, narrative_summary: str, components: list[UIComponent])` covering `KPIGrid`, `TimeSeriesChart`, `CategoryBarChart`, `BudgetVarianceChart`, `DataTable`, and `FilterBar`.
  - Include `validate_ui_semantics(ui_args, result_summary) -> tuple[bool, str]` to verify data-shape-to-chart suitability (e.g., `KPIGrid` requires `row_count == 1`; `TimeSeriesChart` requires temporal `x_column`; every bound column must exist in `result_summary.columns`).

- [ ] **Step 2: Implement `training/gbnf_compiler.py`**
  - Implement `compile_hop1_gbnf() -> str` enforcing valid JSON for `execute_duckdb_query` where `sql` starts with `SELECT ` or `WITH `.
  - Implement `compile_hop2_gbnf(valid_columns: list[str]) -> str` dynamically restricting every `column`, `x_column`, `y_columns`, and `series_column` terminal in `render_workspace_ui` to the exact column names returned by DuckDB in Hop 1.

- [ ] **Step 3: Unit test contracts and dynamic grammar generation**
  - Run `uv run pytest nl_query/tests/test_gbnf_compiler.py -v`.

---

## Task 2: Top-K Schema Pruner with Hard-Negative Distractors (Recommendation #3)

**Files:**
- Create: `training/schema_pruner.py`
- Create: `nl_query/tests/test_schema_pruner.py`

- [ ] **Step 1: Implement deterministic BM25 + Foreign-Key Graph Pruner (`training/schema_pruner.py`)**
  - Implement `select_top_k_tables(question: str, schema: dict, k: int = 5) -> list[str]` that scores each table in `training_schema.json` (and Personal Finance schemas) by token overlap against table names, column names, descriptions, and enum hints, plus 1-hop foreign-key join neighbors (`student_id_hash`, `cds_code`, `school_id`, `account_id`).
  - Implement `build_training_ddl_subset(question: str, gold_sql: str, schema: dict, k: int = 5) -> str`:
    1. Parse `gold_sql` to extract the 1–2 actual tables used.
    2. Fill the remaining `k - len(gold_tables)` slots with the highest-scoring non-gold tables from `select_top_k_tables` (hard-negative distractors).
    3. Shuffle the `k` tables deterministically and format the compact DDL string (<800 tokens).

- [ ] **Step 2: Verify recall on existing `nl_query/eval_test_set.jsonl`**
  - Assert that `select_top_k_tables(..., k=5)` achieves `>= 98%` recall of gold tables across all questions in `nl_query/eval_test_set.jsonl`.

---

## Task 3: Seeded Multi-Turn & Self-Healing Dataset Synthesis on Modal (Recommendations #3 & #4)

**Files:**
- Modify: `training/generate_pairs.py`
- Modify: `training/modal_generate.py`

- [ ] **Step 1: Replace `NULL`-row validation in `training/modal_generate.py` with seeded DuckDB warehouses**
  - Mount `oss_framework/data/analytics.duckdb` (or a compacted 50 MB seed warehouse with 2,000 realistic rows per table) plus a seeded Personal Finance & Budget DuckDB (`finance_seed.duckdb`) into the Modal volume `lfed-training-data`.
  - Compute real `DuckDBResultSummary` metadata (`row_count`, `distinct_count`, `min`, `max`, `sample_rows`) on every candidate SQL query.

- [ ] **Step 2: Generate the Three Trajectory Splits (3,000 Total Verified Trajectories)**
  - **Split A (70% / 2,100 examples — Golden 2-Hop)**: `System + 5-Table Pruned DDL` → `User` → `Assistant (execute_duckdb_query)` → `Tool (duckdb_result_summary)` → `Assistant (render_workspace_ui)`.
  - **Split B (15% / 450 examples — Self-Healing Error Recovery)**: Perturb column names or date functions on valid SQL, execute against DuckDB to capture the exact `BinderError` (with `Candidate bindings`), and emit the 3-step trajectory (`User` → `Erroneous SQL (loss_mask=0)` → `Tool (duckdb_execution_error)` → `Corrected SQL (loss_mask=1)` → `Tool (duckdb_result_summary)` → `Assistant UI (loss_mask=1)`).
  - **Split C (15% / 450 examples — Conversational Follow-Ups)**: Append a second user turn refining filters or grouping (`"Now filter that to just recurring subscriptions"`).

- [ ] **Step 3: Deploy and spawn on Modal**
  ```bash
  modal deploy training/modal_generate.py
  uv run python -c "import modal; modal.Function.from_name('local-data-stack-generate', 'generate_trajectories').spawn(n_trajectories=3000)"
  ```

---

## Task 4: Native `bfloat16` Full Fine-Tuning / High-Rank DoRA & GRPO on Modal (Recommendation #1)

**Files:**
- Create: `training/modal_train_slm.py`

- [ ] **Step 1: Build `training/modal_train_slm.py` with Pure Hugging Face + `FlashAttention-2` + `Liger-Kernel`**
  - Configure Modal image with `torch>=2.4.0`, `transformers>=4.46.0`, `trl>=0.12.0`, `peft>=0.13.0`, `flash-attn`, `liger-kernel`, `duckdb>=1.0.0` on `gpu="A100-80GB"` or `gpu="H100"`.
  - Support two clean `bfloat16` training modes (no Unsloth, no `bitsandbytes` 4-bit):
    - **`mode="fft"` (Default for 1.2B–1.7B models: `Qwen/Qwen2.5-Coder-1.5B-Instruct`, `Qwen/Qwen3-1.7B`, `LiquidAI/LFM2.5-1.2B-Instruct`)**: Full `bf16` parameter updates, `lr=2e-5`, cosine schedule, `neftune_noise_alpha=5.0`, `use_liger_kernel=True`, `save_strategy="no"`.
    - **`mode="dora"` (Default for 3B models: `Qwen/Qwen2.5-Coder-3B-Instruct`, `LiquidAI/LFM2-2.6B`)**: `LoraConfig(use_dora=True, r=64, lora_alpha=128, target_modules="all-linear")`, `lr=1e-4`.
  - Enforce **Completion-Only Loss Masking** so loss is computed *only* on valid assistant tool-call turns (`labels = -100` on `system`, `user`, `tool`, and Split B erroneous Turn 1 assistant outputs).

- [ ] **Step 2: Add Optional 1-Epoch Execution-Guided `GRPOTrainer` Function (`run_grpo_alignment`)**
  - Implement deterministic reward scoring using `validate_sql` + `execution_match` (Hop 1) and `validate_ui_semantics` (Hop 2).

- [ ] **Step 3: Deploy and spawn training runs via Fire-and-Forget**
  ```bash
  modal deploy training/modal_train_slm.py
  uv run python -c "import modal; modal.Function.from_name('local-data-stack-train-slm', 'train_sft').spawn(base_model='Qwen/Qwen2.5-Coder-1.5B-Instruct', mode='fft')"
  ```

---

## Task 5: Calibrated High-Bitrate (`Q8_0` / `Q6_K` + `imatrix`) GGUF Export (Recommendation #2)

**Files:**
- Modify: `training/modal_export_gguf.py`

- [ ] **Step 1: Upgrade `training/modal_export_gguf.py` for `imatrix` + `Q8_0` / `Q6_K`**
  - Support exporting both standalone `bf16` full-fine-tuned checkpoints (skipping PEFT merge) and `bf16` DoRA checkpoints (`merge_and_unload()`).
  - Convert to `f16.gguf` via `convert_hf_to_gguf.py`.
  - Generate `calibration_sql_genui.txt` (200 multi-turn prompts + tool calls from the training set) and run `llama-imatrix` to produce `imatrix.dat`.
  - Quantize based on model size tier:
    - **1.2B–1.7B models**: Export **`Q8_0`** (`~1.6–1.8 GB`) — near-lossless vs. `bf16`.
    - **3B models**: Export **`Q6_K` with `--imatrix imatrix.dat`** (`~2.3 GB`) and **`Q5_K_M` with `--imatrix imatrix.dat`** (`~2.0 GB`).

- [ ] **Step 2: Deploy, spawn export, and pull GGUF locally**
  ```bash
  modal deploy training/modal_export_gguf.py
  uv run python -c "import modal; modal.Function.from_name('local-data-stack-export-gguf', 'export_gguf').spawn(run_id='qwen2.5-coder-1.5b-fft', quant_type='Q8_0')"
  modal volume get lfed-gguf-export /gguf/lfed-qwen2.5-coder-1.5b-2hop-Q8_0.gguf models/
  ```

---

## Task 6: Two-Hop + Self-Healing + Dynamic GBNF Evaluation Gate (`nl_query/eval.py`)

**Files:**
- Modify: `nl_query/eval.py`
- Modify: `nl_query/model_inference.py`

- [ ] **Step 1: Wire `LlamaCppLLM` in `nl_query/model_inference.py` to support `LlamaGrammar` and Multi-Turn KV Reuse**
  - Accept `grammar_str: str | None` in `LlamaCppLLM.__call__` via `llama_cpp.LlamaGrammar.from_string(grammar_str)`.
  - Maintain conversation messages across Hop 1, optional Self-Healing Retry (up to 2 retries on DuckDB `BinderError`), and Hop 2 so `llama.cpp` reuses the KV cache prefix.

- [ ] **Step 2: Upgrade `nl_query/eval.py` to report all four release gates**
  - **Gate 1 — Hop 1 First-Pass Execution Match (`EX@1`)**: Target `>= 90%`.
  - **Gate 2 — Hop 1 Self-Healing Execution Match (`EX@3`, max 2 retries)**: Target `>= 96%`.
  - **Gate 3 — Hop 2 UI Schema & Semantic Suitability**: Target `100%` JSON schema validity (via dynamic `compile_hop2_gbnf`) and `>= 94%` semantic chart suitability.
  - **Gate 4 — End-to-End Two-Hop Latency**: Target `< 800ms` on Apple Silicon Metal.
