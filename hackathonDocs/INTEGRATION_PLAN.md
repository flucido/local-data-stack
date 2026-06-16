# Integration Plan: End-to-End SIS → Warehouse → Natural-Language Query

## Goal

Unify two systems into one local-first pipeline so a local administrator can take
raw data all the way from ingestion through to natural-language querying:

1. **`local-data-stack`** — existing dlt → dbt → DuckDB → Rill education analytics pipeline.
2. **`Kasualdad LFED`** — Gradio app + fine-tuned Qwen2.5-Coder-14B that turns natural
   language into DuckDB SQL (currently a separate repo at
   `/Users/flucido/projects/build-small-hackathon/Kasualdad_LFED`).

The natural-language query capability is brought **into this repo** and pointed at the
**real warehouse** the pipeline produces.

## Confirmed decisions

- **Integration:** Bring the NL→SQL app into `local-data-stack` as a unified project.
- **Schema bridge:** Retrain the model on the real schema (no flat-schema compatibility shim).
- **Privacy/query scope:** Expose both core (hashed student-grain) and analytics layers; the
  read-only execution guard enforces safety.
- **Data source:** California Dept of Education (CDE) downloadable data — real, anonymized.
- **Grain:** **Both layers** — real CDE aggregates *and* a calibrated synthetic student layer.
- **CDE domains:** **All ~16** available domains.

## Key constraint discovered (CDE data)

CDE downloadable files are:
- **Pipe-delimited (`|`) `.txt`**, aggregated at **state/county/district/school** level.
- Disaggregated by race/ethnicity, gender, student program group, grade span.
- **Privacy-suppressed**: cells with ≤10 students shown as `*`.
- **No individual student records** (SOARS student-level data is restricted-access).

Therefore CDE data lands at the **aggregate layer**, and the student-grain layer must be
**synthesized and calibrated** to match CDE rates.

## Target architecture

One local DuckDB warehouse with three queryable schema layers:

- **`cde.*`** — real anonymized CDE aggregate tables, one per domain (absenteeism, enrollment,
  discipline, graduation, dropout, CAASPP, ELPAC, FRPM, English learners, special education,
  foster youth, homeless, stability, post-secondary, staff, accountability, CALPADS UPC, CBEDS).
  Keyed by year + CDS code (county/district/school) + demographic category + grade span.
- **`core.*`** — student-grain star schema (existing dbt `dim_students` / `fact_*`), populated by
  synthetic students calibrated so rollups reproduce CDE numbers.
- **`analytics.*`** — existing derived rollups (`equity_by_race`, `school_summary`, …),
  reconcilable against `cde.*`.

## Phases

### Phase 1 — CDE ingestion (real aggregate layer)
- Build a CDE loader (extend existing `cde_data_pipeline.py` / `stg_cde__*` prior art) to parse
  pipe-delimited `.txt` → stage1 Parquet → `cde.*` tables.
- Handle CDE specifics: `*` suppression → NULL, CDS code parsing, year normalization, COVID
  2019-20 gap, and a `cde.dim_school` / `dim_district` from the CDS code system as join keys.
- **Note:** CDE's site is bot-protected; automated download may fail. Loader ingests from a
  local drop folder of manually downloaded files.

### Phase 2 — Calibrated synthetic student layer
- Use CDE aggregates as ground-truth marginals (rate by district/school × race × gender ×
  program × grade span).
- Generate synthetic students via **iterative proportional fitting** so per-student rollups
  reproduce CDE numbers.
- Feed synthetic raw → existing dlt → dbt pipeline → `core.*` + `analytics.*`.

### Phase 3 — Bring the app in & wire to the warehouse
- Copy `app.py`, `model_inference.py`, `data_engine.py`, `prompts.py`, `tests/` into `nl_query/`.
- Add ML deps as a `[nl-query]` extra in `pyproject.toml`
  (gradio, torch, transformers, peft, bitsandbytes, accelerate, huggingface_hub, spaces;
  llama-cpp-python for local).
- Replace synthetic Parquet seeding with a **read-only attach** to `data/warehouse.duckdb`;
  introspect `cde.*`, `core.*`, `analytics.*`. Keep the execution guard intact.

### Phase 4 — Retarget training to the new schema
- Update `prompts.py` schema doc + few-shots and `generate_synthetic_v2.py`
  `SCHEMA_DOC`/templates/complexity buckets to cover all three layers and both grains.
- Validate every generated SQL against the real Phase-1/2 warehouse.
- Add Gretel augmentation + NL rephrasing; retrain QLoRA (r=32) on Modal; publish a **new
  adapter + GGUF** (versioned HF repo).
- **Context strategy:** expand the model/inference context window so the full three-layer schema
  fits in the prompt (raise training `max_seq_length` and inference context accordingly).

### Phase 5 — End-to-end orchestration & tests
- Single entry point: CDE load + synthetic gen → dbt → `data/warehouse.duckdb` → launch Gradio.
- Update startup checks (verify warehouse exists; drop Parquet-seed requirement).
- Port/adjust the 81-test suite for the new schema + read-only attach.

## Resolved decisions

1. **Inference context strategy** — **Expand the context window** and include the full schema
   in the prompt (raise model/inference context accordingly).
2. **CDE year coverage** — **Last 5 school years.**
3. **Warehouse target** — **Single unified DuckDB file**, renamed `data/warehouse.duckdb`
   (holds `cde.*`, `core.*`, `analytics.*`). Keeps clean two-part table names for the model.
   Split into a separate production DB only when a district connects real Aeries data.

## Dependencies / prerequisites

- Modal access + Hugging Face write token + target HF repo name (for retraining/publishing).
- Local folder of manually downloaded CDE `.txt` files (per Phase 1 note).

## Source references

- Downloadable Data Files — https://www.cde.ca.gov/ds/ad/downloadabledata.asp
- Absenteeism Downloadable Data Files — https://www.cde.ca.gov/ds/ad/chronicdata.asp
- File Structure: Chronic Absenteeism Data — https://www.cde.ca.gov/ds/ad/fsabd.asp
- Record Layout for 2022 Chronic Absenteeism — https://www.cde.ca.gov/ta/ac/cm/chronic22.asp
