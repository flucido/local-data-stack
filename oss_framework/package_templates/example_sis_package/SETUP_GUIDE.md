# SIS Package Setup Guide

## Installation & Configuration

Complete step-by-step guide for setting up the SIS data package.

---

## Prerequisites

### System Requirements
- **OS**: Linux, macOS, or Windows
- **Python**: 3.8 or higher
- **Database**: PostgreSQL 12+, Snowflake, or Azure SQL
- **Storage**: 500MB+ available disk space
- **Network**: Access to SIS system and database

### Software Requirements
```bash
pip install python>=3.8
pip install pandas>=1.5.0
pip install sqlalchemy>=1.4.0
pip install pyyaml>=6.0
```

### Access Requirements
- SIS system credentials with read access
- Database user with CREATE/WRITE permissions
- For cloud (Azure): Storage account and credentials

---

## Step 1: Package Installation

### Option A: From Git Repository

```bash
# Clone the framework
git clone https://github.com/your-org/oss_framework.git
cd oss_framework

# Install core utilities
cd utilities
pip install -e .

# Navigate to package
cd ../package_templates/example_sis_package
```

### Option B: From Local Directory

```bash
# If you have a local copy
cd /path/to/example_sis_package
```

---

## Step 2: Configure SIS Connection

### 1. Create Configuration File

```bash
# Copy template
cp config/extraction_config.yaml.example config/extraction_config.yaml

# Edit with your credentials
nano config/extraction_config.yaml  # or use your editor
```

### 2. Configure for Your SIS Vendor

#### PowerSchool

```yaml
sis:
  system: powerschool
  host: powerschool.school.edu
  username: ${PS_USERNAME}           # Use env variables
  password: ${PS_PASSWORD}
  database: pssis
  port: 1433
  query: |
    SELECT 
      STUDENTID, 
      FIRSTNAME, 
      LASTNAME, 
      DOB,
      CURRENT_STATUS,
      GRADE_LEVEL
    FROM STUDENTS
    WHERE LASTUPDATEDATE > ?
  batch_date_format: "%Y-%m-%d"
```

#### Skyward

```yaml
sis:
  system: skyward
  host: skyward.school.edu
  username: ${SKY_USERNAME}
  password: ${SKY_PASSWORD}
  database: skywarddb
  port: 5432                         # Skyward uses PostgreSQL
  query: |
    SELECT 
      STUDENTID, 
      FIRSTNAME, 
      LASTNAME,
      DOB,
      ENROLLMENT_STATUS,
      GRADELEVEL
    FROM STUDENT
    WHERE MODIFYDATE > ?
  batch_date_format: "%Y-%m-%d %H:%M:%S"
```

#### Generic SQL Server

```yaml
sis:
  system: generic
  driver: mssql+pyodbc
  host: sqlserver.school.edu
  username: ${SIS_USER}
  password: ${SIS_PASSWORD}
  database: student_data
  port: 1433
  query: SELECT * FROM dbo.Students WHERE LastModified > ?
```

### 3. Set Environment Variables

```bash
# Linux/macOS
export SIS_USER="your_username"
export SIS_PASSWORD="your_password"
export DB_HOST="your_db_host"
export DB_USER="db_username"
export DB_PASSWORD="db_password"

# Windows (PowerShell)
$env:SIS_USER = "your_username"
$env:SIS_PASSWORD = "your_password"
$env:DB_HOST = "your_db_host"
$env:DB_USER = "db_username"
$env:DB_PASSWORD = "db_password"
```

---

## Step 3: Configure Data Transformation

### 1. Field Mappings

Edit `config/transformation_config.yaml`:

```yaml
entities:
  students:
    source_table: dbo.Students      # Your SIS table name
    target_table: stage2a.students
    
    # Map SIS columns to standard schema
    mappings:
      student_id: StudentNumber     # SIS_COLUMN: standard_column
      first_name: FirstName
      last_name: LastName
      middle_name: MiddleName
      date_of_birth: BirthDate
      gender: Gender
      grade_level: GradeLevel
      school_id: SchoolCode
      enrollment_status: Status
      english_learner: ELStatus
      special_education: SPEDStatus
      economically_disadvantaged: EconomicDisadvantaged
      
    # Define data type conversions
    type_mappings:
      date_of_birth: DATE
      grade_level: INT
      enrollment_status: VARCHAR(50)
      
    # Pseudonymization rules (Stage 2B)
    pseudonymization:
      student_id: hash               # hash, mask, or no-op
      first_name: mask
      last_name: mask
      middle_name: mask
      date_of_birth: hash
      gender: no-op                  # Non-sensitive
      grade_level: no-op
      
    # Data validation rules
    validation:
      null_check: [student_id, first_name, last_name]
      unique_check: [student_id]
      range_check:
        grade_level: [0, 16]
      pattern_check:
        student_id: ^[A-Z0-9]{5,10}$
```

### 2. Batch Mode Configuration

```yaml
batch:
  mode: delta                        # delta, additive, or snapshot
  key_columns: [student_id]          # How to match existing records
  batch_date_column: LASTUPDATEDATE # Timestamp column for delta
  
  # For delta mode: only load records modified since last run
  # For additive mode: append all new records
  # For snapshot mode: replace entire table
```

---

## Step 4: Install Dependencies

```bash
# Install Python requirements
pip install -r requirements.txt

# Verify installation
python -c "import oss_framework; print('Installation successful!')"
```

### Requirements.txt

