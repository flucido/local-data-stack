# OSS Framework Scripts - Week 1-2 Execution Guide

**Purpose**: Ready-to-run scripts for data foundation setup, ingestion, and validation

**Status**: ✅ All scripts prepared and ready to execute

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
AERIES_BASE_URL=https://your-district.aeries.net/api/v5
AERIES_SCHOOL_CODES=001,002,003

# Optional: Excel file paths
EXCEL_DF_REPORT_PATH=./path/to/d_and_f_report.xlsx
EXCEL_DEMOGRAPHIC_DATA_PATH=./path/to/demographic_data.xlsx
EXCEL_RFEP_DATA_PATH=./path/to/rfep_data.xlsx
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
export AERIES_BASE_URL=https://your-district.aeries.net/api/v5
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

## 📋 Legacy Scripts Overview (Prior to dlt Implementation)

### Pre-Implementation Phase (Run BEFORE Week 1)

#### 1. `setup_week1_automated.sh`
**Purpose**: Complete setup of development environment  
**When to run**: ONCE, at very beginning  
**What it does**:
- Creates Python virtual environment
- Installs all dependencies
- Creates config modules (config.py, logging_config.py, data_quality.py)
- Creates test infrastructure
- Generates .env template

**Run it**:
```bash
bash oss_framework/scripts/setup_week1_automated.sh
```

**Output**:
- Virtual environment ready at `./venv/`
- All Python modules created
- Test suite initialized
- `.env.template` generated

---

#### 2. `validate_preimplementation.py`
**Purpose**: Validate all prerequisites BEFORE starting Week 1  
**When to run**: AFTER setup_week1_automated.sh and AFTER answering clarification questions  
**What it does**:
- Checks Python version (3.9+)
- Verifies all required packages installed
- Validates environment variables configured
- Tests DuckDB connection
- Confirms data directories exist and are writable
- Verifies Excel files accessible (if configured)
- Checks clarification questions answered

**Run it**:
```bash
python oss_framework/scripts/validate_preimplementation.py
```

**Output**:
- Green ✅ for passing checks
- Red ❌ for failures (with fix suggestions)
- Green ⏭️ for skipped checks (optional)
- Summary report

**Success looks like**:
```
Results: 15✅ 0❌ 2⏭️ (Total: 17)
========================================================
✅ All checks passed! Ready for Week 1-2 implementation.
```

---

### Week 1-2 Implementation Phase (Run IN SEQUENCE)

#### 3. `run_week1_orchestrator.py`
**Purpose**: Execute complete Week 1-2 data foundation in one command  
**When to run**: AFTER validation passes  
**What it does**:
1. Creates Stage 1 tables in DuckDB
2. Ingests all Aeries data (students, attendance, grades, discipline)
3. Imports D&F report from Excel
4. Imports demographic data from Excel
5. Runs data quality validation tests
6. Generates execution report

**Run it**:
```bash
python oss_framework/scripts/run_week1_orchestrator.py
```

**Output**:
- Detailed logs in `./oss_framework/logs/oea.log`
- Console output showing each step
- Final report with:
  - Total duration
  - Results for each step
  - Data record counts
  - Next steps

**Success looks like**:
```
✅ Stage 1 tables created
✅ Aeries data ingested: {'students': 1234, 'attendance': 45678, ...}
✅ D&F report imported: 456 records
✅ Demographic data imported: 1234 records
✅ All data quality tests passed (15/15)

Week 1-2 Data Foundation Setup Complete
Duration: 234.5 seconds
```

---

## 🔄 Complete Execution Flow

### Quick Start (One-Command Approach)

```bash
# Step 1: Initial setup (one time only)
bash oss_framework/scripts/setup_week1_automated.sh

# Step 2: Validate prerequisites
source venv/bin/activate
python oss_framework/scripts/validate_preimplementation.py

# Step 3: Run Week 1-2 data foundation
python oss_framework/scripts/run_week1_orchestrator.py

# Step 4: Check results
tail -f oss_framework/logs/oea.log
```

