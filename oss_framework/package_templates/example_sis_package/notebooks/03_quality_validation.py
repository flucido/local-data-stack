"""
## Data Quality Validation

Interactive Marimo notebook for comprehensive data quality checks.

**What you'll learn**:
- How to validate data against rules
- How to identify quality issues
- How to generate quality reports
- How to fix common problems

**Prerequisites**:
- Completed 02_transformation_flow.py
- Ran pipeline up to Stage 2A

**Time**: ~20 minutes
"""

import marimo

app = marimo.App()


@app.cell
def __():
    """
    # Data Quality Validation

    Comprehensive validation of transformed data against defined rules.
    """
    import pandas as pd
    import numpy as np
    from pathlib import Path
    import yaml

    return pd, np, Path, yaml


@app.cell
def __(Path, yaml, pd):
    """
    Load Stage 2A data for validation.
    """
    import marimo as mo

    # Load configuration
    with open(Path("config/transformation_config.yaml")) as f:
        config = yaml.safe_load(f)

    # Load sample Stage 2A data (from extraction or tests)
    stage2a_path = Path("data/sample")
    data = {}

    if stage2a_path.exists():
        for csv_file in stage2a_path.glob("*_sample.csv"):
            entity = csv_file.stem.replace("_sample", "")
            data[entity] = pd.read_csv(csv_file)
            mo.md(f"✓ Loaded {entity}: {len(data[entity])} records")
    else:
        mo.md("⚠ Sample data folder not found. Generating test data...")
        # Generate test data for demonstration
        data["students"] = pd.DataFrame(
            {
                "student_id": ["STU001", "STU002", None, "STU004"],
                "first_name": ["John", "Jane", "Bob", "Alice"],
                "grade_level": [9, 10, 11, 99],  # 99 is invalid
            }
        )

    return config, data


@app.cell
def __(config, data):
    """
    ## Validation Rules

    Define and apply validation checks.
    """
    import marimo as mo

    results = []

    for entity, df in data.items():
        if entity not in config["entities"]:
            continue

        entity_config = config["entities"][entity]
        validation = entity_config.get("validation", {})

        mo.md(f"### Validating {entity.upper()}")

        # Null check
        null_check = validation.get("null_check", [])
        if null_check:
            mo.md(f"**Null Check**: {', '.join(null_check)}")
            for col in null_check:
                if col in df.columns:
                    nulls = df[col].isnull().sum()
                    if nulls > 0:
                        mo.md(f"⚠️  {col}: {nulls} null values")
                        results.append(
                            {
                                "entity": entity,
                                "check": "null",
                                "column": col,
                                "status": "FAIL",
                                "count": nulls,
                            }
                        )
                    else:
                        mo.md(f"✓ {col}: No null values")
                        results.append(
                            {
                                "entity": entity,
                                "check": "null",
                                "column": col,
                                "status": "PASS",
                                "count": 0,
                            }
                        )

        # Unique check
        unique_check = validation.get("unique_check", [])
        if unique_check:
            mo.md(f"**Unique Check**: {', '.join(unique_check)}")
            for col in unique_check:
                if col in df.columns:
                    dups = df[col].duplicated().sum()
                    if dups > 0:
                        mo.md(f"⚠️  {col}: {dups} duplicates")
                        results.append(
                            {
                                "entity": entity,
                                "check": "unique",
                                "column": col,
                                "status": "FAIL",
                                "count": dups,
                            }
                        )
                    else:
                        mo.md(f"✓ {col}: All unique")
                        results.append(
                            {
                                "entity": entity,
                                "check": "unique",
                                "column": col,
                                "status": "PASS",
                                "count": 0,
                            }
                        )

        # Range check
        range_check = validation.get("range_check", {})
        if range_check:
            mo.md(f"**Range Check**: {len(range_check)} fields")
            for col, (min_val, max_val) in range_check.items():
                if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
                    out_of_range = df[(df[col] < min_val) | (df[col] > max_val)].shape[
                        0
                    ]
                    if out_of_range > 0:
                        mo.md(
                            f"⚠️  {col}: {out_of_range} values outside [{min_val}, {max_val}]"
                        )
                        results.append(
                            {
                                "entity": entity,
                                "check": "range",
                                "column": col,
                                "status": "FAIL",
                                "count": out_of_range,
                            }
                        )
                    else:
                        mo.md(f"✓ {col}: All in range [{min_val}, {max_val}]")


