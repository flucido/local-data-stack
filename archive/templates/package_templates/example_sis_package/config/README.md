# Package Configuration Guide

This directory contains the configuration files for the SIS package template. Configuration is split into two files: one for data extraction and one for transformation rules.

---

## Configuration Files Overview

### 1. extraction_config.yaml

Defines **how to connect to and extract data** from your Student Information System.

**Use this file to**:
- Specify your SIS vendor (PowerSchool, Skyward, Infinite Campus, etc.)
- Configure connection credentials
- Define extraction SQL queries
- Set output format and destination
- Configure batch mode (delta vs. snapshot)

**Key Sections**:
- `sis`: Source system connection parameters
- `output`: CSV/JSON export settings
- `database`: Target data lake connection
- `batch`: Extraction mode and filtering
- `logging`: Log level and file location

**Customization Checklist**:
- [ ] Set `sis.system` to your vendor
- [ ] Update `sis.host`, `sis.port`, `sis.database`
- [ ] Adjust `sis.query` to match your SIS table names
- [ ] Update `database` credentials for target database
- [ ] Set `batch.mode` (delta for incremental, snapshot for full)
- [ ] Configure `batch.since_date` for delta extractions

---

### 2. transformation_config.yaml

Defines **field mappings, data types, and validation rules** for transforming extracted data.

**Use this file to**:
- Map SIS source columns to standard entity schema
- Specify data types for each field
- Define pseudonymization rules (hash, mask, no-op)
- Implement validation checks (null, unique, range, pattern)
- Set quality thresholds

**Key Sections**:
- `entities`: Per-entity configuration (students, courses, enrollment)
- `mappings`: SIS column → standard schema column
- `type_mappings`: Data type for each field
- `pseudonymization`: Privacy rules (Stage 2B)
- `validation`: Data quality checks (Stage 2A)
- `hash_seed`: Secret key for deterministic hashing
- `quality`: Overall data quality thresholds

**Customization Checklist**:
- [ ] Update `mappings` for each entity with your SIS column names
- [ ] Adjust `type_mappings` if needed
- [ ] Review `pseudonymization` rules for FERPA compliance
- [ ] Modify `validation` rules based on your data quality requirements
- [ ] Change `hash_seed` to a production secret
- [ ] Update `quality` thresholds (null %, duplicates %, min records)

---

## Configuration by SIS Vendor

### PowerSchool

**ODBC Connection**:
```yaml
sis:
  system: powerschool
  host: ps.school.edu
  port: 1433
  driver: mssql+pyodbc
  database: pssis
  username: ${PS_USER}
  password: ${PS_PASSWORD}
```

**Student Query**:
```sql
SELECT 
  STUDENTID as student_id,
  FIRSTNAME as first_name,
  LASTNAME as last_name,
  DATEOFBIRTH as date_of_birth,
  GRADE_LEVEL as grade_level,
  STATUS as enrollment_status,
  LASTUPDATEDATE as _sis_modified_date
FROM STUDENTS
WHERE LASTUPDATEDATE > ?
```

**Field Mappings**:
- Student ID → `STUDENTID`
- First Name → `FIRSTNAME`
- Last Name → `LASTNAME`
- Grade Level → `GRADE_LEVEL`
- Status → `STATUS`
- Modified Date → `LASTUPDATEDATE`

---

### Skyward (formerly Skyward by Jenzabar)

**ODBC Connection**:
```yaml
sis:
  system: skyward
  host: skyward.school.edu
  port: 1433
  driver: mssql+pyodbc
  database: SkywardDB
  username: ${SKY_USER}
  password: ${SKY_PASSWORD}
```

**Student Query**:
```sql
SELECT 
  STU.StudentNumber,
  STU.FirstName,
  STU.LastName,
  STU.BirthDate,
  STU.Grade,
  STU.StatusCode,
  STU.LastChangeDate
FROM STUDENTS STU
WHERE STU.LastChangeDate > ?
```

**Field Mappings**:
- Student ID → `StudentNumber`
- First Name → `FirstName`
- Last Name → `LastName`
- Date of Birth → `BirthDate`
- Grade Level → `Grade`
- Status → `StatusCode`
- Modified Date → `LastChangeDate`

---

### Infinite Campus

**REST API Connection**:
```yaml
sis:
  system: infinite_campus
  host: campus.school.edu
  port: 443
  driver: rest+https
  username: ${IC_USER}
  password: ${IC_PASSWORD}
  
  # REST API endpoint
  query: "/services/v2/students"
```

**Setup**:
```bash
# Install REST driver
pip install requests oauthlib
```

**Field Mappings**:
- Student ID → `studentId`
- First Name → `firstName`
- Last Name → `lastName`
- Date of Birth → `birthDate`
- Grade Level → `gradeLevel`
- Status → `enrollmentStatus`
- Modified Date → `lastModifiedDate`