### Manual Step-by-Step Approach

If you prefer to run each step individually (better for debugging):

```bash
# Activate environment
source venv/bin/activate

# Step 1: Create Stage 1 tables
python oss_framework/scripts/create_stage1_tables.py

# Step 2: Ingest Aeries data
python oss_framework/scripts/ingest_aeries_data.py

# Step 3: Import D&F report
python oss_framework/scripts/import_d_and_f_report.py

# Step 4: Import demographic data
python oss_framework/scripts/import_demographic_data.py

# Step 5: Validate data quality
pytest oss_framework/tests/test_stage1_data_quality.py -v

# Step 6: Check DuckDB directly
duckdb oss_framework/data/oea.duckdb
→ SELECT COUNT(*) FROM raw_students;
→ SELECT COUNT(*) FROM raw_attendance;
```

---

## 📁 Scripts Organization

```
oss_framework/scripts/
├── setup_week1_automated.sh           ← Run FIRST (environment setup)
├── validate_preimplementation.py      ← Run SECOND (validation)
├── run_week1_orchestrator.py          ← Run THIRD (main execution)
│
├── create_stage1_tables.py            ← Created during setup
├── ingest_aeries_data.py              ← Created during setup
├── import_d_and_f_report.py           ← Created during setup
├── import_demographic_data.py         ← Created during setup
├── config.py                          ← Created during setup
├── logging_config.py                  ← Created during setup
├── data_quality.py                    ← Created during setup
│
└── README.md                          ← This file
```

---

## 🔧 Configuration

### Environment Variables (.env)

Create `.env` file in project root:

```bash
cp .env.template .env
# Edit .env with your values
```

**Required variables**:

```bash
# Choose ONE authentication method:

# Option A: API Key (Recommended)
AERIES_AUTH_METHOD=api_key
AERIES_API_KEY=your_key_here

# Option B: OAuth2
AERIES_AUTH_METHOD=oauth2
AERIES_CLIENT_ID=your_id_here
AERIES_CLIENT_SECRET=your_secret_here

# Option C: Database
AERIES_AUTH_METHOD=database
AERIES_DB_HOST=your_server_host
AERIES_DB_DATABASE=aeries_database
```

**Optional variables**:

```bash
DUCKDB_DATABASE_PATH=./oss_framework/data/oea.duckdb
EXCEL_DF_REPORT_PATH=./path/to/d_and_f_report.xlsx
EXCEL_DEMOGRAPHIC_PATH=./path/to/demographic_data.xlsx
EXCEL_RFEP_PATH=./path/to/rfep_data.png
```

---

## 🐛 Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'duckdb'"

**Solution**: Install dependencies
```bash
pip install -r oss_framework/requirements.txt
```

### Issue: "DuckDB: Permission denied"

**Solution**: Fix directory permissions
```bash
chmod 755 oss_framework/data/
```

### Issue: "Aeries API: Rate limit exceeded"

**Solution**: Wait or reduce batch size (built-in backoff handles this)

### Issue: "Excel file not found"

**Solution**: Update .env with correct path
```bash
EXCEL_DF_REPORT_PATH=./oss_framework/docs/tech_docs/Requirements/D\ and\ F\ w_504\ SE.xlsx
```

### Issue: "Configuration validation failed"

**Solution**: Run validation and check error messages
```bash
python oss_framework/scripts/validate_preimplementation.py
```

### Issue: Tests failing during execution

**Solution**: Check DuckDB directly
```bash
duckdb oss_framework/data/oea.duckdb
→ .tables          # List all tables
→ SELECT COUNT(*) FROM raw_students;
→ SELECT * FROM raw_students LIMIT 5;
→ .quit
```

---

## 📊 Expected Results After Week 1-2

### DuckDB Tables Created

