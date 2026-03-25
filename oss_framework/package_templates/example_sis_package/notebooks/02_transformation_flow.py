"""
## Transformation Flow Walkthrough

Interactive Marimo notebook demonstrating each transformation step.

**What you'll learn**:
- How data flows through Stages 1, 2A, 2B, and 3
- What transformations happen at each stage
- How field mappings work
- How to visualize before/after comparisons

**Prerequisites**:
- Completed 01_data_profiling.py notebook
- Understand your field mappings

**Time**: ~25 minutes
"""

import marimo

app = marimo.App()


@app.cell
def __():
    """
    # Transformation Flow Walkthrough

    Watch your data transform through each stage of the data lake.
    """
    import pandas as pd
    import numpy as np
    from pathlib import Path
    import yaml

    return pd, np, Path, yaml


@app.cell
def __(Path, yaml):
    """
    ## Step 1: Load Configuration & Sample Data

    Load transformation rules and sample data.
    """
    import marimo as mo

    # Load transformation config
    config_path = Path("config/transformation_config.yaml")
    with open(config_path) as f:
        transform_config = yaml.safe_load(f)

    mo.md(f"""
    ✓ Loaded transformation configuration
    
    **Configured entities**: {len(transform_config["entities"])}  
    **Hash seed**: {transform_config.get("hash_seed", "NOT SET")[:20]}...  
    **Logging level**: {transform_config["logging"]["level"]}
    """)

    return transform_config


@app.cell
def __(transform_config):
    """
    ## Step 2: Understand Field Mappings

    How source SIS columns map to standard schema.
    """
    import marimo as mo

    for entity, config in transform_config["entities"].items():
        mappings = config["mappings"]

        mo.md(f"""
        ### {entity.upper()} Field Mappings
        
        **Total fields**: {len(mappings)}
        
        | Standard Field | SIS Column | Type |
        |---|---|---|
        """)

        for standard, sis_col in list(mappings.items())[:5]:
            data_type = config["type_mappings"].get(standard, "VARCHAR")
            mo.md(f"| {standard} | {sis_col} | {data_type} |")

        if len(mappings) > 5:
            mo.md(f"... and {len(mappings) - 5} more fields")


@app.cell
def __(transform_config):
    """
    ## Step 3: Stage 1 (Raw) - Preservation

    Stage 1 preserves raw extracted data with minimal changes.
    """
    import marimo as mo

    mo.md(f"""
    # Stage 1: Raw Data (Landing)
    
    **Purpose**: Preserve raw data exactly as extracted  
    **Transformations**: Minimal  
    **Privacy**: None applied yet  
    **Use**: Audit trail, error recovery
    
    ### What Happens at Stage 1
    
    1. **Organization**: Organize by date partition (YYYY/MM/DD)
    2. **No changes**: Keep original column names and values
    3. **Audit**: All records logged with load timestamp
    4. **Backup**: Act as recovery point if issues found downstream
    
    **Example folder structure**:
    ```
    stage1/
    ├── 2026/01/20/
    │   ├── students.csv
    │   ├── courses.csv
    │   └── enrollment.csv
    └── 2026/01/21/
        ├── students.csv
        ├── courses.csv
        └── enrollment.csv
    ```
    """)


@app.cell
def __(transform_config, pd):
    """
    ## Step 4: Stage 2A (Normalized) - Standardization

    Apply field mappings, flatten structures, and validate.
    """
    import marimo as mo

    mo.md(f"""
    # Stage 2A: Normalized Data
    
    **Purpose**: Standardize to common schema  
    **Transformations**: Field mapping, flattening, type conversion  
    **Privacy**: None yet  
    **Use**: Analysis-ready data
    
    ### Transformations Applied at Stage 2A
    
    **1. Field Mapping**
    - Rename SIS columns to standard names
    - Example: `StudentNumber` → `student_id`
    - Example: `FirstName` → `first_name`
    
    **2. Type Conversion**
    - Convert strings to proper types
    - Dates: Parse to YYYY-MM-DD format
    - Numbers: INT, FLOAT, NUMERIC
    - Booleans: Convert Y/N, T/F to 0/1
    
    **3. Data Validation**
    - Check for required fields (NOT NULL)
    - Validate unique constraints (IDs)
    - Check value ranges (grades, dates)
    - Pattern matching (email, phone)
    
    **4. Deduplication**
    - Remove duplicate records
    - Keep latest version by timestamp
    
    ### Example: Student Transformation
    
    **BEFORE (Stage 1 - Raw)**:
    ```
    StudentNumber, FirstName,  LastName,   GradeLevel, ModifyDate
    STU00123,      John,       Smith,      9,          2026-01-20
    STU00124,      Jane,       Doe,        10,         2026-01-20
    ```
    
    **AFTER (Stage 2A - Normalized)**:
    ```
    student_id, first_name, last_name, grade_level, _modified_date
    STU00123,   John,       Smith,     9,           2026-01-20
    STU00124,   Jane,       Doe,       10,          2026-01-20
    ```
    """)


