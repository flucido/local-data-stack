# OEA SIS Package Template

**Version**: 1.0  
**Description**: Student Information System (SIS) data package for Open Education Analytics  
**Data Source**: Student Information System (any vendor: Powerschool, Skyward, etc.)  
**Scope**: K-12 student demographics, enrollment, and academic data

---

## Overview

This package provides a complete template for ingesting Student Information System (SIS) data into the OSS Framework education data lake. It demonstrates best practices for:

- Data source connection and extraction
- Multi-stage data transformation (Stage 1 → 2A → 2B → 3)
- Privacy-compliant pseudonymization
- Quality validation and error handling
- Documentation and metadata management

## Package Structure

```
example_sis_package/
├── README.md                    (This file)
├── SETUP_GUIDE.md               (Installation & configuration)
├── SCHEMAS.md                   (Data schema documentation)
│
├── pipelines/
│   ├── 00_extract_sis.json      (Extract from SIS system)
│   ├── 01_land_stage1.json      (Load to Stage 1)
│   ├── 02_transform_stage2a.json (Flatten & normalize)
│   ├── 03_refine_stage2b.json   (Pseudonymize & aggregate)
│   └── 04_aggregate_stage3.json  (Create analytics tables)
│
├── queries/
│   ├── stage1_validation.sql    (Data quality checks)
│   ├── stage2a_views.sql        (Flattened entity views)
│   ├── stage2b_views.sql        (Privacy-compliant views)
│   ├── stage3_analytics.sql     (Analytics & dashboards)
│   └── README.md                (Query documentation)
│
├── notebooks/
│   ├── 01_data_profiling.py     (Initial data exploration)
│   ├── 02_transformation_flow.py (Data pipeline walkthrough)
│   ├── 03_quality_validation.py  (Validation checks)
│   └── README.md                (Notebook guide)
│
├── data/
│   ├── sample/
│   │   ├── students_sample.csv  (Sample student data)
│   │   ├── courses_sample.csv   (Sample course data)
│   │   └── enrollment_sample.csv (Sample enrollment data)
│   └── README.md                (Sample data documentation)
│
├── docs/
│   ├── ARCHITECTURE.md          (Package architecture)
│   ├── DATA_DICTIONARY.md       (Field definitions)
│   ├── PRIVACY_RULES.md         (Pseudonymization rules)
│   └── TROUBLESHOOTING.md       (Common issues & solutions)
│
└── config/
    ├── extraction_config.yaml   (SIS connection parameters)
    ├── transformation_config.yaml (Data mapping rules)
    └── README.md                (Configuration guide)
```

## Quick Start

### 1. Prerequisites

- Access to SIS system with extract capability
- Python 3.8+ with OSS Framework installed
- SQL database (PostgreSQL, Snowflake, or Azure SQL)
- ~500MB disk space for sample data processing

### 2. Installation

```bash
# Clone or download the package
git clone <repo> && cd example_sis_package

# Install dependencies
pip install -r requirements.txt

# Configure your SIS connection
cp config/extraction_config.yaml.example config/extraction_config.yaml
# Edit with your SIS credentials and database details
```

### 3. Run the Pipeline

```bash
# Extract data from SIS
python -m oss_framework.orchestrator pipelines/00_extract_sis.json

# Transform through each stage
python -m oss_framework.orchestrator pipelines/01_land_stage1.json
python -m oss_framework.orchestrator pipelines/02_transform_stage2a.json
python -m oss_framework.orchestrator pipelines/03_refine_stage2b.json
python -m oss_framework.orchestrator pipelines/04_aggregate_stage3.json
```

### 4. Validate Results

```bash
# Run quality checks
pytest tests/test_sis_package.py

# Explore in notebook
marimo edit notebooks/01_data_profiling.py
```

## Data Flow

```
SIS System
    ↓
[00_extract_sis.json]  (CSV/JSON export from SIS)
    ↓
Stage 1 (Raw)          [01_land_stage1.json]
- Date partitions
- Directory structure
- Minimal transformation
    ↓
Stage 2A (Normalized)  [02_transform_stage2a.json]
- Flattened structures
- Deduplicated records
- Standardized formats
    ↓
Stage 2B (Refined)     [03_refine_stage2b.json]
- Pseudonymized IDs (student, teacher)
- Aggregated metrics
- Privacy-compliant views
    ↓
Stage 3 (Analytics)    [04_aggregate_stage3.json]
- Clean, ready-to-use tables
- Computed features
- Joined entities
    ↓
Dashboards & Notebooks
```

## Entities & Attributes

### Core Entities (from OSS Framework metadata)

| Entity | Attributes | Stage | Purpose |
|--------|-----------|-------|---------|
| **students** | 27 | 1 → 2A → 2B | Demographic data, enrollment status |
| **courses** | 18 | 1 → 2A → 2B | Course catalog, scheduling |
| **enrollment** | 23 | 1 → 2A → 2B | Student-course relationships, grades |
| **attendance** | 21 | 1 → 2A → 2B | Daily attendance, absence patterns |
| **academic_records** | 24 | 1 → 2A → 2B | Assignment grades, assessments |

