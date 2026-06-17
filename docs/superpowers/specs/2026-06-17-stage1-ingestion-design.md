# Stage 1 Ingestion — Design Spec

**Date:** 2026-06-17
**Branch:** `nl-query-integration`
**Prior work:** Data deep dive (2026-06-17) completed Stages 2–4 end-to-end. 134 dbt tests pass. Rill dashboards render. The remaining gap is Stage 1: real source data ingestion has never been run end-to-end. DuckDB currently holds synthetic Aeries data only; CDE raw tables are empty.

---

## Goal

Close the loop: run Stage 1 (ingestion) for real, then re-run Stages 2–4, so the full pipeline executes against actual CDE data and (where credentials exist) real Aeries data. Verify the whole stack end-to-end and confirm dashboards reflect populated data.

---

## Current State (audited 2026-06-17)

### What works
- **Aeries dlt pipeline** (`oss_framework/pipelines/aeries_dlt_pipeline.py`): runs in test mode against the `AeriesConnector` synthetic generators (1,700 students, 45K attendance, 200K grades, 2K discipline, 1,700 enrollment). This is what currently populates `aeries_stage1.raw_*` tables in DuckDB.
- **CDE dlt pipeline** (`oss_framework/pipelines/cde_data_pipeline.py`): code is complete for all 24 domains, three file formats (txt/xlsx/zip), BOM stripping, suppression handling, schema-drift tolerant union. Imports cleanly.
- **Excel imports pipeline** (`oss_framework/pipelines/excel_imports_dlt_pipeline.py`): reads D&F report, demographic data, RFEP from Excel paths configured via env vars. Skips gracefully when paths not set.
- **Orchestrator** (`scripts/run_pipeline.py`): runs Stage 1 → Stage 4 with `--stage all` or any single stage. Stage 1 runs Aeries then Excel pipelines.
- **Stages 2–4**: PASS confirmed (23 staging models, 9 core, 25 features/scoring/analytics, 5 Parquet exports, 134 data quality tests). PII is hashed with SHA-256; `dim_students` exposes only `student_id_hash`.

### What's missing / broken
- **`data/raw/` has CDE source files but they were never loaded into DuckDB.** 22 of 24 CDE domains have real source files in `data/raw/` (txt + xlsx + zip), covering multiple school years. The `CDEDataLoader` defaults to `data/raw` as its `data_dir`. The `data/cde_raw/` directory is documentation-only and a red herring. As a result `cde_raw.cde_*` tables in DuckDB don't exist, all CDE staging views return 0 rows, and `mart_cde_school_accountability` is empty.
- **`openpyxl` was not installed** in the venv (FIXED 2026-06-17: installed 3.1.5 via `uv pip install`). Required by `CDEDataLoader._read_xlsx_file` for `frpm`, `upc`, `restraint_seclusion` domains. It was already declared in `pyproject.toml` as a core dependency — the venv was just out of sync. Note: `uv sync` fails due to a gradio version conflict in the `nl-query` optional extras, so venv sync must be done per-package with `uv pip install --python .venv/bin/python <pkg>`.
- **Excel env vars not documented** in `.env.example`: `EXCEL_DF_REPORT_PATH`, `EXCEL_DEMOGRAPHIC_PATH`, `EXCEL_RFEP_PATH` are referenced by `ExcelImporter` but not listed in the example env file. Pipeline silently skips when missing.
- **No live Aeries credentials.** `.env.example` shows `AERIES_API_KEY=replace_with_your_aeries_api_key`. Without a real key the Aeries pipeline falls back to test mode (synthetic data). This is acceptable for the local test but means Aeries data is not "real" school data.
- **Orchestrator Stage 1 does NOT run the CDE pipeline.** `scripts/run_pipeline.py:stage1_ingestion()` runs `aeries_dlt_pipeline.py` and `excel_imports_dlt_pipeline.py` only. The CDE pipeline is not wired into the orchestrator — it must be run separately. This is a gap for the "full pipeline test" goal.

### Non-goals
- Obtaining real Aeries API credentials (out of scope — requires a school district relationship)
- Downloading every CDE domain (24 total). A representative subset is enough to prove the pipeline works end-to-end.
- Building new dashboards. The five existing dashboards are the verification surface.

---

## Phase 1: CDE Source Data Acquisition — DONE

**Status (2026-06-17):** 22 of 24 CDE domains have real source files already in `data/raw/`, covering multiple school years and all three file formats (txt, xlsx, zip). The data was downloaded previously; the gap was that it had never been loaded into DuckDB via the CDE pipeline.

