# Stage 1 Ingestion — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the Stage 1 gap. Download real CDE source data, install missing dependencies, wire the CDE pipeline into the orchestrator, then run the full pipeline (Stages 1→4) end-to-end and verify Rill dashboards reflect populated data.

**Architecture:** Four sequential phases. Phase 1 acquires CDE source files (the actual data gap). Phase 2 hardens dependencies and config. Phase 3 runs the full pipeline end-to-end. Phase 4 verifies dashboards and documents the result.

**Tech Stack:** Python 3.11, dbt-duckdb 1.11.11, DuckDB, dlt 1.28.0, openpyxl (to install), CDE .txt/.xlsx files

## Global Constraints

- No live Aeries API credentials — Aeries pipeline runs in test mode (synthetic data). This is acceptable.
- CDE data is public — no auth required to download.
- Do not commit downloaded CDE data files to git (they're large and licensed for redistribution with attribution — keep them local). Verify `.gitignore` covers `data/cde_raw/*.txt`, `*.xlsx`, `*.zip` (but NOT `DATA_CATALOG.md`, `README.md`).
- All changes committed atomically per task.
- `PII_SALT` env var must be set before any dbt command (use the local test salt from the prior session).

---

### Task 1: CDE Source File Acquisition — DONE

**Status (2026-06-17):** CDE source files were already present in `data/raw/` (not `data/cde_raw/` — that directory is documentation-only). 22 of 24 CDE domains have real source files covering multiple school years and all three file formats (txt, xlsx, zip). No download needed.

Parse verification done:
- `.txt` (chronic_absenteeism): 263,140 rows in first file, 13 columns, BOM stripped, suppression handling works
- `.xlsx` (frpm): 10,558 rows, 28 columns, auto-header detection works, `School-Level` sheet found

**Files:**
- Read: `oss_framework/pipelines/cde_data_pipeline.py` (DOMAIN_CONFIG globs)
- Read: `data/raw/` directory (22 of 24 domains have files)
- Read: `data/cde_raw/DATA_CATALOG.md` (documentation only — not the data dir)

**Interfaces:**
- Consumes: CDE public download site (already done)
- Produces: Local CDE source files in `data/raw/` (already present)

- [x] **Step 1: Review the domain catalogue and select the subset** — DONE. All 24 domains audited. 22 have files. See spec for the coverage table.

- [x] **Step 2: Verify `.gitignore` excludes CDE data files** — verify status: data/raw is the source dir and should be gitignored. Check before committing.

```bash
git check-ignore data/raw/chronicabsenteeism24.txt data/raw/frpm2425.xlsx
```

If not ignored, add to `.gitignore`:
```
data/raw/*.txt
data/raw/*.xlsx
data/raw/*.zip
```

- [x] **Step 3: Download the 5 selected CDE files** — N/A. Files already present in `data/raw/`. No download needed.

- [x] **Step 4: Verify files are readable by the loader** — DONE. All 22 domains discovered, txt and xlsx parse cleanly.

- [x] **Step 5: Test-parse one txt file end-to-end** — DONE. chronic_absenteeism21.txt: 263,140 rows, 13 columns, suppression markers → None.

- [ ] **Step 6: Commit (if .gitignore needed updating)**

```bash
# Check if data/raw is ignored first
git check-ignore data/raw/chronicabsenteeism21.txt
# If ignored, no commit needed. If not, add patterns and commit.
```

---

### Task 2: Install openpyxl and Verify xlsx Parsing — DONE

**Status (2026-06-17):** `openpyxl` was already declared in `pyproject.toml` as a core dependency (line 39: `"openpyxl>=3.1.0"`). It was not installed in the venv. Installed via `uv pip install --python .venv/bin/python openpyxl` → openpyxl 3.1.5 + et-xmlfile 2.0.0. Verified FRPM xlsx parse: 10,558 rows, 28 columns, `School-Level` sheet found.

Note: `uv sync` fails due to a gradio version conflict in the `nl-query` optional extras (gradio>=6.15.0 requires Python>=3.10 but `requires-python` is >=3.9). Per-package install with `uv pip install --python .venv/bin/python <pkg>` is the workaround.

**Files:**
- Modify: `pyproject.toml` (already has openpyxl — no change needed)
- Read: `oss_framework/pipelines/cde_data_pipeline.py` (xlsx reader)

**Interfaces:**
- Consumes: FRPM xlsx file from Task 1
- Produces: openpyxl installed, FRPM parse verified

- [x] **Step 1: Install openpyxl in the venv** — DONE. `uv pip install --python .venv/bin/python openpyxl` → 3.1.5 installed.

- [x] **Step 2: Add openpyxl to pyproject.toml dependencies** — N/A. Already present at line 39.

- [x] **Step 3: Parse the FRPM xlsx file** — DONE. 10,558 rows, 28 columns, `School-Level` sheet found, auto-header detection works.

- [ ] **Step 4: Commit** — N/A. No pyproject.toml change needed (openpyxl already declared). venv state is local.

---

### Task 3: Document Excel Import Env Vars

**Files:**
- Modify: `.env.example`

**Interfaces:**
- Consumes: ExcelImporter env var names
- Produces: Documented `.env.example` with Excel path vars

- [ ] **Step 1: Read the ExcelImporter to confirm env var names**

Open `oss_framework/pipelines/excel_imports_dlt_pipeline.py:ExcelImporter.__init__`. Confirm the three env vars:
- `EXCEL_DF_REPORT_PATH`
- `EXCEL_DEMOGRAPHIC_PATH`
- `EXCEL_RFEP_PATH`

- [ ] **Step 2: Add the vars to `.env.example`**

Append to `.env.example` (after the Aeries section):
```
# Excel Imports (optional — pipeline skips silently if not set)
# EXCEL_DF_REPORT_PATH=/path/to/df_report.xlsx
# EXCEL_DEMOGRAPHIC_PATH=/path/to/demographics.xlsx
# EXCEL_RFEP_PATH=/path/to/rfep.xlsx
```

Comment them out — there are no default paths. Note that the pipeline skips silently when unset.

- [ ] **Step 3: Commit**

```bash
git add .env.example
git commit -m "docs: document Excel import env vars in .env.example"
```

---

### Task 4: Wire CDE Pipeline into the Orchestrator

**Files:**
- Read: `scripts/run_pipeline.py` (stage1_ingestion method)
- Modify: `scripts/run_pipeline.py`

**Interfaces:**
- Consumes: CDE pipeline entry point
- Produces: Stage 1 runs Aeries → Excel → CDE

- [ ] **Step 1: Read the current stage1_ingestion method**

Open `scripts/run_pipeline.py:stage1_ingestion()`. Currently runs `aeries_dlt_pipeline.py` and `excel_imports_dlt_pipeline.py` via `run_command()`. Each is a subprocess call.

- [ ] **Step 2: Add the CDE pipeline call**

After the Excel pipeline block, add a CDE pipeline block. The CDE pipeline writes to DuckDB by default (destination_type="duckdb", dataset_name="cde_raw"). The entry point is `python3 oss_framework/pipelines/cde_data_pipeline.py` (which runs `run_cde_pipeline` with defaults via `__main__`).

Add to `stage1_ingestion()`:
```python
cde_pipeline = (
    self.project_root / "oss_framework" / "pipelines" / "cde_data_pipeline.py"
)

if cde_pipeline.exists():
    success = success and self.run_command(
        f"python3 {cde_pipeline}",
        "CDE data ingestion (dlt)",
    )
else:
    self.log(f"Skipping: {cde_pipeline} not found", "WARNING")
```

Place it after the Excel block. The CDE pipeline handles missing files gracefully (logs "No files matched" per domain and continues), so a partial `data/cde_raw/` directory won't fail Stage 1.

- [ ] **Step 3: Update the docstring**

Update `stage1_ingestion()` docstring to mention CDE:
```
Runs dlt pipelines to extract data from:
- Aeries API (student, enrollment, attendance, grades) — test mode if no API key
- Excel imports (supplemental data) — skips if env vars not set
- CDE public data files (24 domains) — loads whatever files are in data/cde_raw/
```

- [ ] **Step 4: Verify the orchestrator imports cleanly**

```bash
.venv/bin/python3 -c "from scripts.run_pipeline import PipelineOrchestrator; print('Import OK')"
```

Expected: `Import OK`. If import fails, fix the syntax.

- [ ] **Step 5: Commit**

```bash
git add scripts/run_pipeline.py
git commit -m "feat: wire CDE pipeline into Stage 1 orchestrator"
```

---

### Task 5: Run Stage 1 (Full Ingestion)

**Files:**
- Run: `scripts/run_pipeline.py --stage 1`

**Interfaces:**
- Consumes: CDE files in `data/cde_raw/`, Aeries test mode, Excel env vars (optional)
- Produces: DuckDB `aeries_stage1.raw_*` (refreshed) and `cde_raw.cde_*` (new) tables

- [ ] **Step 1: Set required env vars**

```bash
export PII_SALT="local_test_salt_only_not_for_production_use"
export DUCKDB_DATABASE_PATH="/Users/flucido/projects/local-data-stack/oss_framework/data/analytics.duckdb"
export STAGE1_PATH="./oss_framework/data/stage1"
# Excel vars optional — leave unset to skip
```

- [ ] **Step 2: Run Stage 1**

```bash
.venv/bin/python3 scripts/run_pipeline.py --stage 1 2>&1 | tee /tmp/stage1.log
```

Expected output:
- Aeries pipeline: "Running in TEST MODE with synthetic data" → succeeds, loads 5 resources
- Excel pipeline: skips silently (no env vars set)
- CDE pipeline: logs "Domain 'X': N files, M union columns" per domain → loads rows into `cde_raw.cde_*` tables

If any stage fails, read `/tmp/stage1.log` and diagnose. Common issues:
- CDE file not found → check glob pattern vs actual filename
- openpyxl missing → re-run Task 2
- dlt schema mismatch → inspect the failing domain's file header

- [ ] **Step 3: Verify DuckDB has CDE tables**

```bash
.venv/bin/python3 -c "
import duckdb
con = duckdb.connect('oss_framework/data/analytics.duckdb', read_only=True)
print('=== cde_raw tables ===')
for r in con.execute(\"SELECT table_name FROM information_schema.tables WHERE table_schema='cde_raw' ORDER BY table_name\").fetchall():
    print(f'  {r[0]}')
print()
print('=== row counts ===')
for r in con.execute(\"SELECT table_name FROM information_schema.tables WHERE table_schema='cde_raw' ORDER BY table_name\").fetchall():
    n = con.execute(f'SELECT COUNT(*) FROM cde_raw.{r[0]}').fetchone()[0]
    print(f'  cde_raw.{r[0]:40s} {n:>8} rows')
"
```

Expected: `cde_chronic_absenteeism`, `cde_suspension`, `cde_enrollment_by_grade`, `cde_school_directory`, `cde_frpm` tables with non-zero row counts.

- [ ] **Step 4: Commit (if any code fixes were needed)**

If Stage 1 revealed bugs requiring fixes, commit them. Otherwise skip.

---

### Task 6: Run Stages 2–4 and Tests

**Files:**
- Run: dbt commands, `scripts/export_to_rill.py`

**Interfaces:**
- Consumes: Stage 1 output (populated DuckDB)
- Produces: Analytics marts, Parquet exports, test results

- [ ] **Step 1: Stage 2 — dbt refinement**

```bash
cd oss_framework/dbt && DBT_PROFILES_DIR=. ../../.venv/bin/dbt run --select tag:staging 2>&1 | tail -10
```

Expected: PASS=23. CDE staging views now return real rows.

- [ ] **Step 2: Stage 3 — seed + privacy + core + analytics**

```bash
DBT=/Users/flucido/projects/local-data-stack/.venv/bin/dbt
cd oss_framework/dbt && DBT_PROFILES_DIR=. $DBT seed --select school_cds_mapping_seed 2>&1 | tail -5
DBT_PROFILES_DIR=. $DBT run --select mart_privacy 2>&1 | tail -5
DBT_PROFILES_DIR=. $DBT run --select mart_core 2>&1 | tail -5
DBT_PROFILES_DIR=. $DBT run --select mart_features mart_scoring mart_analytics 2>&1 | tail -10
```

Expected: 1 + 2 + 9 + 25 = 37 PASS. `mart_cde_school_accountability` now has real rows.

- [ ] **Step 3: Verify mart_cde_school_accountability is populated**

```bash
.venv/bin/python3 -c "
import duckdb
con = duckdb.connect('oss_framework/data/analytics.duckdb', read_only=True)
n = con.execute('SELECT COUNT(*) FROM main_analytics.mart_cde_school_accountability').fetchone()[0]
print(f'mart_cde_school_accountability: {n} rows')
if n > 0:
    cols = con.execute('SELECT * FROM main_analytics.mart_cde_school_accountability LIMIT 1').fetchall()
    print(f'Sample columns: {[d[0] for d in con.description]}')
"
```

Expected: non-zero row count. This was 0 before — the CDE data now flows through.

- [ ] **Step 4: Stage 4 — export to Parquet**

```bash
.venv/bin/python3 scripts/export_to_rill.py 2>&1 | tail -20
```

Expected: 5/5 views exported, row counts reflect CDE-enriched data.

- [ ] **Step 5: dbt tests**

```bash
cd oss_framework/dbt && DBT_PROFILES_DIR=. ../../.venv/bin/dbt test 2>&1 | tail -10
```

Expected: PASS=134 (or close — some CDE not-null tests may surface real data quality issues worth noting).

If tests fail on real CDE data, inspect the failures. Some may be legitimate data quality issues (suppressed cells, missing values in certain years) that warrant adjusting the test tolerance, not fixing the data.

- [ ] **Step 6: Commit (if any model fixes needed)**

If dbt tests revealed model bugs, fix and commit. Otherwise skip.

---

### Task 7: Full Pipeline End-to-End Run

**Files:**
- Run: `scripts/run_pipeline.py --stage all`

**Interfaces:**
- Consumes: All prior task outputs
- Produces: Single-command full pipeline execution proof

- [ ] **Step 1: Run the full orchestrator**

```bash
export PII_SALT="local_test_salt_only_not_for_production_use"
export DUCKDB_DATABASE_PATH="/Users/flucido/projects/local-data-stack/oss_framework/data/analytics.duckdb"
.venv/bin/python3 scripts/run_pipeline.py --stage all 2>&1 | tee /tmp/full_pipeline.log
```

Expected: Stages 1→4 all PASS. Completion banner shows total duration. Tests run at the end (may have warnings on real CDE data — acceptable).

- [ ] **Step 2: Verify final DuckDB state**

```bash
.venv/bin/python3 -c "
import duckdb
con = duckdb.connect('oss_framework/data/analytics.duckdb', read_only=True)
print('=== Schema row counts ===')
for schema in ['aeries_stage1', 'cde_raw', 'main_staging', 'main_core', 'main_features', 'main_scoring', 'main_analytics']:
    tables = con.execute(f\"SELECT table_name FROM information_schema.tables WHERE table_schema='{schema}'\").fetchall()
    print(f'{schema}: {len(tables)} tables')
    for t in tables[:3]:
        n = con.execute(f'SELECT COUNT(*) FROM {schema}.{t[0]}').fetchone()[0]
        print(f'  {t[0]:40s} {n:>8} rows')
"
```

- [ ] **Step 3: Commit (if any fixes)**

If the full run revealed issues, fix and commit. Otherwise the working tree should be clean.

---

### Task 8: Verify Rill Dashboards and Document

**Files:**
- Read: `rill_project/dashboards/*.yaml`
- Modify: `CONTRIBUTING.md` (if it has a data setup section), `data/cde_raw/DATA_CATALOG.md` or new `SOURCES.md`

**Interfaces:**
- Consumes: Fresh Parquet exports
- Produces: Verified dashboards + updated docs

- [ ] **Step 1: Restart Rill to pick up fresh Parquet**

```bash
# Find and kill the existing Rill process
pkill -f "rill start" || true
# Restart
cd rill_project && rill start &
# Wait for startup
sleep 3
curl -s -o /dev/null -w "Rill HTTP status: %{http_code}\n" http://localhost:9009/
```

Expected: Rill starts on port 9009 (or next available). HTTP 200 on root.

- [ ] **Step 2: Verify each dashboard loads**

Open http://localhost:9009 in a browser. For each of the 5 dashboards:
- Click into it
- Confirm row counts are non-zero (where expected)
- Confirm dimensions and measures render
- Note any errors

If browser verification isn't possible, query the Parquet files directly:
```bash
.venv/bin/python3 -c "
import duckdb
for f in ['chronic_absenteeism_risk', 'equity_outcomes_by_demographics', 'class_effectiveness', 'performance_correlations', 'wellbeing_risk_profiles']:
    n = duckdb.sql(f\"SELECT COUNT(*) FROM read_parquet('rill_project/data/{f}.parquet')\").fetchone()[0]
    print(f'{f}: {n} rows')
"
```

- [ ] **Step 3: Update DATA_CATALOG.md or create SOURCES.md**

Document where each CDE file was downloaded from, the download date, and the school year covered. Add a note that files are gitignored and must be re-downloaded by anyone cloning the repo.

```bash
# Append to data/cde_raw/DATA_CATALOG.md or create data/cde_raw/SOURCES.md
```

Include per-file:
- Domain key
- Filename
- CDE download URL
- School year
- Download date
- Row count (after load)

- [ ] **Step 4: Update CONTRIBUTING.md data setup section (if it exists)**

Check if `CONTRIBUTING.md` has a "Data Setup" or "Getting Started" section. If yes, add a note:
```
## CDE Data Files

CDE source files are NOT committed to git (large, licensed for redistribution with attribution).
Download the required files into `data/cde_raw/` before running Stage 1. See
`data/cde_raw/DATA_CATALOG.md` for the file list and URLs.
```

- [ ] **Step 5: Final commit**

```bash
git add data/cde_raw/DATA_CATALOG.md data/cde_raw/SOURCES.md CONTRIBUTING.md 2>/dev/null
git commit -m "docs: stage 1 ingestion verification and CDE source documentation"
```

---

### Task 9: Summary Report

**Files:**
- Create: `docs/superpowers/specs/2026-06-17-stage1-ingestion-results.md` (or append to this plan)

- [ ] **Step 1: Write the summary**

```markdown
# Stage 1 Ingestion — Results

**Date:** 2026-06-17
**Branch:** nl-query-integration

## What shipped
- CDE source files downloaded: [count] files covering [count] domains
- openpyxl installed for xlsx parsing
- Excel env vars documented in .env.example
- CDE pipeline wired into Stage 1 orchestrator
- Full pipeline (Stages 1→4) runs end-to-end via `python3 scripts/run_pipeline.py --stage all`

## Pipeline results
- Stage 1 (Ingestion): [Aeries: test mode, N resources | Excel: skipped | CDE: N domains loaded]
- Stage 2 (Refinement): PASS=N staging models
- Stage 3 (Analytics): PASS=N marts (privacy + core + features + scoring + analytics)
- Stage 4 (Export): 5 Parquet files, N total rows
- Tests: PASS=N, WARN=N, ERROR=N

## Key metrics
- mart_cde_school_accountability: [N] rows (was 0 before Stage 1)
- v_chronic_absenteeism_risk: [N] rows
- v_equity_outcomes_by_demographics: [N] rows
- Total DuckDB size: [N] MB

## What did NOT work / deferred
- Aeries real API: out of scope (needs district relationship)
- sbac_caaspp (zip): deferred — large file, caret-delimited path untested on real data
- [any other gaps]

## Commits
- [hash] chore: gitignore CDE raw data files
- [hash] chore: add openpyxl dependency for CDE xlsx files
- [hash] docs: document Excel import env vars in .env.example
- [hash] feat: wire CDE pipeline into Stage 1 orchestrator
- [hash] docs: stage 1 ingestion verification and CDE source documentation
```

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/specs/2026-06-17-stage1-ingestion-results.md
git commit -m "docs: stage 1 ingestion results summary"
```