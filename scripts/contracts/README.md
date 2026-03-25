# Contract Test Toolkit

This folder contains the canonical query-contract checks used for local validation and CI.

## Files
- `contract_query_manifest.json` — single source of truth for contract queries.
- `contract_tests.py` — Python contract runner (used by CI).
- `run_query_audit_phase2.sh` — shell runner that writes detailed PASS/FAIL logs.

## Prerequisites
- Python 3.9+
- DuckDB file available at:
  - `oss_framework/data/oea.duckdb` (default)
  - or set `DUCKDB_DATABASE_PATH`

## Local Usage
### 1) Run CI-equivalent contract checks
```bash
python3 scripts/contracts/contract_tests.py
```

### 2) Run detailed audit logs
```bash
chmod +x scripts/contracts/run_query_audit_phase2.sh
scripts/contracts/run_query_audit_phase2.sh
```
Outputs are written to:
- `DataAnalysisExpert/query_audit_phase2/summary.txt`
- `DataAnalysisExpert/query_audit_phase2/*.log`

### 3) Override DuckDB path
```bash
DUCKDB_DATABASE_PATH=/absolute/path/to/oea.duckdb python3 scripts/contracts/contract_tests.py
```

## Updating Queries
1. Edit `scripts/contracts/contract_query_manifest.json`.
2. Re-run both local checks:
   - `python3 scripts/contracts/contract_tests.py`
   - `scripts/contracts/run_query_audit_phase2.sh`
3. Confirm no new FAIL rows in `DataAnalysisExpert/query_audit_phase2/summary.txt`.

## CI Integration
- Workflow: `.github/workflows/test.yml`
- Job: `contract-tests`
- Triggered on changes under:
  - `schema/**`
  - `dashboards/**`
  - `rill_project/**`
  - `scripts/contracts/**`

## Troubleshooting
- **Error: DuckDB file not found**
  - Set `DUCKDB_DATABASE_PATH` to a valid file.
- **Query contract failures**
  - Check corresponding logs in `DataAnalysisExpert/query_audit_phase2/`.
  - Compare failing SQL with fields in current marts (`main_main_analytics.*`).
- **JSON parse failures**
  - Validate schema definition files with `python3 -m json.tool schema/<file>.json`.
