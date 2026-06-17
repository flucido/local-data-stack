# Data Deep Dive Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Test both CDE and Aeries data pipelines end-to-end, audit and fix student data anonymization, and verify the NL-query schema exposure policy.

**Architecture:** Three sequential phases. Phase 1 tests CDE pipeline (aggregate data, no PII risk) end-to-end. Phase 2 audits Aeries PII surface and fixes privacy gaps before data flows. Phase 3 tests Aeries pipeline only after privacy fixes are locked.

**Tech Stack:** Python 3.11, dbt-duckdb, DuckDB, dlt, CDE .txt/.xlsx/.zip files, Aeries SIS connector framework

## Global Constraints

- No connection to a live Aeries API instance (test/synthetic mode only)
- Privacy fixes must be applied before Aeries pipeline testing (Phase 3)
- NL-query schema exposure must block `main_privacy_sensitive` and any PII-bearing schemas
- Hash algorithm should be SHA-256 (migrate from MD5)
- All changes committed atomically per task

---

### Task 1: CDE Source File Inventory

**Files:**
- Read: `oss_framework/pipelines/cde_data_pipeline.py` (the 24 domain configs)
- Read: `data/` directory listing
- Create: none (terminal-only audit)

**Interfaces:**
- Consumes: nothing
- Produces: Terminal report of CDE file coverage (no code output)

- [ ] **Step 1: List CDE domains from pipeline config**

```bash
python3 -c "
from oss_framework.pipelines.cde_data_pipeline import CDE_DOMAINS
for domain, cfg in CDE_DOMAINS.items():
    print(f'{domain:40s} glob={cfg[\"glob\"]}')
" 2>&1
```

Expected: 24 domains with their file glob patterns printed. If the constant is named differently, adjust. If the pipeline doesn't expose the constant at module level, read it from the source file directly.

- [ ] **Step 2: Inventory data/ directory against domain globs**

```bash
python3 -c "
import os, glob

data_dir = 'data'
for root, dirs, files in os.walk(data_dir):
    for f in sorted(files):
        full = os.path.join(root, f)
        size_kb = os.path.getsize(full) / 1024
        print(f'{size_kb:8.1f} KB  {full}')
" 2>&1 | head -120
```

Expected: List of all files in data/ with sizes. Note which files are .txt, .xlsx, .zip, .html.

- [ ] **Step 3: Cross-reference — which domains have source files, which are missing**

Do this manually or with a quick script:
```bash
python3 -c "
import os, fnmatch
from oss_framework.pipelines.cde_data_pipeline import CDE_DOMAINS

data_dir = 'data'
all_files = []
for root, dirs, files in os.walk(data_dir):
    for f in files:
        all_files.append(os.path.join(root, f))

for domain, cfg in sorted(CDE_DOMAINS.items()):
    pattern = cfg['glob']
    matches = [f for f in all_files if fnmatch.fnmatch(os.path.basename(f), pattern)]
    status = f'{len(matches)} file(s)' if matches else 'MISSING'
    print(f'{domain:40s} pattern={pattern:50s} {status}')
    for m in matches:
        print(f'  -> {m}')
" 2>&1
```

Expected: Table showing which of the 24 CDE domains have source files and which are missing.

- [ ] **Step 4: Record findings**

Note any domains with zero files (expected — not all CDE data may have been downloaded). Note any unexpected file formats (e.g., .html files in data/ that look like download pages, not data).

- [ ] **Step 5: Commit (if no code changes, skip)**

```bash
# No code changes expected; just a terminal audit
```

---

### Task 2: CDE Pipeline Dry Run

**Files:**
- Read: `oss_framework/pipelines/cde_data_pipeline.py`
- Modify: none (run existing code)

**Interfaces:**
- Consumes: CDE file inventory from Task 1
- Produces: Pipeline dry-run output showing what would be ingested

- [ ] **Step 1: Check that pipeline module imports cleanly**

```bash
python3 -c "from oss_framework.pipelines import cde_data_pipeline; print('Import OK')" 2>&1
```

Expected: `Import OK` with no errors. If there are import errors (e.g., from deleted `src/`), fix them.

- [ ] **Step 2: Check config loads**

