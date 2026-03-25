# Package Templates Documentation

Complete guide to OEA package templates for education data integration.

---

## Overview

Package templates provide reusable blueprints for integrating different education data sources into the OSS Framework. Each template demonstrates best practices for configuration, data transformation, quality validation, and deployment.

## Available Templates

### 1. **Example SIS Package** (Student Information System)

**Purpose**: Integrate student demographics, enrollment, and academic data from any SIS vendor  
**Data Sources**: PowerSchool, Skyward, Infinite Campus, custom databases  
**Entities**: Students, Courses, Enrollment, Attendance, Academic Records  
**Status**: Production-ready template  

**Location**: `/oss_framework/package_templates/example_sis_package/`

**Files**:
- `README.md` - Package overview and quick start
- `SETUP_GUIDE.md` - Step-by-step installation guide
- `SCHEMAS.md` - Complete data dictionary
- `config/extraction_config.yaml` - SIS connection settings
- `config/transformation_config.yaml` - Field mappings & validation
- `pipelines/` - JSON orchestration templates
- `queries/` - SQL views and analytics
- `notebooks/` - Interactive Marimo notebooks
- `data/sample/` - Sample data files

## Package Structure Template

All packages follow this standard directory layout:

```
package_name/
├── README.md                    Main package documentation
├── SETUP_GUIDE.md               Installation & configuration
├── SCHEMAS.md                   Entity definitions & data dictionary
│
├── config/
│   ├── extraction_config.yaml   Connection to data source
│   ├── transformation_config.yaml Field mappings & validation rules
│   └── README.md                Configuration guide
│
├── pipelines/
│   ├── 00_extract_source.json   Extract from source system
│   ├── 01_land_stage1.json      Load to Stage 1
│   ├── 02_transform_stage2a.json Normalize to Stage 2A
│   ├── 03_refine_stage2b.json   Pseudonymize to Stage 2B
│   ├── 04_aggregate_stage3.json Create Stage 3 views
│   └── README.md                Pipeline documentation
│
├── queries/
│   ├── stage1_validation.sql    Data quality checks
│   ├── stage2a_views.sql        Normalized entity views
│   ├── stage2b_views.sql        Privacy-compliant views
│   ├── stage3_analytics.sql     Analytics & dashboard data
│   └── README.md                Query documentation
│
├── notebooks/
│   ├── 01_data_profiling.py     Explore & analyze data
│   ├── 02_transformation_flow.py Walk through transformations
│   ├── 03_quality_validation.py Validate data quality
│   └── README.md                Notebook guide
│
├── data/
│   ├── sample/
│   │   ├── entity1_sample.csv   Sample data
│   │   └── entity2_sample.csv
│   └── README.md                Sample data info
│
├── tests/
│   ├── test_package.py          Unit & integration tests
│   ├── conftest.py              Pytest fixtures
│   └── README.md                Testing guide
│
├── docs/
│   ├── ARCHITECTURE.md          Data flow diagrams
│   ├── DATA_DICTIONARY.md       Auto-generated reference
│   ├── PRIVACY_RULES.md         Pseudonymization details
│   └── TROUBLESHOOTING.md       Common issues & solutions
│
└── requirements.txt             Python dependencies
```

## Creating a New Package

### Step 1: Use the Template

```bash
# Copy example SIS package
cp -r package_templates/example_sis_package \
      package_templates/my_new_package

cd package_templates/my_new_package
```

### Step 2: Customize for Your Data Source

Edit configuration files:
- `config/extraction_config.yaml` - Your data source details
- `config/transformation_config.yaml` - Your field mappings
- `SCHEMAS.md` - Your entity definitions

### Step 3: Create Sample Data

Place sample extract files in `data/sample/`:
```bash
# Export 100-1000 sample records from your source
my_extract_tool export students > data/sample/students_sample.csv
my_extract_tool export courses > data/sample/courses_sample.csv
```

### Step 4: Update Documentation

- `README.md` - Your package description
- `SETUP_GUIDE.md` - Your specific setup steps
- `docs/ARCHITECTURE.md` - Your data flow
- `docs/DATA_DICTIONARY.md` - Your field descriptions

### Step 5: Test & Validate

```bash
# Run setup guide steps
bash scripts/test_extraction.py --limit 10

# Run quality checks
pytest tests/test_package.py -v

# Explore in notebook
marimo edit notebooks/01_data_profiling.py
```

## Package Configuration

### extraction_config.yaml

Defines how to connect to and extract from the data source:

```yaml
sis:
  system: powerschool              # Vendor name
  host: ${SIS_HOST}                # Use environment variables
  username: ${SIS_USER}
  password: ${SIS_PASSWORD}
  database: pssis
  query: SELECT * FROM Students    # SQL to extract
  batch_date_format: "%Y-%m-%d"

output:
  folder: sis_exports/
  format: csv                      # csv or json
  compression: none

database:
  host: ${DB_HOST}
  database: data_lake
  schemas:
    stage1: stage1
    stage2a: stage2a

batch:
  mode: delta                      # delta, additive, snapshot
  key_columns: [id]               # For matching records
```

### transformation_config.yaml

Defines field mappings, data types, and validation rules:

```yaml
entities:
  students:
    source_table: dbo.Students
    
    # Map source columns to standard schema
    mappings:
      student_id: StudentNumber
      first_name: FirstName
    
    # Pseudonymization rules (Stage 2B)
    pseudonymization:
      student_id: hash             # Hash, mask, or no-op
      first_name: mask
    
    # Validation rules (Stage 2A)
    validation:
      null_check: [student_id]
      unique_check: [student_id]
      range_check:
        grade_level: [0, 16]
```