@app.cell
def __(transform_config):
    """
    ## Step 5: Pseudonymization Rules

    How Stage 2B applies privacy rules.
    """
    import marimo as mo

    # Show pseudonymization rules
    for entity, config in list(transform_config["entities"].items())[:2]:
        rules = config.get("pseudonymization", {})

        mo.md(f"""
        ### {entity.upper()} - Pseudonymization Rules
        
        | Field | Rule | Effect |
        |-------|------|--------|
        """)

        hash_fields = [f for f, r in rules.items() if r == "hash"]
        mask_fields = [f for f, r in rules.items() if r == "mask"]
        noop_fields = [f for f, r in rules.items() if r == "no-op"]

        if hash_fields:
            mo.md(f"""
            **Hash (Deterministic)**:  
            {", ".join(hash_fields[:3])}
            """)

        if mask_fields:
            mo.md(f"""
            **Mask (Irreversible)**:  
            {", ".join(mask_fields[:3])}
            """)

        if noop_fields:
            mo.md(f"""
            **No-op (Unchanged)**:  
            {", ".join(noop_fields[:3])}
            """)


@app.cell
def __(transform_config):
    """
    ## Step 6: Stage 2B (Refined) - Pseudonymization

    Apply privacy rules and aggregate data.
    """
    import marimo as mo

    mo.md(f"""
    # Stage 2B: Refined Data (Privacy-Compliant)
    
    **Purpose**: Apply pseudonymization for privacy  
    **Transformations**: Hash/mask sensitive fields, aggregate  
    **Privacy**: FERPA-compliant  
    **Use**: Authorized analysis, reports
    
    ### Transformations Applied at Stage 2B
    
    **1. Field Hashing**
    - Deterministic hashing of IDs
    - `student_id: STU00123` → `hashed_student_id: a7f3e8d2c1b4...`
    - Same input always produces same hash
    - Allows authorized users to link records
    
    **2. Field Masking**
    - One-way masking of PII
    - `first_name: John` → `first_name: Jo****`
    - `phone: 555-1234` → `phone: 555-****`
    - Cannot reverse to get original value
    
    **3. Aggregation**
    - Create summary statistics
    - Group by hashable IDs
    - Example: Average grade per student (hashed)
    
    **4. View Creation**
    - Create filtered views for different user groups
    - Role-based access control (RBAC)
    
    ### Example: Student Pseudonymization
    
    **BEFORE (Stage 2A - Normalized)**:
    ```
    student_id, first_name, last_name, date_of_birth, grade_level
    STU00123,   John,       Smith,     1995-05-10,    9
    ```
    
    **AFTER (Stage 2B - Refined)**:
    ```
    hashed_student_id,      first_name, last_name, grade_level
    a7f3e8d2c1b45e9f2a3b,  Jo****,     Sm****,    9
    ```
    
    **Benefits**:
    - ✓ Student ID is still linkable (by authorized users)
    - ✓ Personal information is irreversibly masked
    - ✓ Non-sensitive grades remain for analysis
    - ✓ FERPA compliant
    """)


@app.cell
def __(transform_config):
    """
    ## Step 7: Stage 3 (Analytics) - Aggregation

    Create clean, analysis-ready tables.
    """
    import marimo as mo

    mo.md(f"""
    # Stage 3: Analytics Data
    
    **Purpose**: Clean, aggregate, analysis-ready  
    **Transformations**: Joins, computed features, metrics  
    **Privacy**: Same as Stage 2B  
    **Use**: Dashboards, reports, ML models
    
    ### Transformations Applied at Stage 3
    
    **1. Entity Joining**
    - Join students with courses
    - Join with enrollment data
    - Join with attendance/grades
    
    **2. Feature Engineering**
    - Compute attendance rate: `(days_present / total_days)`
    - Compute grade average: `AVG(assignment_grades)`
    - Compute engagement score
    
    **3. Aggregations**
    - Group by student, course, term
    - Create summary tables
    - Prepare for dashboards
    
    **4. Data Quality**
    - Final validation
    - Error flagging for known issues
    - Completeness checks
    
    ### Example: Student Performance Analytics
    
    **Created Table**: `stage3.student_performance`
    ```
    hashed_student_id, course_id, final_grade, 
    attendance_rate, grade_trend, engagement_score
    
    a7f3e8d2c1b45e9f,  MATH101, 85.0, 0.95, 0.0, 0.85
    a7f3e8d2c1b45e9f,  ENG101,  92.0, 0.98, 0.05, 0.90
    ```
    
    **Ready for**:
    - Dashboard widgets
    - Analytical queries
    - Machine learning models
    - Performance reports
    """)