```bash
python3 -c "
from oss_framework.scripts.config import Config
c = Config()
print(f'DuckDB path: {c.DUCKDB_DATABASE_PATH}')
print(f'Stage1 path: {c.STAGE1_PATH}')
print(f'Stage2 path: {c.STAGE2_PATH}')
print(f'Stage3 path: {c.STAGE3_PATH}')
" 2>&1
```

Expected: Paths print correctly. Defaults should resolve even without .env file because config.py has fallbacks.

- [ ] **Step 3: Run pipeline in dry-run/discovery mode**

Examine `cde_data_pipeline.py` to find the main entrypoint. If it's a script with `if __name__ == '__main__'`, identify what happens on execution. Then run a limited test:

```bash
python3 -c "
from oss_framework.pipelines.cde_data_pipeline import CDE_DOMAINS
import os, glob

data_dir = 'data'
# Discover files per domain
for domain, cfg in sorted(CDE_DOMAINS.items()):
    pattern = os.path.join(data_dir, '**', cfg['glob'])
    matches = glob.glob(pattern, recursive=True)
    if matches:
        print(f'{domain}: found {len(matches)} file(s)')
    else:
        print(f'{domain}: NO FILES — will skip')
print('Discovery complete')
" 2>&1
```

Expected: Lists domains and their file counts. No crashes.

- [ ] **Step 4: Test file format parsing on one representative file per format type**

```bash
python3 -c "
import pandas as pd

# Test .txt (tab-delimited with BOM)
txt_file = 'data/cde_raw/absenteeism_reason.txt'
try:
    df = pd.read_csv(txt_file, sep='\t', encoding='utf-8-sig')
    print(f'absenteeism_reason.txt: {len(df)} rows, {len(df.columns)} cols')
    print(f'  Columns: {list(df.columns)[:10]}...')
except Exception as e:
    print(f'absenteeism_reason.txt: ERROR - {e}')

# Test .xlsx (multi-sheet)
import os, glob
xlsx_files = glob.glob('data/cde_raw/**/*.xlsx', recursive=True)
if xlsx_files:
    f = xlsx_files[0]
    try:
        xls = pd.ExcelFile(f)
        print(f'{os.path.basename(f)}: {xls.sheet_names}')
    except Exception as e:
        print(f'{os.path.basename(f)}: ERROR - {e}')
" 2>&1
```