```sql
-- Stage 1 Landing Zone
raw_students              (~1,700 rows)
raw_attendance            (~45,000 rows)
raw_academic_records      (~200,000 rows)
raw_discipline            (~2,000 rows)
raw_enrollment            (~35,000 rows)
```

### Data Quality Checks

- ✅ No null student_ids
- ✅ All dates valid
- ✅ Foreign key relationships intact
- ✅ >99% data completeness

### Logs Generated

```
oss_framework/logs/oea.log
├── Configuration validated
├── Stage 1 tables created
├── Students ingested: 1,700 records
├── Attendance ingested: 45,000 records
├── Grades ingested: 200,000 records
├── Discipline ingested: 2,000 records
├── D&F report imported: 456 records
├── Demographic data imported: 1,700 records
└── Data quality: 15/15 tests passed
```

---

## 📈 Performance Expectations

| Operation | Expected Time | Notes |
|-----------|--------------|-------|
| Setup (first time) | 2-3 minutes | Installs 20+ Python packages |
| Validation | 30 seconds | Quick checks, no data processing |
| Create Stage 1 tables | 10 seconds | Just schema creation |
| Ingest Aeries data | 2-5 minutes | Depends on API response time |
| Import Excel reports | 30-60 seconds | Depends on file size |
| Data quality tests | 1-2 minutes | ~15 tests running |
| **Total Week 1-2** | **6-12 minutes** | One-command execution |

---

## ✅ Success Checklist

- [ ] Setup completed without errors
- [ ] Validation passed (0 ❌, all ✅)
- [ ] Orchestrator completed successfully
- [ ] Log file created with detailed output
- [ ] DuckDB contains 5 Stage 1 tables
- [ ] Row counts match expected values
- [ ] Data quality tests all passing
- [ ] No errors in logs

---

## 🚀 Next Phases

Once Week 1-2 is complete:

### Week 3-4: Feature Engineering
```bash
# Build dbt Stage 2 models
cd oss_framework/dbt
dbt build
```

### Week 5-6: Integrated Analysis
```bash
# Create Stage 3 analytics views
# (Scripts provided in next documentation)
```

### Week 7-8: Dashboards
```bash
# Start Metabase and configure dashboards
docker-compose up metabase
# Open http://localhost:3000
```

---

## 📞 Support & Debugging

### View detailed logs
```bash
tail -f oss_framework/logs/oea.log
```

### Run specific module test
```bash
pytest oss_framework/tests/test_stage1_data_quality.py::test_raw_students_not_empty -v
```

### Check DuckDB schema
```bash
duckdb oss_framework/data/oea.duckdb
→ DESCRIBE raw_students;
→ SELECT COUNT(*), COUNT(DISTINCT student_id) FROM raw_attendance;
```

### Check environment
```bash
python oss_framework/scripts/validate_preimplementation.py -v
```

---

## 📚 Related Documentation

- **Overview**: `/NEXT_STEPS.md`
- **Detailed Spec**: `/oss_framework/docs/INTEGRATED_ANALYTICS_FRAMEWORK_DETAILED.md`
- **Quick Reference**: `/oss_framework/docs/QUICK_REFERENCE.md`
- **Clarification Questions**: `/oss_framework/docs/CLARIFICATION_QUESTIONS.md`

---

## 🎯 Ready to Execute?

1. **First time?** Start with setup:
   ```bash
   bash oss_framework/scripts/setup_week1_automated.sh
   ```

2. **Already setup?** Run validation:
   ```bash
   python oss_framework/scripts/validate_preimplementation.py
   ```

3. **Everything good?** Execute Week 1-2:
   ```bash
   python oss_framework/scripts/run_week1_orchestrator.py
   ```

**Estimated total time**: 10-15 minutes from start to finish

---

**Status**: ✅ Scripts ready for Week 1-2 implementation  
**Last Updated**: January 27, 2026