**Total**: 113 attributes across 5 core entities

For complete attribute definitions, see `docs/DATA_DICTIONARY.md` or `SCHEMAS.md`.

## Privacy & Compliance

### Pseudonymization Rules

This package implements FERPA-compliant data handling:

- **Hash**: student_id, teacher_id, date_of_birth (deterministic, linkable for authorized users)
- **Mask**: names, contact info, addresses (irreversible)
- **No-op**: grades, demographics, engagement (non-sensitive)

Applied at Stage 2B → 3 transition.

### Configuration

Privacy rules are defined in `config/transformation_config.yaml` and applied automatically during pipeline execution.

See `docs/PRIVACY_RULES.md` for detailed rationale.

## Pipeline Parameters

Each pipeline supports dynamic parameters for flexibility:

### Common Parameters

```json
{
  "source_folder": "sis_exports/",
  "destination_container": "datalake/",
  "stage": "stage2a",
  "batch_mode": "delta",
  "hash_seed": "your-secret-key",
  "min_records": 100,
  "max_errors": 0.05
}
```

See `docs/ARCHITECTURE.md` for complete parameter reference.

## Queries & Views

Pre-built SQL queries for common analytics:

### Stage 2B Views (Privacy-compliant)
```sql
-- Anonymized student enrollment
SELECT 
  hashed_student_id,
  course_id,
  final_grade,
  attendance_rate
FROM stage2b.enrollments
WHERE school_id = 'SCH001';

-- Course engagement metrics
SELECT 
  course_id,
  COUNT(DISTINCT hashed_student_id) as student_count,
  AVG(engagement_score) as avg_engagement
FROM stage2b.engagement_summary
GROUP BY course_id;
```

See `queries/` directory for complete query library.

## Notebooks

Interactive Marimo notebooks for exploration and validation:

- **01_data_profiling.py**: Initial data exploration and anomaly detection
- **02_transformation_flow.py**: Step-by-step pipeline walkthrough
- **03_quality_validation.py**: Comprehensive data quality checks

Run with: `marimo edit notebooks/01_data_profiling.py`

## Configuration

### extraction_config.yaml

```yaml
sis:
  system: powerschool          # Vendor (powerschool, skyward, etc.)
  host: sis.school.edu
  username: ${SIS_USER}        # Use environment variables
  password: ${SIS_PASSWORD}
  database: sisdata
  query: SELECT * FROM dbo.Students WHERE ModifyDate > ?
  
output:
  format: csv                  # csv or json
  delimiter: ","
  encoding: utf-8
  
batch:
  mode: delta                  # delta, additive, or snapshot
  key_columns: [student_id]
  batch_date: '${BATCH_DATE}'  # Injected at runtime
```

### transformation_config.yaml

```yaml
entities:
  students:
    source_table: dbo.Students
    mappings:
      student_id: StudentNumber
      first_name: FirstName
      last_name: LastName
    pseudonymization:
      student_id: hash
      first_name: mask
      last_name: mask
      
validation:
  null_check: [student_id, first_name]
  unique_check: [student_id]
  range_check:
    grade_level: [0, 16]
```

## Testing

Run the test suite:

```bash
# Run all tests
pytest tests/ -v

# Run specific test
pytest tests/test_sis_package.py::TestSISExtraction -v

# With coverage
pytest tests/ --cov=sis_package --cov-report=html
```

## Troubleshooting

Common issues and solutions:

### Issue: "Connection refused to SIS system"
**Solution**: Check `extraction_config.yaml` credentials and network access.

### Issue: "Hash mismatch in Stage 2B"
**Solution**: Verify `hash_seed` is consistent across pipeline runs.

### Issue: "Grade values out of range"
**Solution**: Run `notebooks/03_quality_validation.py` to identify invalid records.

See `docs/TROUBLESHOOTING.md` for more details.

## Support & Documentation

- **Getting Started**: See `SETUP_GUIDE.md`
- **Data Schemas**: See `SCHEMAS.md` and `docs/DATA_DICTIONARY.md`
- **Architecture**: See `docs/ARCHITECTURE.md`
- **Privacy**: See `docs/PRIVACY_RULES.md`
- **Queries**: See `queries/README.md`
- **Notebooks**: See `notebooks/README.md`

## Contributing

To customize this package for your SIS:

1. Modify `config/extraction_config.yaml` with your SIS details
2. Update field mappings in `config/transformation_config.yaml`
3. Adjust `pipelines/` JSON templates as needed
4. Run `notebooks/01_data_profiling.py` to validate extraction
5. Update `docs/` with your specific implementation

## License

This package template is part of the Open Source Education (OSE) Framework. See LICENSE file for details.

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Jan 2026 | Initial SIS package template |

---

**Last Updated**: January 26, 2026  
**Maintainer**: OSE Framework Team  
**Status**: Template - Ready to customize for your SIS system