## Pipeline Templates

Each package includes 5 standard pipeline JSON templates:

### Pipeline 0: Extract Source
Connects to the data source system and exports data to CSV/JSON.

**Input**: Source system configuration  
**Output**: CSV/JSON files in `sis_exports/` folder  
**Example**: PowerSchool → CSV export

### Pipeline 1: Land Stage 1
Organizes extracted data into Stage 1 directory structure with date partitions.

**Input**: `sis_exports/` CSV files  
**Output**: `stage1/` partitioned by date  
**Transformations**: Minimal (preserve raw structure)

### Pipeline 2: Transform Stage 2A
Flattens nested structures, deduplicates, standardizes formats.

**Input**: `stage1/` data  
**Output**: `stage2a/` normalized tables  
**Transformations**: Flatten JSON, deduplicate, type conversion

### Pipeline 3: Refine Stage 2B
Applies pseudonymization rules, creates aggregated views.

**Input**: `stage2a/` data  
**Output**: `stage2b/` privacy-compliant data  
**Transformations**: Hash/mask sensitive fields, aggregate metrics

### Pipeline 4: Aggregate Stage 3
Creates clean, analytics-ready tables with computed features.

**Input**: `stage2b/` data  
**Output**: `stage3/` analytics tables  
**Transformations**: Join entities, compute metrics, create features

## SQL Queries

Pre-built queries for common analytics scenarios:

### stage1_validation.sql
Quality checks on raw data:
```sql
-- Check for required fields
SELECT COUNT(*) as missing_student_ids 
FROM stage1.students 
WHERE student_id IS NULL;

-- Check for duplicates
SELECT student_id, COUNT(*) as count
FROM stage1.students
GROUP BY student_id
HAVING COUNT(*) > 1;
```

### stage2a_views.sql
Normalized entity views:
```sql
-- Flattened student data
CREATE VIEW stage2a.vw_students AS
SELECT 
  student_id,
  first_name,
  grade_level
FROM stage2a.students;
```

### stage2b_views.sql
Privacy-compliant analytics views:
```sql
-- Anonymized student metrics
CREATE VIEW stage2b.vw_student_metrics AS
SELECT 
  hashed_student_id,
  AVG(attendance_rate) as avg_attendance,
  AVG(final_grade) as avg_grade
FROM stage2b.enrollment
GROUP BY hashed_student_id;
```

### stage3_analytics.sql
Dashboard and analytics data:
```sql
-- Ready for dashboards
CREATE TABLE stage3.student_performance AS
SELECT 
  hashed_student_id,
  course_id,
  final_grade,
  attendance_rate,
  engagement_score
FROM stage2b.vw_complete_student_metrics;
```

## Notebooks

Interactive Marimo notebooks for exploration and validation:

### 01_data_profiling.py
Initial data exploration:
- Record counts by entity
- Null value analysis
- Duplicate detection
- Value range analysis
- Data type validation

### 02_transformation_flow.py
Walkthrough of transformation pipeline:
- Extract sample from Stage 1
- Apply each transformation
- Visualize before/after
- Explain business logic

### 03_quality_validation.py
Comprehensive quality checks:
- Run all validation rules
- Generate quality report
- Identify anomalies
- Suggest fixes

## Deployment Options

### Local Development
```bash
python -m oss_framework.orchestrator pipelines/00_extract_sis.json
```

### Scheduled (Cron)
```bash
# Daily at 2 AM
0 2 * * * cd /path/to/package && python -m oss_framework.orchestrator pipelines/master_orchestrator.json
```

### Cloud (Azure Data Factory)
- Use Azure Data Factory copy activity for extraction
- Call Python scripts for transformations
- Store in Azure SQL or Snowflake

### Cloud (AWS)
- Use Lambda + RDS for extraction
- Call Glue jobs for transformations
- Store in Redshift or S3

### Cloud (Snowflake)
- Use Snowflake native connectors for extraction
- Execute SQL transformations directly
- Leverage Snowflake compute

## Best Practices

### 1. Environment Variables
Always use environment variables for sensitive data:
```yaml
host: ${SIS_HOST}
username: ${SIS_USER}
password: ${SIS_PASSWORD}
```

### 2. Configuration Management
Keep configurations in YAML files, not hardcoded:
```python
config = load_yaml('config/extraction_config.yaml')
```

### 3. Data Validation
Implement comprehensive validation:
```yaml
validation:
  null_check: [required_fields]
  unique_check: [id_fields]
  range_check: {grade_level: [0, 16]}
```

### 4. Error Handling
Log errors with context:
```python
except Exception as e:
    logger.error(f"Extraction failed: {e}", extra={'batch_date': batch_date})
    raise
```

### 5. Testing
Create unit and integration tests:
```bash
pytest tests/test_package.py -v --cov
```

## Contributing Templates

To contribute a new package template:

1. Follow the standard structure above
2. Include all documentation files
3. Provide sample data (anonymized)
4. Add comprehensive setup guide
5. Create unit tests
6. Submit pull request with example usage

## Support

- **Documentation**: Check README.md and SETUP_GUIDE.md
- **Issues**: GitHub issues with logs
- **Questions**: Contact OSE Framework team

---

**Last Updated**: January 26, 2026
