# local-data-stack

`local-data-stack` is an open-source, local-first analytics framework for K-12 education data. It combines Python orchestration, DuckDB, dbt transformations, Rill dashboards, and a fine-tuned LLM for natural-language SQL generation — so contributors can explore the full architecture without depending on cloud services or private student records.

## What's here

Three integrated layers, all running locally:

1. **Data pipeline** (`oss_framework/`) — dlt ingestion, dbt transformations, DuckDB warehouse. Ingests CDE (California Dept of Education) downloadable data and Aeries SIS exports into a unified warehouse with PII hashing and read-only access controls.

2. **NL-to-SQL query layer** (`nl_query/`) — A Gradio web app powered by a fine-tuned Qwen2.5-Coder-14B LoRA adapter. Administrators ask questions in plain English; the model generates DuckDB SQL, which is validated and executed against the warehouse. Live demo: [Hugging Face Space](https://huggingface.co/spaces/KDDSTLC/LFED).

3. **Dashboards** (`rill_project/`) — Rill BI-as-code dashboards aligned with the California School Dashboard accountability system. Four state indicators: Chronic Absenteeism, Suspension Rate, Academic ELA, and English Learner Progress.

## Hugging Face models

| Model | HF repo | Description |
|-------|---------|-------------|
| LFED SQL v2 (r=64) | [KDDSTLC/lfed-qwen2.5-coder-14b-sql-lora-warehouse-r64](https://huggingface.co/KDDSTLC/lfed-qwen2.5-coder-14b-sql-lora-warehouse-r64) | Trained on real warehouse schema (~30 tables). Current default. |
| LFED SQL v1 (r=32) | [KDDSTLC/lfed-qwen2.5-coder-14b-sql-lora](https://huggingface.co/KDDSTLC/lfed-qwen2.5-coder-14b-sql-lora) | Trained on synthetic 5-table schema. Rollback safety net. |
| LFED GGUF | [KDDSTLC/lfed-qwen2.5-coder-14b-sql-gguf](https://huggingface.co/KDDSTLC/lfed-qwen2.5-coder-14b-sql-gguf) | GGUF quantization for llama.cpp / local inference. |

The v2 adapter (r=64) is trained on the real DuckDB warehouse schema — `main_core`, `main_analytics`, `main_staging` (~30+ tables). Training pairs were generated using Qwen2.5-72B-Instruct-AWQ via vLLM on Modal A100-80GB, with every generated SQL validated by executing it against the real warehouse.

The v1 adapter (r=32) was trained on a simpler 5-table synthetic schema. It is kept as a separate repo (not a version bump) for rollback and comparison.

## Repository layout

```text
local-data-stack/
├── oss_framework/              # Data pipeline
│   ├── connectors/             # Aeries, CDE, Excel source connectors
│   ├── pipelines/              # dlt ingestion pipelines
│   ├── dbt/                     # DuckDB dbt project (staging, marts)
│   ├── data/                    # Warehouse + sample data
│   ├── scripts/                 # Orchestration helpers
│   └── tests/                   # Pipeline + contract tests
├── nl_query/                    # NL-to-SQL query layer
│   ├── app.py                   # Gradio web app
│   ├── model_inference.py       # Transformers + PEFT LoRA wrapper
│   ├── data_engine.py           # DuckDB read-only execution guard
│   ├── prompts.py               # System prompt, schema docs, few-shot
│   ├── eval.py                  # Evaluation harness
│   ├── eval_test_set.jsonl      # Held-out test set (manual curation)
│   └── tests/                   # Unit + E2E tests (mocked LLM)
├── training/                    # Training data generation pipeline
│   ├── generate_pairs.py        # NL->SQL pair generator (local + Ollama)
│   ├── modal_generate.py        # Modal A100 GPU generation (vLLM + 72B)
│   └── training_schema.json     # Curated warehouse schema for training
├── rill_project/                # Rill dashboards (BI-as-code)
│   ├── metrics/                 # Metrics view YAML (one per indicator)
│   ├── dashboards/              # Explore dashboard YAML
│   ├── models/                  # SQL model definitions
│   ├── alerts/                  # Alert definitions
│   └── apis/                    # Custom API definitions
├── models/                      # Local LoRA adapter weights (gitignored)
│   └── README.md                # How to fetch weights from HF Hub
├── scripts/                     # Root orchestration entrypoints
└── docs/                        # CDE reference docs + known issues
```

## Architecture overview

```text
CDE downloadable data files  +  Aeries SIS exports
         ↓
Stage 1: dlt ingestion (oss_framework/pipelines/)
         ↓
Stage 2: dbt transformations (oss_framework/dbt/)
         ↓
DuckDB warehouse (oss_framework/data/analytics.duckdb)
         ↓                              ↓
NL-to-SQL Gradio app              Rill dashboards
(nl_query/ + LoRA model)          (rill_project/)
```

The warehouse uses SHA-256 PII hashing — student identities are pseudonymized as `student_id_hash`. The NL query layer enforces read-only access (`SELECT` only) with schema-aware validation and a watchdog timeout.

### Dashboard layer: California School Dashboard alignment

The Rill dashboard layer is aligned with the **California School Dashboard**, the CDE's integrated accountability and continuous improvement system. Four state indicators are exposed, each sourced directly from the CDE's pre-computed Dashboard downloadable data files:

| Indicator | Source file | Grades | Status measure | Goal direction |
|---|---|---|---|---|
| Chronic Absenteeism | `chronicdownloadYYYY.txt` | TK-8 | Chronic absenteeism rate (%) | Lower is better |
| Suspension Rate | `suspdownloadYYYY.txt` | TK-12 | Suspension rate (%) | Lower is better |
| Academic — ELA | `eladownloadYYYY.txt` | 3-8, 11 | Avg Distance from Standard | Higher is better |
| English Learner Progress (ELPI) | `elpidownloadYYYY.txt` | 1-12 | ELPI status rate (%) | Higher is better |

Each indicator carries the CDE-pre-computed **Status** (current year), **Change** (year-over-year difference), and **Performance Color** (Red - Orange - Yellow - Green - Blue) straight from the state's 5x5 Status x Change grid.

For the full CDE methodology, see the [2025 Dashboard Technical Guide](https://www.cde.ca.gov/ta/ac/cm/dashboardguide.asp).

## Quick start

### 1. Install dependencies

```bash
pip install -e '.[dev]'
```

### 2. Create your local environment file

```bash
cp .env.example .env
# edit .env with your Aeries credentials or local source settings
```

### 3. Run dbt against DuckDB

```bash
cd oss_framework/dbt
dbt deps
DBT_PROFILES_DIR=. dbt parse
DBT_PROFILES_DIR=. dbt build
```

### 4. Launch Rill dashboards

```bash
cd rill_project
rill start
```

### 5. (Optional) Run the NL-to-SQL app

The NL query layer requires a CUDA GPU for the 14B 4-bit model. On macOS, use the GGUF variant with llama.cpp instead.

```bash
# Fetch the LoRA adapter from Hugging Face
hf download KDDSTLC/lfed-qwen2.5-coder-14b-sql-lora-warehouse-r64 \
  --local-dir models/lora-warehouse-r64

# Launch the Gradio app (requires CUDA)
cd nl_query
python app.py
```

### 6. (Optional) Run the eval harness

```bash
cd nl_query
python eval.py --test-set eval_test_set.jsonl --adapter ../models/lora-warehouse-r64
```

## Synthetic sample data

A sample file is included at `oss_framework/data/sample_data/synthetic_student_metrics.parquet`. It contains 5 anonymized rows with columns commonly used by downstream modeling and dashboard examples.

## Validation commands

```bash
# Pipeline tests
python -m pytest oss_framework/tests/test_public_release_sanitization.py -q --no-cov
python scripts/contracts/contract_tests.py

# NL query layer tests (mocked LLM, no GPU needed)
cd nl_query && python -m pytest tests/ -v

# Linting
python -m ruff check oss_framework
python -m black --check oss_framework
```

## Training the model

The training pipeline generates NL-to-SQL pairs against the real warehouse schema, validates every SQL by executing it, and trains a QLoRA adapter.

```bash
# Generate training pairs locally (requires Ollama + DeepSeek-Coder)
python training/generate_pairs.py --n 5000 --output training/pairs.jsonl

# Or generate on Modal with a 72B model (higher quality)
modal run --detach training/modal_generate.py
```

See `training/README.md` and `models/README.md` for details on fetching weights and the training pipeline.

## Known issues

- **Rill metrics gap**: The NL-to-SQL model generates raw DuckDB SQL, not Metrics SQL against Rill metrics views. See [docs/known-issues-rill-metrics-gap.md](docs/known-issues-rill-metrics-gap.md).

## License

- Code: [MIT License](LICENSE)
- Documentation: [CC BY 4.0](LICENSE)