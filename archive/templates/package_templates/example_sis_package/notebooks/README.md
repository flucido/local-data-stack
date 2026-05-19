# Interactive Notebooks Guide

This directory contains interactive Marimo notebooks for exploring, validating, and understanding the SIS package data pipeline.

## Notebooks Overview

### 1. **00_package_setup.py** - Setup & Configuration

**Time**: ~15 minutes  
**Purpose**: Configure the package for your SIS system

**What you'll learn**:
- How to customize `extraction_config.yaml` for your SIS vendor
- How to map fields from your SIS to standard schema
- How to set up environment variables for secure credential handling
- How to choose the right batch mode (delta/additive/snapshot)
- How to understand FERPA-compliant privacy rules

**Topics covered**:
- SIS system identification (PowerSchool, Skyward, Infinite Campus, generic SQL)
- Connection parameters for each vendor
- Field mapping examples by vendor
- Environment variable setup for security
- Batch mode comparison (delta vs. additive vs. snapshot)
- Privacy rule explanation (hash, mask, no-op)
- Configuration validation checklist

**Next**: Run `01_data_profiling.py` after completing setup

---

### 2. **01_data_profiling.py** - Data Exploration

**Time**: ~20 minutes  
**Purpose**: Explore extracted raw SIS data

**What you'll learn**:
- How to load extracted CSV/JSON files
- How to identify null values and missing data
- How to detect duplicate records
- How to analyze numeric and text fields
- How to find data anomalies
- How to generate a data profiling report

**Topics covered**:
- Loading data from extraction folder
- Entity-by-entity summary statistics
- Column analysis (type, uniqueness, null %)
- Numeric field statistics (mean, min, max, std)
- Text field analysis (length, top values)
- Anomaly detection (all-null columns, constant values, duplicates)
- Sample record viewing

**Output**: Data profiling report showing data quality baseline

**Next**: Run `02_transformation_flow.py` to understand transformations

---

### 3. **02_transformation_flow.py** - Pipeline Walkthrough

**Time**: ~25 minutes  
**Purpose**: Understand how data transforms through each stage

**What you'll learn**:
- How Stage 1 preserves raw data
- How Stage 2A normalizes and validates data
- How Stage 2B applies pseudonymization
- How Stage 3 creates analytics tables
- What happens at each transformation step

**Topics covered**:
- Field mapping walkthrough (SIS columns → standard schema)
- Type conversion (strings to dates, numbers, booleans)
- Data validation rules at Stage 2A
- Pseudonymization strategies (hash vs. mask vs. no-op)
- FERPA compliance explanation
- Aggregation and feature engineering at Stage 3
- Complete data flow visualization
- Validation rules by entity

**Output**: Visual understanding of complete transformation pipeline

**Next**: Run `03_quality_validation.py` to check data quality

---

### 4. **03_quality_validation.py** - Quality Checks

**Time**: ~20 minutes  
**Purpose**: Validate transformed data against quality rules

**What you'll learn**:
- How to run null value checks
- How to verify unique constraints
- How to validate numeric ranges
- How to detect outliers and anomalies
- How to generate quality scores
- How to identify needed fixes

**Topics covered**:
- Null value validation per field
- Unique constraint checking for IDs
- Range validation for numeric fields
- Pattern validation (email, phone, etc.)
- Duplicate detection
- Quality threshold comparison
- Field-by-field quality metrics
- Anomaly detection (constant columns, outliers)
- Recommendations for issues found

**Output**: Data quality report with issues and recommendations

**Next**: Run `04_stage_comparison.py` to verify transformations

---

### 5. **04_stage_comparison.py** - Stage Validation

**Time**: ~20 minutes  
**Purpose**: Compare data across stages to verify transformations

**What you'll learn**:
- How to verify field mappings Stage 1→2A
- How to confirm pseudonymization Stage 2A→2B
- How to validate aggregations Stage 2B→3
- How to check record counts consistency
- How to verify data types were converted correctly
- How to confirm FERPA compliance

**Topics covered**:
- Stage 1 vs. Stage 2A field comparison
- Stage 2A vs. Stage 2B pseudonymization verification
- Stage 2B vs. Stage 3 aggregation comparison
- Record count progression
- Data type transformations
- Privacy compliance verification
- Quality metrics across stages
- Transformation validation summary

**Output**: Confirmation that all stages completed correctly

---

## Running the Notebooks

### Prerequisites