@app.cell
def __(config, data):
    """
    ## Quality Metrics

    Calculate overall quality scores.
    """
    import marimo as mo

    quality_cfg = config.get("quality", {})

    for entity, df in data.items():
        if entity not in config["entities"]:
            continue

        mo.md(f"### {entity.upper()} - Quality Metrics")

        # Calculate metrics
        total_cells = len(df) * len(df.columns)
        null_cells = df.isnull().sum().sum()
        null_pct = null_cells / total_cells * 100 if total_cells > 0 else 0

        dup_rows = df.duplicated().sum()
        dup_pct = dup_rows / len(df) * 100 if len(df) > 0 else 0

        # Compare to thresholds
        null_status = (
            "✓ PASS"
            if null_pct <= quality_cfg.get("max_null_percent", 0.05) * 100
            else "⚠️  FAIL"
        )
        dup_status = (
            "✓ PASS"
            if dup_pct <= quality_cfg.get("max_duplicate_percent", 0.01) * 100
            else "⚠️  FAIL"
        )
        record_status = (
            "✓ PASS"
            if len(df) >= quality_cfg.get("min_record_count", 100)
            else "⚠️  FAIL"
        )

        mo.md(f"""
        | Metric | Value | Status |
        |--------|-------|--------|
        | Records | {len(df):,} | {record_status} |
        | Null % | {null_pct:.2f}% | {null_status} |
        | Duplicate % | {dup_pct:.2f}% | {dup_status} |
        """)


@app.cell
def __(data):
    """
    ## Field-by-Field Quality Report

    Detailed per-field analysis.
    """
    import marimo as mo

    for entity, df in data.items():
        mo.md(f"### {entity.upper()} - Field Quality")

        report = []
        for col in df.columns:
            null_count = df[col].isnull().sum()
            null_pct = null_count / len(df) * 100
            unique = df[col].nunique()

            if pd.api.types.is_numeric_dtype(df[col]):
                stats = f"Mean: {df[col].mean():.2f}, Min: {df[col].min():.2f}, Max: {df[col].max():.2f}"
            else:
                sample = (
                    str(df[col].dropna().iloc[0])[:20]
                    if len(df[col].dropna()) > 0
                    else "NULL"
                )
                stats = f"Unique: {unique:,}, Sample: {sample}"

            status = "✓" if null_pct < 5 else "⚠️"
            report.append(f"| {col} | {null_pct:.1f}% | {stats} | {status} |")

        mo.md(
            "| Field | Null % | Stats | Status |\n|-------|--------|-------|--------|\n"
            + "\n".join(report)
        )


@app.cell
def __(data):
    """
    ## Anomaly Detection

    Identify unusual patterns and outliers.
    """
    import marimo as mo

    anomalies = []

    for entity, df in data.items():
        # Constant columns
        const_cols = [col for col in df.columns if df[col].nunique() == 1]
        if const_cols:
            anomalies.append(f"**{entity}**: Constant columns: {', '.join(const_cols)}")

        # Numeric outliers (>3 std devs)
        numeric_cols = df.select_dtypes(include=["number"]).columns
        for col in numeric_cols:
            mean = df[col].mean()
            std = df[col].std()
            if std > 0:
                outliers = df[abs((df[col] - mean) / std) > 3].shape[0]
                if outliers > 0:
                    anomalies.append(
                        f"**{entity}.{col}**: {outliers} outliers (>{3} std devs)"
                    )

    if anomalies:
        mo.md("### Detected Anomalies\n" + "\n".join([f"- {a}" for a in anomalies]))
    else:
        mo.md("### ✓ No obvious anomalies detected")


@app.cell
def __(data):
    """
    ## Recommendations

    Suggest fixes for identified issues.
    """
    import marimo as mo

    recommendations = [
        "1. **Null values in required fields**: Update source data or adjust field mapping",
        "2. **Duplicates**: Add unique constraint or review deduplication logic",
        "3. **Out-of-range values**: Update validation rules or clean source data",
        "4. **Constant columns**: Verify field mapping - may be unmapped fields",
        "5. **Outliers**: Review for data entry errors or adjust thresholds",
    ]

    mo.md("### Recommendations for Data Quality Issues\n" + "\n".join(recommendations))


@app.cell
def __(data):
    """
    ## Summary & Next Steps

    Quality validation complete!
    """
    import marimo as mo

    mo.md("""
    ### Validation Summary
    
    ✓ **Null value checks**: Verified required fields
    ✓ **Unique constraints**: Checked ID fields for duplicates
    ✓ **Range validation**: Confirmed numeric values in bounds
    ✓ **Quality metrics**: Calculated overall data quality scores
    ✓ **Anomaly detection**: Identified unusual patterns
    
    ### Next Steps
    
    **If issues found**:
    1. Update field mappings in `config/transformation_config.yaml`
    2. Re-run pipeline stages
    3. Re-run this validation
    
    **If validation passes**:
    1. Proceed to Stage 3 aggregation
    2. Run `04_stage_comparison.py` to verify transformations
    3. Deploy to production dashboards
    
    **Status**: Quality validation complete!
    
    **Next Notebook**: `04_stage_comparison.py` - Compare data across stages
    """)


if __name__ == "__main__":
    app.run()
