"""
## Data Profiling & Exploration

Interactive Marimo notebook for exploring extracted SIS data.

**What you'll learn**:
- How to load and explore extracted data
- How to identify data quality issues
- How to detect anomalies and missing values
- How to generate a data quality report

**Prerequisites**:
- Completed 00_package_setup.py notebook
- Ran extraction pipeline (00_extract_sis.json)
- Sample data available in sis_exports/ folder

**Time**: ~20 minutes
"""

import marimo

app = marimo.App()


@app.cell
def __():
    """
    # Data Profiling & Exploration

    This notebook explores the raw extracted data from your SIS system.
    We'll identify data quality issues, anomalies, and patterns.
    """
    import pandas as pd
    import numpy as np
    from pathlib import Path
    import os

    # Configuration
    EXPORT_FOLDER = "sis_exports"

    return pd, np, Path, os, EXPORT_FOLDER


@app.cell
def __(pd, Path, EXPORT_FOLDER):
    """
    ## Step 1: Load Extracted Data

    Load the CSV/JSON files exported from your SIS system.
    """
    import marimo as mo

    export_path = Path(EXPORT_FOLDER)

    if not export_path.exists():
        mo.md(f"❌ Export folder not found: {EXPORT_FOLDER}")
        mo.md(
            "Please run: `python -m oss_framework.orchestrator pipelines/00_extract_sis.json`"
        )
    else:
        # List available files
        files = list(export_path.glob("*.csv")) + list(export_path.glob("*.json"))

        if not files:
            mo.md(f"⚠ No CSV or JSON files found in {EXPORT_FOLDER}")
        else:
            mo.md(f"✓ Found {len(files)} exported files:")
            for f in files:
                mo.md(f"  - {f.name}")


@app.cell
def __(pd, Path, EXPORT_FOLDER):
    """
    Load the main entity files (students, courses, enrollment, attendance).
    """
    import marimo as mo

    # Try to load each entity
    data = {}
    entities = ["students", "courses", "enrollment", "attendance"]

    for entity in entities:
        csv_file = Path(EXPORT_FOLDER) / f"{entity}.csv"
        json_file = Path(EXPORT_FOLDER) / f"{entity}.json"

        if csv_file.exists():
            try:
                data[entity] = pd.read_csv(csv_file)
                mo.md(f"✓ Loaded {entity}: {len(data[entity])} records")
            except Exception as e:
                mo.md(f"⚠ Error loading {entity}: {str(e)}")
        elif json_file.exists():
            try:
                data[entity] = pd.read_json(json_file)
                mo.md(f"✓ Loaded {entity}: {len(data[entity])} records")
            except Exception as e:
                mo.md(f"⚠ Error loading {entity}: {str(e)}")

    return data


@app.cell
def __(data):
    """
    ## Step 2: Entity Summary

    Overview of each loaded entity.
    """
    import marimo as mo

    if not data:
        mo.md("No data loaded. Please check extraction.")
    else:
        for entity, df in data.items():
            mo.md(f"""
            ### {entity.upper()}
            
            **Records**: {len(df):,}  
            **Fields**: {len(df.columns)}  
            **Columns**: {", ".join(df.columns.tolist())}
            """)


@app.cell
def __(data, pd):
    """
    ## Step 3: Data Quality Overview

    Key metrics for each entity.
    """
    import marimo as mo

    if not data:
        mo.md("No data loaded.")
    else:
        for entity, df in data.items():
            # Calculate metrics
            null_count = df.isnull().sum()
            null_percent = (null_count / len(df) * 100).round(2)
            duplicates = df.duplicated().sum()

            quality_summary = f"""
            ### {entity.upper()} - Data Quality
            
            | Metric | Value |
            |--------|-------|
            | Total Records | {len(df):,} |
            | Total Fields | {len(df.columns)} |
            | Null Values | {null_count.sum():,} ({null_percent.mean():.2f}%) |
            | Duplicate Rows | {duplicates:,} |
            | Memory Usage | {df.memory_usage(deep=True).sum() / 1024 / 1024:.2f} MB |
            
            """

            # Find fields with most nulls
            fields_with_nulls = null_count[null_count > 0]
            if len(fields_with_nulls) > 0:
                quality_summary += f"""
            **Fields with Nulls**:
            """
                for field, count in fields_with_nulls.head(5).items():
                    pct = count / len(df) * 100
                    quality_summary += f"\n- {field}: {count:,} ({pct:.2f}%)"

            mo.md(quality_summary)


@app.cell
def __(data):
    """
    ## Step 4: Column-by-Column Analysis

    Detailed breakdown of each column's data.
    """
    import marimo as mo

    if not data:
        mo.md("No data loaded.")
    else:
        for entity, df in data.items():
            mo.md(f"### {entity.upper()} - Column Analysis")

            analysis = []
            for col in df.columns:
                col_data = df[col]
                null_count = col_data.isnull().sum()
                null_pct = null_count / len(df) * 100
                unique_count = col_data.nunique()

                # Determine data type
                dtype = str(col_data.dtype)

                # Get sample value
                sample = (
                    col_data.dropna().iloc[0] if len(col_data.dropna()) > 0 else "NULL"
                )

                row = f"""
| {col} | {dtype} | {unique_count:,} | {null_count:,} ({null_pct:.1f}%) | {str(sample)[:30]} |
"""
                analysis.append(row)

            mo.md(
                """
| Column | Type | Unique | Nulls | Sample |
|--------|------|--------|-------|--------|
"""
                + "".join(analysis)
            )