@app.cell
def __(transform_config):
    """
    ## Step 8: Validation Rules at Each Stage

    What checks run at Stage 2A.
    """
    import marimo as mo

    for entity, config in list(transform_config["entities"].items())[:1]:
        validation = config.get("validation", {})

        mo.md(f"""
        ### {entity.upper()} - Stage 2A Validation Rules
        
        **Purpose**: Ensure data quality before downstream use
        """)

        # Null checks
        null_check = validation.get("null_check", [])
        if null_check:
            mo.md(f"""
            **Required Fields (Cannot be null)**:  
            {", ".join(null_check)}
            """)

        # Unique checks
        unique_check = validation.get("unique_check", [])
        if unique_check:
            mo.md(f"""
            **Unique Constraints**:  
            {", ".join(unique_check)}
            """)

        # Range checks
        range_check = validation.get("range_check", {})
        if range_check:
            mo.md(f"""
            **Value Range Validation**:  
            """)
            for field, (min_val, max_val) in range_check.items():
                mo.md(f"- {field}: {min_val} to {max_val}")


@app.cell
def __(transform_config):
    """
    ## Step 9: Data Quality Thresholds

    Overall quality targets.
    """
    import marimo as mo

    quality = transform_config.get("quality", {})

    mo.md(f"""
    ### Data Quality Standards
    
    | Metric | Threshold | Your Config |
    |--------|-----------|-------------|
    | Max Null % | <5% | {quality.get("max_null_percent", 0.05) * 100:.1f}% |
    | Max Duplicate % | <1% | {quality.get("max_duplicate_percent", 0.01) * 100:.1f}% |
    | Min Record Count | >100 | {quality.get("min_record_count", 100)} |
    | Max Error % | <2% | {quality.get("max_error_percent", 0.02) * 100:.1f}% |
    
    **Fail Criteria**: Pipeline stops if thresholds exceeded
    """)


@app.cell
def __(transform_config):
    """
    ## The Complete Data Flow

    Visualization of all transformations.
    """
    import marimo as mo

    mo.md(f"""
    # Complete Data Flow
    
    ```
    SIS System (Raw Extract)
        ↓
    [00_extract_sis.json]
    - Connect to SIS
    - Run SQL query
    - Export to CSV/JSON
        ↓
    Stage 1: Raw (Landing)  [01_land_stage1.json]
    ├─ Organize by date
    ├─ Preserve all data
    └─ No transformations
        ↓
    Stage 2A: Normalized  [02_transform_stage2a.json]
    ├─ Map fields (StudentNumber → student_id)
    ├─ Convert types
    ├─ Validate (null, unique, range)
    ├─ Flatten structures
    └─ Quality checks
        ↓
    Stage 2B: Refined  [03_refine_stage2b.json]
    ├─ Hash IDs (student_id → hashed_student_id)
    ├─ Mask PII (names, addresses)
    ├─ Aggregate metrics
    └─ Create views
        ↓
    Stage 3: Analytics  [04_aggregate_stage3.json]
    ├─ Join entities
    ├─ Compute features
    ├─ Create aggregations
    └─ Final validation
        ↓
    Dashboards & Reports
    - Grafana dashboards
    - Excel reports
    - ML models
    ```
    
    **Total transformations**: ~50 individual operations  
    **Data points preserved**: ~95% (some deduplicated)  
    **Privacy compliance**: FERPA compliant
    """)


@app.cell
def __(transform_config):
    """
    ## Next Steps

    You understand the transformation flow! Now:

    1. **Run the actual pipeline**:
       ```bash
       python -m oss_framework.orchestrator pipelines/00_extract_sis.json
       python -m oss_framework.orchestrator pipelines/01_land_stage1.json
       python -m oss_framework.orchestrator pipelines/02_transform_stage2a.json
       python -m oss_framework.orchestrator pipelines/03_refine_stage2b.json
       python -m oss_framework.orchestrator pipelines/04_aggregate_stage3.json
       ```

    2. **Validate quality** in next notebook:
       ```bash
       marimo edit notebooks/03_quality_validation.py
       ```

    3. **Compare stages** to verify transformations:
       ```bash
       marimo edit notebooks/04_stage_comparison.py
       ```

    **Status**: Transformation flow understood!

    **Next Notebook**: `03_quality_validation.py` - Validate data quality
    """
    import marimo as mo

    mo.md("""
    ## Summary
    
    You've learned:
    - ✓ How data flows through Stages 1, 2A, 2B, 3
    - ✓ Field mapping from SIS to standard schema
    - ✓ Type conversion and validation at Stage 2A
    - ✓ Pseudonymization strategies (hash, mask, no-op)
    - ✓ Privacy compliance at Stage 2B
    - ✓ Analytics preparation at Stage 3
    - ✓ Data quality thresholds and validation
    
    The transformation process is automated - just run the pipeline!
    """)


if __name__ == "__main__":
    app.run()
