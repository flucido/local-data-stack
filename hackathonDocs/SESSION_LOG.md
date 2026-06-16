# Session Log — Phase 3 NL→SQL Scaffolding

**Branch:** `nl-query-integration`
**Status:** Scaffolding complete, verified. Awaiting CDE data drop to begin Phase 1/4.

---

## What we set out to do

Unify the separately-built **Kasualdad LFED** natural-language→SQL Gradio app into the
`local-data-stack` education-analytics pipeline so administrators can query the
DuckDB warehouse in plain English.

See `hackathonDocs/INTEGRATION_PLAN.md` for the full 5-phase plan. This session
delivered **Phase 3: bring the app into the repo and wire it to the real warehouse.**

### Confirmed design decisions (carried from prior session)
- App lives inside the repo at `nl_query/` (flat-module layout, no `__init__`).
- Expose **both** layers: `main_core.*` (hashed student-grain) and `main_analytics.*` (rollups).
- Read-only execution guard + defense-in-depth (warehouse opened `read_only=True`).
- Target data: California Dept of Education (CDE) real aggregates + calibrated synthetic students.
- Ingest all ~16 CDE domains, last 5 school years.
- Single unified warehouse at `data/warehouse.duckdb` (falls back to
  `oss_framework/data/analytics.duckdb` until the unified DB is built).
- Retrain the model on the real star schema (Phase 4, not done yet).

---

## What was built this session

New package `nl_query/` (9 files):

| File | Purpose |
|------|---------|
| `data_engine.py` | Read-only warehouse attach; multi-schema introspection with PII/dlt exclusion; SQL extraction; static + schema-aware validation; `execute_safe` (LIMIT-wrap + watchdog timeout). |
| `prompts.py` | System prompt + live schema context + few-shot examples targeting real warehouse tables. |
| `model_inference.py` | `TransformersLLM` wrapper; thread-safe singleton; `generate_sql` / `generate_sql_streaming`. Heavy imports (torch/transformers/peft) are lazy so the module imports without them. |
| `ui_strings.py` | UI copy + starter questions retargeted to the warehouse (no fabricated school names). |
| `app.py` | Gradio app. Lazy model load; `build_demo()` factory so importing doesn't build UI/require a model; schema injected into prompts. |
| `tests/conftest.py` | `db` fixture → read-only warehouse; skips if no warehouse present. |
| `tests/test_data_engine.py` | Path resolution, introspection, isolation, limits, extract edge cases. |
| `tests/test_execution_guard.py` | Extraction, forbidden tokens, schema-aware validation, read-only enforcement, multi-statement, E2E. |
| `tests/test_model_inference.py` | Prompt assembly, schema/few-shot builders, mocked singleton + generation, JSON envelope. |

Edited `pyproject.toml`: added the `[nl-query]` optional-dependency group
(gradio, transformers, peft, bitsandbytes, accelerate, llama-cpp-python, etc.).

---

## Key technical decisions & constraints

- **Fully-qualified table keys.** Introspection returns `{"schema.table": [(col, type, "")]}`
  so generated SQL is unambiguous against `main_`-prefixed dbt schemas.
- **PII safety.** `get_schema_info` excludes `main_privacy_sensitive`,
  `priv_pii_lookup_table` (de-anonymization keys), and `_dlt_*` bookkeeping tables.
  Warehouse is opened `read_only=True` as defense-in-depth.
- **Warehouse path resolution** (`get_warehouse_path`): env `LFED_WAREHOUSE_DB`
  → `data/warehouse.duckdb` → fallback `oss_framework/data/analytics.duckdb`.
- **Exposed schemas** configurable via `LFED_EXPOSED_SCHEMAS`; defaults cover
  `core`/`main_core`, `analytics`/`main_analytics`, `cde`/`main_cde`.
- **Lazy model load.** `app.py` sets `llm = None` at module level; the 14B model
  only loads in `__main__`. Tests mock `TransformersLLM`.
- **`data/` is git-ignored.** `data/cde_raw/README.md` (drop-folder convention)
  was force-added; `data/warehouse.duckdb` must NEVER be committed.

---

## Verification (all passing)

- Direct introspection: **29 exposed tables** (9 `main_core` + 20 `main_analytics`);
  PII/dlt/blocked schemas correctly excluded.
- Round-trip: `SELECT COUNT(*) FROM main_core.dim_students` → **1700**.
- Test suite: **80 passed** (`pytest nl_query/tests`).

---

## Real warehouse schema (reference)

Source: `oss_framework/data/analytics.duckdb` (the current fallback). 53 tables across
`aeries_stage1`, `main`, `main_analytics`(20), `main_core`(9), `main_features`,
`main_privacy`, `main_privacy_sensitive` (BLOCKED — PII lookup), `main_scoring`,
`main_seeds`, `main_staging`.

Key tables the prompts/few-shots target:
- `main_core.dim_students` — `student_id_hash, academic_year, school_id, grade_level, gender, primary_race, ell_status, special_education_flag, free_reduced_lunch_flag, ...`
- `main_core.fact_attendance` — `student_id_hash, school_id, academic_year, days_enrolled, days_absent, attendance_rate, absence_rate, ...`
- `main_core.fact_discipline` — `incident_type, severity, suspension_days, ...`
- `main_analytics.equity_by_race` — `primary_race, student_count, avg_gpa, avg_attendance_rate, pct_suspended`
- `main_analytics.school_summary` — `school_id, student_count, avg_attendance_rate, avg_gpa, pct_high_risk`

---

## How to run / test (tomorrow)

```bash
# Tests (no model needed; skips warehouse-dependent tests if DB absent)
python3 -m pytest nl_query/tests -o addopts="" -p no:cacheprovider -q

# Install NL→SQL deps when ready to run the app
pip install -e ".[nl-query]"

# Launch the app (loads the 14B model)
python3 nl_query/app.py
```

---

## Next steps (not started)

1. **Phase 1 — CDE loader.** Ingest downloaded CDE files (`data/cde_raw/`) for all
   ~16 domains, last 5 years, into `cde.*` (real aggregates) in the unified warehouse.
2. **Phase 2 — Calibrated synthetic students** in `core.*`, consistent with CDE aggregates.
3. **Build unified `data/warehouse.duckdb`** so the engine stops using the fallback.
4. **Phase 4 — Retrain** the Qwen2.5-Coder model on the real star schema; refresh few-shots.
5. **Phase 5 — Orchestration** to keep the warehouse + model in sync.