### 1A. Domain coverage (audited 2026-06-17)

Files in `data/raw/` matched against `DOMAIN_CONFIG` globs:

| Domain | Format | Files | Notes |
|---|---|---|---|
| chronic_absenteeism | txt | 5 | 2020-21 through 2024-25, 263K rows in first file alone |
| absenteeism_reason | txt | 5 | 2020-21 through 2024-25 |
| cumulative_enrollment | txt | 4 | |
| census_enrollment_rates | txt | 5 | |
| chronic_absenteeism_dashboard | txt | 1 | 2025 |
| suspension | txt | 5 | |
| suspension_dashboard | txt | 4 | |
| expulsion | txt | 4 | |
| ela_dashboard | txt | 4 | |
| elpac_dashboard | txt | 4 | |
| homeless_enrollment | txt | 4 | |
| frpm | xlsx | 5 | School-Level sheet, 10K rows each |
| upc | xlsx | 5 | |
| restraint_seclusion | xlsx | 3 | |
| sbac_caaspp | zip | 1 | Caret-delimited |
| school_directory | txt | 1 | schldir.txt |
| cbedsora | txt | 10 | a/b file pairs |
| enrollment_by_grade | txt | 1 | |
| enrollment_by_subgroup | txt | 1 | |
| class_assignment | txt | 1 | |
| teacher_misassignment | txt | 1 | |
| teacher_out_of_field | txt | 1 | |
| teacher_prep | txt | 1 | |

**Missing (2 of 24):** None with zero files — `enrollment_by_grade`, `enrollment_by_subgroup`, `class_assignment`, `teacher_misassignment`, `teacher_out_of_field`, `teacher_prep` each have 1 file. All 24 domains have at least one source file except `teacher_prep` — verify that one.

### 1B. Parse verification (done 2026-06-17)

- `.txt` (chronic_absenteeism): 263,140 rows, 13 columns, BOM stripped, suppression handling works
- `.xlsx` (frpm): 10,558 rows, 28 columns, auto-header detection works, `School-Level` sheet found
- `.zip` (sbac_caaspp): untested on real data — defer

**Phase 1 result:** No acquisition needed. Data is present. Skip directly to loading (Phase 3).

---

## Phase 2: Dependency & Config Hardening

### 2A. Install missing Python dependencies — DONE

`openpyxl` was declared in `pyproject.toml` but not installed in the venv. Fixed 2026-06-17 via `uv pip install --python .venv/bin/python openpyxl` (installed 3.1.5). Note: `uv sync` fails due to a gradio version conflict in the `nl-query` optional extras (gradio>=6.15.0 requires Python>=3.10 but `requires-python` is >=3.9). Per-package install with `uv pip install` is the workaround.

### 2B. Document Excel env vars in `.env.example`

Add the three Excel path vars the `ExcelImporter` reads:
```
EXCEL_DF_REPORT_PATH=/path/to/df_report.xlsx
EXCEL_DEMOGRAPHIC_PATH=/path/to/demographics.xlsx
EXCEL_RFEP_PATH=/path/to/rfep.xlsx
```
Comment them out (no default paths — these are user-supplied). Note that the Excel pipeline skips silently when vars are unset.

### 2C. Wire CDE pipeline into the orchestrator

Modify `scripts/run_pipeline.py:stage1_ingestion()` to also run the CDE pipeline after Aeries and Excel. Either:
- Add a `cde_pipeline.py` call alongside the Aeries/Excel ones, OR
- Refactor Stage 1 to run all three pipelines in sequence with individual success tracking.

The CDE pipeline entry point: `python3 -m oss_framework.pipelines.cde_data_pipeline` (or `python3 oss_framework/pipelines/cde_data_pipeline.py`). Default destination_type=duckdb, dataset_name=cde_raw. This writes to the `cde_raw` schema in DuckDB, which is what `oss_framework/dbt/models/staging/cde/sources.yml` expects.

Note: the CDE pipeline should not fail the whole Stage 1 if some domains have no files — it should log and continue. The existing code already handles missing files gracefully (logs "No files matched" and returns).

---

## Phase 3: End-to-End Pipeline Run

### 3A. Run Stage 1 (ingestion)

Run the orchestrator's Stage 1, now including CDE:
```bash
.venv/bin/python3 scripts/run_pipeline.py --stage 1
```