---

### Generic SQL Server

**ODBC Connection**:
```yaml
sis:
  system: generic_sql
  host: sqlserver.school.edu
  port: 1433
  driver: mssql+pyodbc
  database: studentdata
  username: ${SQL_USER}
  password: ${SQL_PASSWORD}
```

**Student Query**:
```sql
SELECT 
  student_number,
  first_name,
  last_name,
  birth_date,
  grade_level,
  enrollment_status,
  modified_timestamp
FROM students
WHERE modified_timestamp > ?
```

---

## Environment Variables

For security, always use environment variables for credentials:

```bash
# Set before running pipeline
export SIS_HOST="ps.school.edu"
export SIS_USER="svc_extract"
export SIS_PASSWORD="your-secure-password"
export DB_HOST="datalake.database.windows.net"
export DB_USER="datalake_user"
export DB_PASSWORD="your-datalake-password"
```

Or add to `.env` file (not git-tracked):

```
# .env (DO NOT COMMIT)
SIS_HOST=ps.school.edu
SIS_USER=svc_extract
SIS_PASSWORD=your-secure-password
DB_HOST=datalake.database.windows.net
DB_USER=datalake_user
DB_PASSWORD=your-datalake-password
```

Then load in Python:
```python
from dotenv import load_dotenv
import os

load_dotenv()
sis_host = os.getenv('SIS_HOST')
```

---

## Batch Mode Options

### Delta Mode (Incremental)

Extract only records modified since last run:

```yaml
batch:
  mode: delta
  key_columns: [student_id]
  batch_date_column: _sis_modified_date
  since_date: yesterday
```

**Pros**:
- Faster (fewer records to process)
- Efficient network usage
- Suitable for daily incremental runs

**Cons**:
- Requires reliable timestamp column
- Complex deduplication logic

**When to use**: Production daily/hourly extractions

---

### Additive Mode (Append)

Append all extracted records to existing data:

```yaml
batch:
  mode: additive
  batch_date_column: _load_timestamp
```

**Pros**:
- Simple - no deduplication needed
- Preserves historical snapshots

**Cons**:
- Large data volume
- Requires explicit deduplication in transformation

**When to use**: Initial loads, weekly full extracts

---

### Snapshot Mode (Replace)

Replace entire table with fresh extract:

```yaml
batch:
  mode: snapshot
```

**Pros**:
- Simplest to understand
- Always consistent

**Cons**:
- Requires re-processing entire dataset
- No historical tracking

**When to use**: Small reference tables, weekly refreshes

---

## Field Mapping Examples

### Standard Student Fields

```yaml
mappings:
  student_id: StudentNumber       # Primary identifier
  first_name: FirstName           # PII
  last_name: LastName
  middle_name: MiddleName
  date_of_birth: BirthDate        # PII
  gender: Gender
  ethnicity: Ethnicity
  grade_level: Grade
  enrollment_status: Status
```

### Contact Information

```yaml
mappings:
  phone_number: Phone
  email_address: Email
  address_line1: Address1
  address_city: City
  address_state: State
  address_zip: ZipCode
```

### Demographic Flags

```yaml
mappings:
  special_education: SPEDStatus
  english_learner: ELStatus
  economically_disadvantaged: EconomicStatus
  homeless_status: HomelessFlag
  foster_care_status: FosterCareFlag
  military_family: MilitaryConnected
```

---

## Pseudonymization Rules

Applied at Stage 2B → 3 transition. Three options:

### 1. Hash (Deterministic)

```yaml
pseudonymization:
  student_id: hash
```

- Converts `student_id` to a consistent hash
- Same input always produces same hash
- Allows authorized users to link records
- Cannot reverse to get original value
- Use for: IDs that must be linkable

### 2. Mask (Irreversible)

```yaml
pseudonymization:
  first_name: mask
```

- Replaces value with masked placeholder (e.g., "First 3 chars + ***")
- Cannot reverse or link records
- Completely anonymous
- Use for: Names, addresses, contact info

### 3. No-op (No Operation)

```yaml
pseudonymization:
  grade_level: no-op
```

- Keeps value unchanged
- Use for: Non-sensitive fields (grades, codes, status)

---

## Data Validation Rules

Applied at Stage 2A. Multiple validation types:

### Null Check

```yaml
validation:
  null_check:
    - student_id      # Cannot be null
    - first_name
    - last_name
```

Fails transformation if these fields contain NULLs.

### Unique Check

```yaml
validation:
  unique_check:
    - student_id      # Must be unique
    - course_id
```

Fails if duplicates detected.

### Range Check

```yaml
validation:
  range_check:
    grade_level: [0, 16]      # 0-16 only
    gpa: [0.0, 4.0]
```

Fails if values outside range.

### Pattern Check