Install Marimo (interactive notebook framework):
```bash
pip install marimo
```

### Start a Notebook

```bash
marimo edit notebooks/00_package_setup.py
```

Or run all notebooks:
```bash
marimo run notebooks/00_package_setup.py
marimo run notebooks/01_data_profiling.py
marimo run notebooks/02_transformation_flow.py
marimo run notebooks/03_quality_validation.py
marimo run notebooks/04_stage_comparison.py
```

### Recommended Workflow

Follow this sequence for best understanding:

1. **First time setup**:
   ```bash
   marimo edit notebooks/00_package_setup.py    # Configure your SIS
   python -m oss_framework.orchestrator pipelines/00_extract_sis.json
   ```

2. **Explore extracted data**:
   ```bash
   marimo edit notebooks/01_data_profiling.py   # Understand raw data
   ```

3. **Understand transformations**:
   ```bash
   marimo edit notebooks/02_transformation_flow.py  # Learn pipeline
   ```

4. **Run full pipeline**:
   ```bash
   python -m oss_framework.orchestrator pipelines/01_land_stage1.json
   python -m oss_framework.orchestrator pipelines/02_transform_stage2a.json
   python -m oss_framework.orchestrator pipelines/03_refine_stage2b.json
   python -m oss_framework.orchestrator pipelines/04_aggregate_stage3.json
   ```

5. **Validate quality**:
   ```bash
   marimo edit notebooks/03_quality_validation.py  # Check data quality
   ```

6. **Verify stages**:
   ```bash
   marimo edit notebooks/04_stage_comparison.py    # Confirm transformations
   ```

---

## Key Features

### Interactive Widgets

All notebooks use Marimo's reactive cells:
- **Dropdowns**: Select SIS vendor, batch mode, etc.
- **DataFrames**: View and sort data tables
- **Status indicators**: ✓ PASS, ⚠️ FAIL, ℹ️ INFO

### Real-time Reactivity

- Change a dropdown and all dependent cells update instantly
- Run validation and see results immediately
- No need to re-run entire notebook

### Exportable Reports

From Marimo UI:
- **Export as PDF**: For stakeholder reports
- **Export as HTML**: Share via email
- **Share link**: Collaborate with others (requires Marimo server)

---

## Troubleshooting

### "Module not found" errors

Install missing dependencies:
```bash
pip install -r ../requirements.txt
```

### "Data folder not found"

Run extraction pipeline first:
```bash
python -m oss_framework.orchestrator pipelines/00_extract_sis.json
```

### "Connection refused" errors

Check your environment variables:
```bash
export SIS_HOST="your-sis-host"
export SIS_USER="your-username"
export SIS_PASSWORD="your-password"
```

### Notebook runs very slowly

- Reduce dataset size in extraction (use `--limit 1000`)
- Close other applications
- Check database connectivity

---

## Next Steps After Notebooks

### 1. Deploy to Production

```bash
# Schedule daily pipeline runs
0 2 * * * python -m oss_framework.orchestrator pipelines/master_orchestrator.json

# Or use cloud scheduling (AWS Lambda, Azure Functions, etc.)
```

### 2. Create Dashboards

Using Stage 3 analytics data:
- **Grafana**: Real-time dashboards
- **Superset**: Self-service analytics
- **Metabase**: SQL-based exploration
- **Power BI**: Business intelligence

### 3. Set Up Monitoring

- Track pipeline execution times
- Monitor data quality metrics
- Alert on quality threshold violations
- Log all transformations for audit

### 4. Expand to Other Data Sources

- Copy this SIS template
- Adapt for other education sources:
  - HR/Staff data
  - Finance/Budget data
  - Assessment results
  - Attendance systems

---

## Reference Documentation

For more details on each topic:

- **Configuration**: See `../config/README.md`
- **Setup**: See `../SETUP_GUIDE.md`
- **Schemas**: See `../SCHEMAS.md`
- **Architecture**: See `../docs/ARCHITECTURE.md`
- **Privacy**: See `../docs/PRIVACY_RULES.md`
- **Troubleshooting**: See `../docs/TROUBLESHOOTING.md`

---

## Contact & Support

- **Questions**: Check troubleshooting section in each notebook
- **Issues**: See `../docs/TROUBLESHOOTING.md`
- **Enhancements**: Contribute to the OSS Framework

---

**Last Updated**: January 26, 2026  
**Framework**: Marimo (reactive notebooks)  
**Status**: Production-ready