Expected:
- Aeries pipeline runs in test mode (synthetic data) — replaces existing `aeries_stage1.raw_*` tables
- Excel pipeline runs — skips silently if env vars not set (acceptable)
- CDE pipeline runs — loads whatever files are present in `data/cde_raw/` into `cde_raw.cde_*` tables

Verify DuckDB now has `cde_raw` schema with populated tables. Row counts should be non-zero for downloaded domains.

### 3B. Run Stage 2 (dbt refinement)

```bash
cd oss_framework/dbt && DBT_PROFILES_DIR=. dbt run --select tag:staging
```

Expected: 23 models PASS. CDE staging views now return real rows (not 0).

### 3C. Run Stage 3 (analytics marts)

```bash
cd oss_framework/dbt && DBT_PROFILES_DIR=. dbt seed --select school_cds_mapping_seed
cd oss_framework/dbt && DBT_PROFILES_DIR=. dbt run --select mart_privacy
cd oss_framework/dbt && DBT_PROFILES_DIR=. dbt run --select mart_core
cd oss_framework/dbt && DBT_PROFILES_DIR=. dbt run --select mart_features mart_scoring mart_analytics
```

Expected: 1 + 2 + 9 + 25 = 37 models PASS. `mart_cde_school_accountability` now has real rows (was 0 before).

### 3D. Run Stage 4 (export to Parquet)

```bash
.venv/bin/python3 scripts/export_to_rill.py
```

Expected: 5 Parquet files exported. Row counts should reflect CDE data where it feeds in.

### 3E. Run dbt tests

```bash
cd oss_framework/dbt && DBT_PROFILES_DIR=. dbt test
```

Expected: 134 tests PASS. CDE not-null tests now exercise real data — any genuine data quality issues surface here.

### 3F. Run the full orchestrator end-to-end

Single command to prove the whole thing works as one:
```bash
.venv/bin/python3 scripts/run_pipeline.py --stage all
```

Expected: Stages 1→4 all PASS, tests run, completion banner shows duration.

---

## Phase 4: Verification & Documentation

### 4A. Verify dashboards reflect new data

Restart Rill (it watches files, but a restart guarantees fresh state):
```bash
# kill existing rill (pid 83249) and restart
cd rill_project && rill start
```

Open http://localhost:9009 in a browser. Check:
- Chronic Absenteeism Risk: row counts match `v_chronic_absenteeism_risk`
- Equity Outcomes: cohort sizes reflect CDE enrollment data
- Class Effectiveness, Performance Correlations, Wellbeing: all render without errors

### 4B. Update `.env.example` and docs

- Add `EXCEL_*` path vars to `.env.example` (Phase 2B)
- Update `docs/superpowers/specs/2026-06-17-data-deep-dive-design.md` or write a follow-up noting the Stage 1 gap is closed
- Note in `CONTRIBUTING.md` (if it has a data setup section) that CDE files must be downloaded into `data/cde_raw/`

### 4C. Commit

Single commit per logical change:
- `chore: add openpyxl dependency for CDE xlsx files`
- `docs: document Excel import env vars in .env.example`
- `feat: wire CDE pipeline into Stage 1 orchestrator`
- `docs: stage 1 ingestion verification and summary`

---

## Open questions (resolve before starting)

1. **CDE data freshness**: CDE publishes annually. Which school year(s) to download? Latest available is likely 2023-24 or 2024-25. Pick the most recent for each domain.
2. **CDE file naming**: CDE files sometimes have year suffixes (`chronicabsenteeism2425.txt`) or generic names. Verify the glob patterns in `DOMAIN_CONFIG` match what CDE actually publishes. Adjust globs if needed.
3. **School directory PII**: `school_directory` is flagged "Style C, PII" in the domain config. Verify it contains school-level contact info (not student PII) before loading. If it has principal names or similar, that's school-staff PII — decide whether to load it or filter.
4. **Aeries real credentials**: Out of scope for this plan. The test-mode synthetic data is sufficient to prove the pipeline. Real Aeries data requires a district relationship and is a separate workstream.

---

## Deliverables

- `data/cde_raw/` populated with at least 5 CDE source files (txt + xlsx)
- `openpyxl` installed and importable in the venv
- `.env.example` documents Excel env vars
- `scripts/run_pipeline.py` Stage 1 includes the CDE pipeline
- Full pipeline (`--stage all`) runs clean end-to-end
- `mart_cde_school_accountability` has real rows
- Rill dashboards render with populated data
- Verification report committed to docs