```yaml
validation:
  pattern_check:
    student_id: '^[A-Z0-9]{5,10}$'   # Alphanumeric, 5-10 chars
    email: '^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
```

Fails if pattern doesn't match.

### SQL Check

```yaml
validation:
  sql_check: |
    SELECT student_id FROM stage2a.students 
    WHERE grade_level < 0 OR grade_level > 16
```

Fails if query returns rows (custom validation logic).

---

## Quality Thresholds

```yaml
quality:
  max_null_percent: 0.05           # Max 5% null values
  max_duplicate_percent: 0.01      # Max 1% duplicates
  min_record_count: 100             # Fail if < 100 records
  max_error_percent: 0.02           # Fail if > 2% validation errors
```

**Adjust based on your data quality**:
- Lenient: `0.10` (10%)
- Standard: `0.05` (5%)
- Strict: `0.01` (1%)

---

## Configuration Workflow

### Step 1: Understand Your SIS

- Identify which table contains which entity (students, courses, enrollment)
- Find column names for each field
- Check for timestamp columns (for delta extraction)
- Test data access with sample queries

### Step 2: Update extraction_config.yaml

```yaml
sis:
  system: powerschool              # Your vendor
  host: ${SIS_HOST}
  username: ${SIS_USER}
  password: ${SIS_PASSWORD}
  database: pssis
  query: SELECT ...                # Your extraction query
  
batch:
  mode: delta
  batch_date_column: LastModified  # Your timestamp column
```

### Step 3: Update transformation_config.yaml

```yaml
entities:
  students:
    source_table: dbo.Students     # Your table name
    mappings:
      student_id: StudentID         # Map to your columns
      first_name: FirstName
      # ... etc
```

### Step 4: Test Configuration

```bash
# Run extraction with limit
python -m oss_framework.orchestrator \
  pipelines/00_extract_sis.json \
  --limit 100 \
  --dry-run

# Check output
head -5 sis_exports/students.csv
```

### Step 5: Validate & Deploy

```bash
# Run full extraction
python -m oss_framework.orchestrator pipelines/00_extract_sis.json

# Run validation notebook
marimo edit notebooks/03_quality_validation.py

# If valid, proceed with transformation
python -m oss_framework.orchestrator pipelines/01_land_stage1.json
```

---

## Troubleshooting Configuration Issues

### Issue: "Cannot connect to SIS"

**Check**:
- `sis.host` and `sis.port` are correct
- Credentials in environment variables are set
- Network firewall allows connection
- SIS system is running

**Solution**:
```bash
# Test connection
python -c "
import pyodbc
conn = pyodbc.connect(
  f'Driver={{ODBC Driver 17 for SQL Server}};'
  f'Server={os.getenv(\"SIS_HOST\")};'
  f'Database=pssis;'
  f'UID={os.getenv(\"SIS_USER\")};'
  f'PWD={os.getenv(\"SIS_PASSWORD\")}'
)
print('Connected!')
"
```

### Issue: "Column not found in source"

**Check**:
- SIS table name is correct
- Column names match actual SIS schema
- Case sensitivity (e.g., StudentID vs studentid)

**Solution**:
```bash
# List actual columns in SIS
sqlcmd -S ${SIS_HOST} -U ${SIS_USER} -P ${SIS_PASSWORD} -d pssis \
  -Q "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='Students'"
```

### Issue: "Hash seed mismatch between runs"

**Check**:
- `hash_seed` in transformation_config.yaml is consistent
- All pipeline runs use same config file

**Solution**:
```yaml
# Use a stable, production secret
hash_seed: "your-organization-stable-seed-v1"  # Change only for re-hashing
```

---

## Security Best Practices

1. **Never commit credentials** to git
   ```bash
   # Add to .gitignore
   echo "extraction_config.yaml" >> .gitignore
   echo ".env" >> .gitignore
   ```

2. **Use environment variables** for all secrets
   ```yaml
   username: ${SIS_USER}           # Not: username: actual_user
   password: ${SIS_PASSWORD}
   ```

3. **Rotate credentials regularly**
   ```bash
   # Update every 90 days in production
   export SIS_PASSWORD="new-secure-password"
   ```

4. **Audit access logs**
   ```bash
   # Check who extracted data
   grep "extraction" logs/transformation.log
   ```

5. **Encrypt data in transit**
   ```yaml
   sis:
     ssl: true                      # HTTPS for REST APIs
     verify_certificate: true
   ```

---

## Reference

For more information:

- **Extraction Guide**: See `extraction_config.yaml` inline comments
- **Transformation Guide**: See `transformation_config.yaml` inline comments
- **Schema Reference**: See `SCHEMAS.md`
- **Setup Instructions**: See `SETUP_GUIDE.md`
- **Troubleshooting**: See `docs/TROUBLESHOOTING.md`

---

**Last Updated**: January 26, 2026  
**Maintainer**: OSE Framework Team