Expected: Files parse without errors. Note any encoding issues, missing columns, or unexpected structure.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "audit: CDE source file inventory and dry run"
```

---

### Task 3: dbt CDE Staging Build

**Files:**
- Read: `oss_framework/dbt/models/staging/cde/sources.yml`
- Read: `oss_framework/dbt/models/staging/cde/stg_cde__*.sql` (all 14 models)
- Read: `oss_framework/dbt/profiles.yml`
- Read: `oss_framework/dbt/dbt_project.yml`

**Interfaces:**
- Consumes: CDE staging models, dbt project config
- Produces: dbt build output for CDE staging models

- [ ] **Step 1: Verify dbt is installed and profiles are configured**

```bash
cd oss_framework/dbt && DBT_PROFILES_DIR=. dbt --version 2>&1
```

Expected: dbt version prints. If dbt not installed: `pip install dbt-duckdb`.

- [ ] **Step 2: Run dbt deps**

```bash
cd oss_framework/dbt && DBT_PROFILES_DIR=. dbt deps 2>&1
```

Expected: Dependencies resolve (or already installed). Note any missing packages.

- [ ] **Step 3: Parse dbt project (finds compilation errors without running)**

```bash
cd oss_framework/dbt && DBT_PROFILES_DIR=. dbt parse 2>&1
```

Expected: All models parse without errors. If there are errors, note which files fail and why (missing refs, syntax errors, etc.).

- [ ] **Step 4: Build only CDE staging models**

First identify the selection syntax. The CDE staging models are in `models/staging/cde/`. Try:

```bash
cd oss_framework/dbt && DBT_PROFILES_DIR=. dbt build --select staging.cde 2>&1
```

If that selector doesn't work, use path-based:
```bash
cd oss_framework/dbt && DBT_PROFILES_DIR=. dbt build --select models/staging/cde/ 2>&1
```

Expected: Each model either builds successfully or fails with a specific error. Document failures.

- [ ] **Step 5: For any failures, inspect the error and the model SQL**

For each failing model, read the SQL and check:
- Source references: does the `source()` call match `sources.yml`?
- Column references: do column names match what the source provides?
- Type casting: are casts valid for the actual data?
- Ref dependencies: do upstream models exist?

Fix one model at a time, re-running `dbt build --select <model_name>` after each fix.

- [ ] **Step 6: Commit after CDE staging builds clean**

```bash
git add -A && git commit -m "fix: dbt CDE staging models build clean"
```

---

### Task 4: CDE Analytics Mart Build

**Files:**
- Read: `oss_framework/dbt/models/mart_analytics/analytics/mart_cde_school_accountability.sql`
- Read: `oss_framework/dbt/models/mart_analytics/analytics/_analytics__models.yml`

**Interfaces:**
- Consumes: CDE staging models (from Task 3)
- Produces: Analytics marts built and verified

- [ ] **Step 1: Build CDE analytics models**

```bash
cd oss_framework/dbt && DBT_PROFILES_DIR=. dbt build --select mart_cde_school_accountability 2>&1
```

Expected: Model builds or fails with a specific error.

- [ ] **Step 2: Verify downstream Rill models still resolve**

Check that Rill models referencing CDE data aren't broken:
```bash
cd oss_framework/dbt && DBT_PROFILES_DIR=. dbt parse 2>&1
```

Confirm full project parses clean after CDE staging + analytics models exist.

- [ ] **Step 3: Run a quick data validation query**

```bash
python3 -c "
import duckdb
con = duckdb.connect('oss_framework/data/analytics.duckdb', read_only=True)
# List tables in analytics schema
tables = con.execute(\"SELECT table_name FROM information_schema.tables WHERE table_schema = 'analytics'\").fetchall()
print('Tables in analytics schema:')
for t in tables:
    print(f'  {t[0]}')
# If mart_cde_school_accountability exists, show row count
try:
    count = con.execute('SELECT COUNT(*) FROM analytics.mart_cde_school_accountability').fetchone()[0]
    print(f'mart_cde_school_accountability: {count} rows')
except Exception as e:
    print(f'mart_cde_school_accountability: {e}')
" 2>&1
```

Expected: Tables listed. Row count shown (may be 0 if no CDE data loaded yet — that's OK).

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "feat: CDE analytics mart builds and validates"
```

---

### Task 5: Aeries PII Field Trace

**Files:**
- Read: `oss_framework/dbt/models/staging/aeries/stg_aeries__students.sql`
- Read: `oss_framework/dbt/models/staging/aeries/stg_aeries__enrollment.sql`
- Read: `oss_framework/dbt/models/staging/aeries/stg_aeries__attendance.sql`
- Read: `oss_framework/dbt/models/staging/aeries/stg_aeries__discipline.sql`
- Read: `oss_framework/dbt/models/staging/aeries/stg_aeries__academic_records.sql`
- Read: `oss_framework/dbt/models/staging/aeries/stg_aeries__programs.sql`
- Read: `oss_framework/dbt/models/mart_core/core/dim_students.sql`
- Read: `oss_framework/dbt/models/mart_analytics/hex_ready/school_summary.sql`
- Read: `oss_framework/dbt/models/mart_analytics/hex_ready/equity_by_race.sql`

**Interfaces:**
- Consumes: Aeries staging models, core models, analytics models
- Produces: PII trace report — which fields contain PII at each layer

- [ ] **Step 1: Read each Aeries staging model and identify PII columns**

Open each `stg_aeries__*.sql` file. For each model, list every column and classify it:

| Classification | Examples |
|---|---|
| **Direct PII** | student_name, date_of_birth, address, ssn, phone, email |
| **Indirect PII (join key)** | student_id, permanent_id, student_number |
| **Non-PII** | grade_level, school_code, academic_year, attendance_days, gpa |
| **Demographic (sensitive)** | ethnicity, race, gender, frpm_status, ell_status, iep_status |

Output a table like:
```
stg_aeries__students:
  student_id        -> Indirect PII (join key)
  permanent_id      -> Indirect PII (join key)
  first_name        -> Direct PII
  last_name         -> Direct PII
  date_of_birth     -> Direct PII
  grade_level       -> Non-PII
  ...
```

Do this for all 6 Aeries staging models plus `dim_students`.

- [ ] **Step 2: Trace PII columns through dim_students**

Read `dim_students.sql`. Identify which PII columns from staging are:
- Hashed (calls `hash_pii()` or `hash_pii_secure()`)
- Dropped (not selected)
- Passed through raw

Also check: does `dim_students` expose `student_id` as a join key? If so, is it hashed or raw?

- [ ] **Step 3: Trace PII into analytics marts**

Read `school_summary.sql` and `equity_by_race.sql`. Verify:
- No Direct PII columns appear
- Join keys are hashed (not raw student_id)
- Demographic fields used only in aggregation, not per-student

- [ ] **Step 4: Record findings in a terminal report**

```bash
echo "=== PII Field Trace Report ==="
echo ""
echo "Aeries Staging -> dim_students -> Analytics"
echo ""
echo "Direct PII columns: [list from Step 1]"
echo "Hashed in dim_students: [list]"
echo "Passed through raw: [list — these are gaps]"
echo "Dropped: [list]"
echo ""
echo "Analytics exposure:"
echo "school_summary: [PII columns present?]"
echo "equity_by_race: [PII columns present?]"
```

- [ ] **Step 5: Commit**

```bash
# Report is terminal output; commit any notes if written to file
```

---

### Task 6: Hash Implementation Review & Fix

**Files:**
- Read: `oss_framework/dbt/macros/hash_pii.sql`
- Read: `oss_framework/dbt/macros/hash_pii_secure.sql`
- Read: `oss_framework/dbt/dbt_project.yml` (vars section)
- Modify: `oss_framework/dbt/macros/hash_pii.sql` (if changing algorithm)
- Modify: `oss_framework/dbt/macros/hash_pii_secure.sql` (if changing algorithm)
- Modify: `oss_framework/dbt/dbt_project.yml` (if changing hash_algorithm var)

**Interfaces:**
- Consumes: PII trace from Task 5
- Produces: Upgraded hash macros (SHA-256)

- [ ] **Step 1: Read current hash macros**

Open `hash_pii.sql` and `hash_pii_secure.sql`. Note:
- What algorithm is used (MD5 vs SHA-256)
- How salt is consumed (from `var('PII_SALT')` or env var?)
- What the difference is between `hash_pii` and `hash_pii_secure`

- [ ] **Step 2: Check dbt_project.yml hash config**

Open `dbt_project.yml`. Under `vars:`, check:
```
hash_algorithm: 'md5'   # or 'sha256'
PII_SALT: "{{ env_var('PII_SALT', 'change_me') }}"
```

Note what's configured. Check `.env.example` for `PII_SALT`.

- [ ] **Step 3: Plan the upgrade to SHA-256**

DuckDB supports `sha256()` as a built-in function. The change is:
```sql
-- Before (MD5):
md5(CONCAT(column_name, '{{ var("PII_SALT") }}'))

-- After (SHA-256):
sha256(CONCAT(column_name, '{{ var("PII_SALT") }}'))
```

If the macro already supports both via a `var('hash_algorithm')` parameter, just change the default in `dbt_project.yml`. If hardcoded to MD5, update the macro.

- [ ] **Step 4: Update dbt_project.yml**

```yaml
vars:
  hash_algorithm: 'sha256'
  PII_SALT: "{{ env_var('PII_SALT', 'change_me') }}"
```

- [ ] **Step 5: Update hash_pii.sql macro if hardcoded**

If the macro reads `var('hash_algorithm')` and dispatches, verify SHA-256 branch works. If hardcoded to MD5:

```sql
{% macro hash_pii(column_name) %}
    sha256(CONCAT({{ column_name }}, '{{ var("PII_SALT") }}'))
{% endmacro %}
```

And same change in `hash_pii_secure.sql` if it differs.

- [ ] **Step 6: Verify the change with dbt parse**

```bash
cd oss_framework/dbt && DBT_PROFILES_DIR=. dbt parse 2>&1
```

Expected: All models still parse. Any model calling `hash_pii()` should still work since DuckDB's `sha256()` has the same signature.

- [ ] **Step 7: Commit**

```bash
git add oss_framework/dbt/dbt_project.yml oss_framework/dbt/macros/hash_pii.sql oss_framework/dbt/macros/hash_pii_secure.sql
git commit -m "security: upgrade PII hash from MD5 to SHA-256"
```

---

### Task 7: NL-Query Schema Exposure Audit

**Files:**
- Read: `nl_query/data_engine.py`
- Read: `nl_query/prompts.py`

**Interfaces:**
- Consumes: data_engine schema filtering, prompt schema injection
- Produces: Audit of which schemas/tables are exposed to the LLM, with fixes if needed

- [ ] **Step 1: Read data_engine.py schema filtering logic**

Open `nl_query/data_engine.py`. Find the section that lists allowed or blocked schemas. It should look something like:

```python
EXPOSED_SCHEMAS = ["core", "analytics", "cde"]
BLOCKED_SCHEMAS = ["main_privacy_sensitive"]
```

Note the actual values. Check how tables are enumerated (information_schema query or hardcoded list).

- [ ] **Step 2: Check prompts.py for schema injection**

Open `nl_query/prompts.py`. Find where table schemas are injected into the system prompt. Verify:
- Only `EXPOSED_SCHEMAS` tables appear
- Column-level details are included (the LLM needs column names to write SQL)
- No PII columns from `dim_students` appear in the prompt

- [ ] **Step 3: Verify there's no circumvention path**

Check if:
- The LLM can query `main_privacy_sensitive` through a view in an exposed schema
- DuckDB's read_only mode prevents writes but allows reads from any schema unless explicitly blocked
- The forbidden tokens check (`data_engine.py`) catches attempts to bypass schema filters

- [ ] **Step 4: If gaps found, fix data_engine.py**

If `dim_students` columns like `first_name`, `last_name`, `date_of_birth` appear in the system prompt, add column-level filtering:

```python
PII_COLUMNS = {
    "core.dim_students": ["first_name", "last_name", "date_of_birth", "student_id"],
}
```

Filter these out when building the schema prompt.

- [ ] **Step 5: Commit**

```bash
git add nl_query/data_engine.py nl_query/prompts.py
git commit -m "security: audit and harden NL-query schema exposure"
```

---

### Task 8: Aeries Pipeline Code Review

**Files:**
- Read: `oss_framework/pipelines/aeries_dlt_pipeline.py`
- Read: `oss_framework/connectors/__init__.py`
- Read: `oss_framework/connectors/aeries.py`
- Read: `oss_framework/connectors/base.py`
- Read: `oss_framework/connectors/mappings/aeries_to_canonical.py`

**Interfaces:**
- Consumes: Connector framework, Aeries implementation
- Produces: Pipeline code review findings and fixes

- [ ] **Step 1: Read the connector framework files**

Open `base.py` to understand the `SISConnector` interface. Then `aeries.py` to see the implementation. Finally `__init__.py` for the factory function.

Check that:
- `AeriesConnector` implements all abstract methods
- Factory `get_sis_connector("aeries")` returns without error
- No references to deleted `src/` or `aeries_column_mappings.py`

- [ ] **Step 2: Read aeries_dlt_pipeline.py**

Check what changed (the commit diff showed 222 lines removed). Verify:
- Does it use `get_sis_connector()` or direct imports?
- Are there any `from src.` imports?
- Does it reference `aeries_column_mappings` (deleted)?
- What does `if __name__ == '__main__'` do?

- [ ] **Step 3: Try a module-level import**

```bash
python3 -c "from oss_framework.pipelines import aeries_dlt_pipeline; print('Import OK')" 2>&1
```

Expected: `Import OK`. If import fails, fix the broken references.

- [ ] **Step 4: Try instantiating the connector in test mode**

```bash
python3 -c "
from oss_framework.connectors import get_sis_connector
connector = get_sis_connector('aeries', test_mode=True)
print(f'Connector: {connector}')
print(f'Test mode: {connector.test_mode}')
" 2>&1
```

Expected: Connector instantiates without error. Test mode is True.

- [ ] **Step 5: Fix any broken references found**

If there are `from src.` imports or `aeries_column_mappings` references, remove them or redirect to the connector framework. If `src/db/connection.py` was imported, replace with direct duckdb usage or the config module.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "fix: repair Aeries pipeline imports after dead code removal"
```

---

### Task 9: Aeries dbt Models Build (with test data)

**Files:**
- Read: `oss_framework/dbt/models/staging/aeries/stg_aeries__*.sql` (6 models)
- Read: `oss_framework/dbt/models/mart_core/core/dim_students.sql`
- Read: `oss_framework/dbt/models/mart_analytics/hex_ready/school_summary.sql`
- Read: `oss_framework/dbt/models/mart_analytics/hex_ready/equity_by_race.sql`
- Potentially create: test seed data or mock Parquet files

**Interfaces:**
- Consumes: Aeries staging models, core models, analytics models
- Produces: dbt build output for Aeries models

- [ ] **Step 1: Check if test/sample data exists**

```bash
ls -la oss_framework/data/sample_data/ 2>&1
ls -la oss_framework/data/stage1/ 2>&1
```

The sample_data directory should have `synthetic_student_metrics.parquet`. The stage1 directory may have `.gitkeep` only.

- [ ] **Step 2: Parse Aeries staging models only**

```bash
cd oss_framework/dbt && DBT_PROFILES_DIR=. dbt parse --select staging.aeries 2>&1
```

Expected: All 6 Aeries staging models parse. If they reference sources that don't exist in the DuckDB yet, that's OK — `dbt parse` only checks SQL syntax and ref existence, not data.

- [ ] **Step 3: Check what happens on dbt build for Aeries models**

Without real Aeries data in DuckDB, most models will produce 0 rows. That's fine — we're validating they compile and execute. Run:

```bash
cd oss_framework/dbt && DBT_PROFILES_DIR=. dbt build --select staging.aeries 2>&1
```

Expected: Models compile and execute. They may produce 0 rows or fail on missing source tables. Document which models fail and why.

- [ ] **Step 4: If sources are missing, check sources.yml**

Read `oss_framework/dbt/models/sources.yml`. Verify source table names match what the pipeline would create. If sources reference tables that the pipeline doesn't produce, the pipeline needs to be run first — but for now, note the gaps.

- [ ] **Step 5: Build dim_students and hex_ready models**

```bash
cd oss_framework/dbt && DBT_PROFILES_DIR=. dbt build --select dim_students school_summary equity_by_race 2>&1
```

Expected: Models compile. May produce 0 rows if staging is empty — that's acceptable at this stage.

- [ ] **Step 6: Record build status for all Aeries models**

```
=== Aeries dbt Build Status ===
stg_aeries__students:       [compiles / fails]
stg_aeries__enrollment:     [compiles / fails]
stg_aeries__attendance:     [compiles / fails]
stg_aeries__discipline:     [compiles / fails]
stg_aeries__academic_records: [compiles / fails]
stg_aeries__programs:       [compiles / fails]
dim_students:               [compiles / fails]
school_summary:             [compiles / fails]
equity_by_race:             [compiles / fails]
```

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "test: Aeries dbt model build validation"
```

---

### Task 10: End-to-End Verification & Wrap-up

**Files:**
- Read: All modified files from Tasks 1-9
- Run: Full dbt project parse

**Interfaces:**
- Consumes: All prior task outputs
- Produces: Final verification report

- [ ] **Step 1: Run full dbt parse**

```bash
cd oss_framework/dbt && DBT_PROFILES_DIR=. dbt parse 2>&1
```

Expected: All models parse without errors.

- [ ] **Step 2: Run full test suite**

```bash
python -m pytest oss_framework/tests/test_public_release_sanitization.py -v --no-cov 2>&1
```

Expected: Existing tests pass. Note any failures (pre-existing or new).

- [ ] **Step 3: Verify NL-query module imports**

```bash
python3 -c "
from nl_query.data_engine import DataEngine
from nl_query.prompts import build_system_prompt
from nl_query.model_inference import ModelInference
print('All NL-query modules import OK')
" 2>&1
```

Expected: All imports succeed.

- [ ] **Step 4: Summarize findings**

```bash
echo "=== Data Deep Dive Summary ==="
echo ""
echo "Phase 1 — CDE Pipeline:"
echo "  CDE staging models: [pass/fail count]"
echo "  CDE analytics models: [pass/fail count]"
echo "  Source files available: [count] / 24 domains"
echo ""
echo "Phase 2 — Aeries Privacy:"
echo "  PII fields traced: [count]"
echo "  Hash algorithm: SHA-256 (migrated from MD5)"
echo "  Schema exposure: [audited / gaps found]"
echo "  Privacy gaps fixed: [count]"
echo ""
echo "Phase 3 — Aeries Pipeline:"
echo "  Imports: [clean / broken]"
echo "  Connector framework: [functional / issues]"
echo "  dbt models (Aeries): [pass/fail count]"
echo ""
echo "Full dbt parse: [pass/fail]"
echo "Tests: [pass/fail]"
```

- [ ] **Step 5: Final commit**

```bash
git add -A && git commit -m "docs: data deep dive verification and summary"
```