@app.cell
def __(data):
    """
    ## Step 5: Numeric Field Analysis

    Statistics for numeric columns.
    """
    import marimo as mo

    if not data:
        mo.md("No data loaded.")
    else:
        for entity, df in data.items():
            numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()

            if numeric_cols:
                mo.md(f"### {entity.upper()} - Numeric Fields")
                stats = df[numeric_cols].describe().T

                # Format for display
                summary = []
                for col in numeric_cols:
                    col_stats = df[col].describe()
                    summary.append(f"""
| {col} | {col_stats["count"]:.0f} | {col_stats["mean"]:.2f} | {col_stats["min"]:.2f} | {col_stats["max"]:.2f} |
""")

                mo.md(
                    """
| Column | Count | Mean | Min | Max |
|--------|-------|------|-----|-----|
"""
                    + "".join(summary)
                )


@app.cell
def __(data):
    """
    ## Step 6: Text Field Analysis

    Length and pattern analysis for text columns.
    """
    import marimo as mo

    if not data:
        mo.md("No data loaded.")
    else:
        for entity, df in data.items():
            text_cols = df.select_dtypes(include=["object"]).columns.tolist()

            if text_cols:
                mo.md(f"### {entity.upper()} - Text Fields")

                for col in text_cols[:5]:  # Top 5 text columns
                    col_data = df[col].dropna()

                    if len(col_data) > 0:
                        # Calculate string lengths
                        str_lens = col_data.astype(str).str.len()

                        # Get top values
                        top_values = col_data.value_counts().head(3)

                        summary = f"""
#### {col}
- **Total values**: {len(col_data):,}
- **Avg length**: {str_lens.mean():.1f} chars
- **Min/Max length**: {str_lens.min()}/{str_lens.max()}
- **Top values**:
"""
                        for val, count in top_values.items():
                            summary += f"\n  - {str(val)[:40]}: {count:,} ({count / len(col_data) * 100:.1f}%)"

                        mo.md(summary)


@app.cell
def __(data):
    """
    ## Step 7: Data Anomalies

    Identify potential data quality issues.
    """
    import marimo as mo

    if not data:
        mo.md("No data loaded.")
    else:
        anomalies = []

        for entity, df in data.items():
            mo.md(f"### {entity.upper()} - Anomalies")

            # Check for all nulls in a column
            all_null_cols = [col for col in df.columns if df[col].isnull().all()]
            if all_null_cols:
                anomalies.append(f"**⚠️  All null columns**: {', '.join(all_null_cols)}")

            # Check for constant values (potential issues)
            const_cols = [
                col
                for col in df.select_dtypes(
                    include=["object", "int64", "float64"]
                ).columns
                if df[col].nunique() == 1
            ]
            if const_cols:
                anomalies.append(
                    f"**⚠️  Constant value columns**: {', '.join(const_cols)}"
                )

            # Check for IDs with duplicates
            id_cols = [col for col in df.columns if "id" in col.lower() and col != "id"]
            for id_col in id_cols:
                dups = df[id_col].duplicated().sum()
                if dups > 0:
                    anomalies.append(f"**⚠️  {id_col}**: {dups:,} duplicates found")

            if anomalies:
                mo.md("\n".join([f"- {a}" for a in anomalies]))
            else:
                mo.md("✓ No obvious anomalies detected")

            anomalies = []


@app.cell
def __(data):
    """
    ## Step 8: Sample Records

    View actual data samples for verification.
    """
    import marimo as mo

    if not data:
        mo.md("No data loaded.")
    else:
        for entity, df in data.items():
            mo.md(f"### {entity.upper()} - Sample Records (First 5)")

            # Display first 5 rows
            mo.md(mo.ui.dataframe(df.head(5)))


@app.cell
def __(data):
    """
    ## Next Steps

    Based on this profiling:

    1. **Review data quality** - Any issues found above?
    2. **Update validation rules** - Adjust thresholds if needed
    3. **Check field mappings** - Do the field names match your SIS?
    4. **Move to transformation** - Run `02_transformation_flow.py`

    ### Data Quality Checklist

    - ✓ Record counts reasonable?
    - ✓ No unexpected all-null columns?
    - ✓ ID fields have duplicates?
    - ✓ Numeric ranges make sense?
    - ✓ Date fields are properly formatted?

    **Status**: Data profiling complete!

    **Next Notebook**: `02_transformation_flow.py` - Apply transformations
    """
    import marimo as mo

    mo.md("""
    ## Summary
    
    You've analyzed:
    - ✓ Entity record counts and field counts
    - ✓ Null value patterns and percentages
    - ✓ Numeric field statistics and ranges
    - ✓ Text field patterns and top values
    - ✓ Data anomalies and potential issues
    - ✓ Sample records for verification
    
    This profiling establishes the baseline data quality before transformation.
    """)


if __name__ == "__main__":
    app.run()