```
# Data processing
pandas>=1.5.0
numpy>=1.23.0

# Database
sqlalchemy>=1.4.0
pyodbc>=4.0.0              # For SQL Server
psycopg2-binary>=2.9.0     # For PostgreSQL
snowflake-sqlalchemy>=1.4.0 # For Snowflake

# Configuration & utilities
pyyaml>=6.0
python-dotenv>=0.19.0

# Testing & quality
pytest>=7.0
pytest-cov>=4.0
```

---

## Step 5: Test Configuration

### Run Connection Test

```bash
# Test SIS connection
python -c "from sis_package import extractor; extractor.test_connection()"
```

### Run Sample Extraction

```bash
# Extract small sample (10 records)
python scripts/test_extraction.py --limit 10

# Check output
head data/sample/students_sample.csv
```

### Validate Mapping

```bash
# Test field mapping configuration
python scripts/validate_mapping.py config/transformation_config.yaml
```

---

## Step 6: Run Full Pipeline

### Option A: Sequential Execution

```bash
# Run each stage in order
python -m oss_framework.orchestrator pipelines/00_extract_sis.json
python -m oss_framework.orchestrator pipelines/01_land_stage1.json
python -m oss_framework.orchestrator pipelines/02_transform_stage2a.json
python -m oss_framework.orchestrator pipelines/03_refine_stage2b.json
python -m oss_framework.orchestrator pipelines/04_aggregate_stage3.json
```

### Option B: All-in-One

```bash
# Run complete pipeline (master orchestrator)
python -m oss_framework.orchestrator pipelines/master_orchestrator.json
```

### Option C: With Parameters

```bash
# Override default parameters
python -m oss_framework.orchestrator \
  pipelines/00_extract_sis.json \
  --batch_mode=snapshot \
  --min_records=1000 \
  --env_vars="SIS_USER=$SIS_USER,SIS_PASSWORD=$SIS_PASSWORD"
```

---

## Step 7: Validate Results

### Run Data Quality Checks

```bash
# Comprehensive validation
pytest tests/test_sis_package.py -v

# Specific test
pytest tests/test_sis_package.py::TestDataQuality::test_null_values -v
```

### Run Interactive Validation Notebook

```bash
# Open data profiling notebook
marimo edit notebooks/01_data_profiling.py

# Run transformation walkthrough
marimo edit notebooks/02_transformation_flow.py

# Run quality validation
marimo edit notebooks/03_quality_validation.py
```

### Quick SQL Validation

```bash
# Connect to database
psql -h $DB_HOST -U $DB_USER -d $DB_NAME

# Check Stage 1 record count
SELECT COUNT(*) FROM stage1.students;

# Check Stage 2A transformations
SELECT COUNT(*) FROM stage2a.students;

# Check Stage 2B anonymization (sample)
SELECT hashed_student_id, grade_level FROM stage2b.students LIMIT 10;

# Check Stage 3 aggregations
SELECT COUNT(*), AVG(attendance_rate) FROM stage3.student_metrics;
```

---

## Step 8: Schedule for Production

### Create Cron Job (Linux/macOS)

```bash
# Edit crontab
crontab -e

# Daily extraction at 2 AM
0 2 * * * cd /path/to/sis_package && python -m oss_framework.orchestrator pipelines/master_orchestrator.json

# Weekly snapshot every Sunday at 1 AM
0 1 * * 0 cd /path/to/sis_package && python -m oss_framework.orchestrator pipelines/master_orchestrator.json --batch_mode=snapshot
```

### Create Scheduled Task (Windows)

```powershell
# Create task that runs daily at 2 AM
$trigger = New-ScheduledTaskTrigger -Daily -At 2am
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-ExecutionPolicy Bypass -File 'C:\path\to\run_pipeline.ps1'"
Register-ScheduledTask -TaskName "SIS-Daily-Extract" -Trigger $trigger -Action $action
```

### Cloud Orchestration (Azure Data Factory / Airflow)

See `docs/ARCHITECTURE.md` for cloud deployment options.

---

## Troubleshooting

### Issue: "Cannot connect to SIS system"

**Check**:
1. SIS host is accessible: `ping $SIS_HOST`
2. Credentials are correct: Try login manually
3. Firewall rules allow database port
4. VPN/proxy settings if required

**Solution**:
```bash
# Test connection directly
python scripts/test_connection.py config/extraction_config.yaml
```

### Issue: "Field mapping errors"

**Check**:
1. Column names match your SIS exactly (case-sensitive)
2. Data types are compatible
3. Null values handled appropriately

**Solution**:
```bash
# Validate mapping
python scripts/validate_mapping.py config/transformation_config.yaml

# Compare SIS schema to expected
python scripts/compare_schemas.py
```

### Issue: "Pseudonymization hash mismatch"

**Cause**: Different hash seed between pipeline runs

**Solution**:
```yaml
# In transformation_config.yaml, ensure consistent seed
hash_seed: "your-stable-secret-key"  # Same across all runs
```

### Issue: "Out of memory during transformation"

**Cause**: Processing too many records at once

**Solution**:
```yaml
batch:
  mode: delta                # Process only new/modified records
  chunk_size: 10000          # Process in smaller batches
  compression: gzip          # Compress intermediate files
```

---

## Next Steps

1. **Data Exploration**: Run `notebooks/01_data_profiling.py`
2. **Transformation Review**: Open `notebooks/02_transformation_flow.py`
3. **Quality Validation**: Execute `notebooks/03_quality_validation.py`
4. **Create Custom Queries**: Add to `queries/` for your use cases
5. **Build Dashboards**: Connect to Stage 3 for analytics

---

## Support

- **Documentation**: See README.md and docs/ folder
- **Examples**: Check notebooks/ for working examples
- **Issues**: Create issue in GitHub with logs from pipeline execution
- **Questions**: Contact OSE Framework team

---

**Last Updated**: January 26, 2026
