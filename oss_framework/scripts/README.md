# OSS Framework Scripts - Local-First Execution Guide

**Purpose**: Active local-first scripts for Stage 1 ingestion, validation, and DuckDB-based workflows

**Status**: Active guidance only. Archived planning-era and BI/dashboard rollout steps have been removed from this guide.

---

## 🚀 NEW: Modern dlt-Based Data Ingestion (Recommended)

### Why dlt?
- **Schema Evolution**: Automatically handles schema changes in source data
- **Incremental Loading**: Efficiently loads only new/changed data
- **State Management**: Tracks progress for reliable restarts
- **Parquet + DuckDB**: Writes to Parquet files (source of truth) with DuckDB views for fast querying
- **Test Mode**: Auto-generates synthetic data for development/testing

### Quick Start with dlt Pipelines

```bash
# Install dlt
pip install 'dlt[duckdb]'

# Configure environment (test mode - no API key needed)
export AERIES_API_KEY=test_key_for_development_only

# Run Stage 1 ingestion (both Aeries + Excel imports)
python3 oss_framework/scripts/run_stage1_ingestion.py

# Or run individual pipelines:
python3 oss_framework/pipelines/aeries_dlt_pipeline.py filesystem --test
python3 oss_framework/pipelines/excel_imports_dlt_pipeline.py filesystem
```

### What Happens During Ingestion

**Stage 1: dlt pipelines write to Parquet files**
```
oss_framework/data/stage1/
├── transactional/aeries/
│   ├── raw_students/load_date=2026-01-28/*.parquet
│   ├── raw_attendance/load_date=2026-01-28/*.parquet
│   ├── raw_academic_records/load_date=2026-01-28/*.parquet
│   ├── raw_discipline/load_date=2026-01-28/*.parquet
│   └── raw_enrollment/load_date=2026-01-28/*.parquet
└── reference/excel/
    ├── raw_d_and_f/load_date=2026-01-28/*.parquet
    ├── raw_demographic/load_date=2026-01-28/*.parquet
    └── raw_rfep/load_date=2026-01-28/*.parquet
```

**DuckDB Views: Fast querying layer**
```sql
-- Views created by sync_raw_views_from_stage1.py
CREATE VIEW raw_students AS 
  SELECT * FROM read_parquet('stage1/.../raw_students/**/*.parquet');
  
-- Then dbt reads from these views for Stage 2/3 transformations
```

### Configuration for dlt Pipelines

**Environment Variables (.env)**
```bash
# Test mode (generates synthetic data)
AERIES_API_KEY=test_key_for_development_only

# Production mode (connects to real Aeries API)
AERIES_API_KEY=your_actual_api_key_here
AERIES_API_URL=https://your-district.aeries.net/api/v5

 # Optional: Excel file paths
EXCEL_DF_REPORT_PATH=./path/to/d_and_f_report.xlsx
EXCEL_DEMOGRAPHIC_PATH=./path/to/demographic_data.xlsx
EXCEL_RFEP_PATH=./path/to/rfep_data.xlsx
```

### Testing the dlt Pipelines

```bash
# Run comprehensive test suite
python3 -m pytest oss_framework/tests/test_stage1_dlt_pipelines.py -v

# Expected output: 11 tests passing
# ✅ Aeries pipeline: data quality, record counts, file structure
# ✅ Excel pipeline: directory structure, graceful handling of missing files
# ✅ Integration: orchestrator execution, end-to-end flow
```

### Architecture: Hybrid Medallion Pattern

```
┌─────────────────────────────────────────────────┐
│  Stage 1: Parquet Files (Source of Truth)      │
│  - Written by dlt pipelines                    │
│  - Partitioned by load_date                    │
│  - Supports time travel & audit                │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│  DuckDB Views (Fast Query Layer)               │
│  - Created by sync_raw_views_from_stage1.py    │
│  - SELECT * FROM read_parquet(...)             │
│  - No data duplication                         │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│  dbt Transformations (Stage 2/3)               │
│  - Reads from DuckDB views                     │
│  - SQL-based feature engineering               │
│  - Writes back to DuckDB                       │
└─────────────────────────────────────────────────┘
```

### Performance Expectations

| Operation | Expected Time | Notes |
|-----------|--------------|-------|
| Aeries dlt pipeline (test mode) | 30-60 seconds | Generates 1,700 students, 45K attendance, 200K grades |
| Aeries dlt pipeline (production) | 2-5 minutes | Depends on API response time |
| Excel imports pipeline | 10-20 seconds | Depends on file size |
| Test suite execution | 20-40 seconds | 11 comprehensive tests |
| **Total Stage 1 ingestion** | **1-6 minutes** | One-command execution |

### Troubleshooting dlt Pipelines

#### Issue: "No module named 'dlt'"
```bash
pip install 'dlt[duckdb]'
```

#### Issue: "Pipeline completed but no data"
Check if running in test mode vs production:
```bash
# Test mode indicator
echo $AERIES_API_KEY  # Should be "test_key_for_development_only"

# Switch to production
export AERIES_API_KEY=your_real_api_key
export AERIES_API_URL=https://your-district.aeries.net/api/v5
```

#### Issue: "Excel files not found"
Expected behavior - pipeline gracefully skips missing Excel files:
```
⏭️  D&F report not found at: None
⏭️  Demographic data not found at: None
✅ Excel imports pipeline completed (0 loads)
```

#### Issue: "Parquet files not created"
Check directory permissions:
```bash
ls -la oss_framework/data/stage1/transactional/aeries/
chmod -R 755 oss_framework/data/
```

### Migration from Legacy Scripts

If you're currently using the old scripts (`ingest_aeries_data.py`, `import_d_and_f_report.py`):

**Advantages of dlt approach:**
- ✅ No manual schema management
- ✅ Incremental loading built-in
- ✅ Better error handling and retry logic
- ✅ Audit trail via Parquet partitions
- ✅ Test mode for development

**Migration steps:**
1. Run dlt pipelines alongside old scripts (they write to different locations)
2. Validate data quality matches
3. Update DuckDB views to point to Parquet files
4. Archive old scripts once validated

---

## Current Supported Script Surface

Use the active local-first flow in this repository:

```bash
# Install dlt support
pip install 'dlt[duckdb]'

# Optional test-mode credential
export AERIES_API_KEY=test_key_for_development_only

# Run Stage 1 ingestion
python3 oss_framework/scripts/run_stage1_ingestion.py

# Create or refresh DuckDB raw views from the Stage 1 Parquet output
python3 oss_framework/scripts/sync_raw_views_from_stage1.py

# Validate the Stage 1 pipelines
python3 -m pytest oss_framework/tests/test_stage1_dlt_pipelines.py -v
```

If downstream dbt models are part of your run, the DuckDB/dbt handoff happens only after `sync_raw_views_from_stage1.py` creates or refreshes the DuckDB raw views from the Stage 1 Parquet output. Running Stage 1 ingestion alone updates the Parquet source-of-truth files, but dbt reads the DuckDB views rather than the Parquet directories directly.

This guide intentionally omits planning-era setup/orchestration sections and archived BI/runtime rollout instructions. If you need historical implementation notes, treat them as archived reference material rather than active operational guidance.

---

**Status**: Active local-first ingestion guidance only  
**Last Updated**: January 27, 2026
