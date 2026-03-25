"""
## Package Setup & Configuration Walkthrough

Interactive Marimo notebook for configuring the SIS package template.

**What you'll learn**:
- How to customize extraction_config.yaml for your SIS
- How to map fields for your specific data source
- How to set up environment variables and credentials
- How to test the configuration

**Prerequisites**:
- Python 3.8+ installed
- Access to your SIS system
- SQL database (PostgreSQL, Snowflake, Azure SQL)

**Time**: ~15 minutes
"""

import marimo

app = marimo.App()


@app.cell
def __():
    """
    # Package Setup & Configuration

    This notebook will walk you through configuring the SIS package template
    for your specific Student Information System.
    """
    import os
    from pathlib import Path
    import yaml
    import json

    return os.path, Path, yaml, json


@app.cell
def __(app):
    """
    ## Step 1: Understanding Your Configuration Files

    The SIS package uses two main configuration files:

    1. **extraction_config.yaml** - How to connect to your SIS and extract data
    2. **transformation_config.yaml** - How to map and validate fields

    Let's load and examine the current configurations.
    """
    config_dir = Path("config")

    # Load extraction config
    with open(config_dir / "extraction_config.yaml") as f:
        extraction_config = yaml.safe_load(f)

    # Load transformation config
    with open(config_dir / "transformation_config.yaml") as f:
        transformation_config = yaml.safe_load(f)

    import marimo as mo

    mo.md(f"""
    ### Current Extraction Configuration
    
    **SIS System**: {extraction_config["sis"]["system"]}  
    **Host**: {extraction_config["sis"]["host"]}  
    **Database**: {extraction_config["sis"]["database"]}  
    **Batch Mode**: {extraction_config["batch"]["mode"]}  
    
    **Output Format**: {extraction_config["output"]["format"]}  
    **Output Folder**: {extraction_config["output"]["folder"]}  
    """)

    return extraction_config, transformation_config


@app.cell
def __(transformation_config):
    """
    ### Configured Entities

    The transformation config includes mappings for these entities:
    """
    import marimo as mo

    entities = list(transformation_config["entities"].keys())

    entity_info = []
    for entity in entities:
        mappings = transformation_config["entities"][entity]["mappings"]
        entity_info.append(f"- **{entity}**: {len(mappings)} fields")

    mo.md("\n".join(entity_info))

    return entities


@app.cell
def __(app, extraction_config, entities):
    """
    ## Step 2: Identifying Your SIS System

    Which Student Information System do you use?
    """
    import marimo as mo

    # Common SIS systems
    sis_systems = {
        "powerschool": "PowerSchool (MSSQL, ODBC)",
        "skyward": "Skyward by Jenzabar (MSSQL, ODBC)",
        "infinite_campus": "Infinite Campus (REST API)",
        "generic_sql": "Generic SQL Server",
        "other": "Other system",
    }

    # Current system
    current_system = extraction_config["sis"]["system"]

    sis_choice = mo.ui.dropdown(
        options=sis_systems, value=current_system, label="Select Your SIS:"
    )

    (
        mo.md(f"""
    ### Your SIS Selection
    
    Current: **{sis_systems.get(current_system, "Unknown")}**
    
    Change to:
    """),
        sis_choice,
    )


@app.cell
def __(sis_choice, sis_systems):
    """
    ### SIS-Specific Configuration Examples

    Based on your selection, here are the key connection parameters:
    """
    import marimo as mo

    selected = sis_choice.value

    configs = {
        "powerschool": {
            "connection": "MSSQL via ODBC",
            "host_example": "ps.school.edu",
            "port_example": 1433,
            "driver_example": "mssql+pyodbc",
            "key_tables": ["STUDENTS", "COURSES", "ENROLLMENTS"],
            "timestamp_column": "LASTUPDATEDATE",
        },
        "skyward": {
            "connection": "MSSQL via ODBC",
            "host_example": "skyward.school.edu",
            "port_example": 1433,
            "driver_example": "mssql+pyodbc",
            "key_tables": ["STUDENTS", "COURSES", "ENROLLMENTS"],
            "timestamp_column": "LastChangeDate",
        },
        "infinite_campus": {
            "connection": "REST API (HTTPS)",
            "host_example": "campus.school.edu",
            "port_example": 443,
            "driver_example": "rest+https",
            "key_endpoints": ["/services/v2/students", "/services/v2/courses"],
            "timestamp_field": "lastModifiedDate",
        },
        "generic_sql": {
            "connection": "Generic SQL Server",
            "host_example": "sqlserver.school.edu",
            "port_example": 1433,
            "driver_example": "mssql+pyodbc",
            "note": "Adjust table and column names to match your schema",
        },
    }

    if selected in configs:
        cfg = configs[selected]
        info = f"""
        ### {sis_systems[selected]} Configuration
        
        **Connection Type**: {cfg["connection"]}  
        **Host Example**: {cfg.get("host_example", "N/A")}  
        **Port**: {cfg.get("port_example", "N/A")}  
        **Driver**: {cfg.get("driver_example", "N/A")}  
        
        **Key Tables/Endpoints**: {", ".join(cfg.get("key_tables", cfg.get("key_endpoints", [])))}  
        **Timestamp Column**: {cfg.get("timestamp_column", cfg.get("timestamp_field", "N/A"))}  
        """
        if "note" in cfg:
            info += f"\n**Note**: {cfg['note']}"
    else:
        info = "Please select a valid SIS system."

    mo.md(info)


@app.cell
def __(app):
    """
    ## Step 3: Environment Variables

    Before running extractions, set your SIS credentials as environment variables:
    """
    import marimo as mo
    import os

    env_vars = {
        "SIS_HOST": os.getenv("SIS_HOST", "NOT SET"),
        "SIS_USER": "***" if os.getenv("SIS_USER") else "NOT SET",
        "SIS_PASSWORD": "***" if os.getenv("SIS_PASSWORD") else "NOT SET",
        "DB_HOST": os.getenv("DB_HOST", "NOT SET"),
        "DB_USER": os.getenv("DB_USER", "NOT SET"),
        "DB_PASSWORD": "***" if os.getenv("DB_PASSWORD") else "NOT SET",
    }

    status_lines = []
    for var, value in env_vars.items():
        status = "✓ SET" if value != "NOT SET" else "✗ NOT SET"
        status_lines.append(f"- {var}: {status}")

    mo.md(f"""
    ### Environment Variable Status
    
    {"".join(status_lines)}
    
    ### To Set Environment Variables
    
    **Option 1: Terminal (Linux/Mac)**
    ```bash
    export SIS_HOST="ps.school.edu"
    export SIS_USER="svc_extract"
    export SIS_PASSWORD="your-password"
    export DB_HOST="datalake.server.com"
    export DB_USER="datalake_user"
    export DB_PASSWORD="your-password"
    ```
    
    **Option 2: Create .env file**
    ```
    SIS_HOST=ps.school.edu
    SIS_USER=svc_extract
    SIS_PASSWORD=your-password
    DB_HOST=datalake.server.com
    DB_USER=datalake_user
    DB_PASSWORD=your-password
    ```
    
    Then load in Python:
    ```python
    from dotenv import load_dotenv
    load_dotenv()
    ```
    
    **Option 3: Windows (Command Prompt)**
    ```
    set SIS_HOST=ps.school.edu
    set SIS_USER=svc_extract
    set SIS_PASSWORD=your-password
    ```
    """)


@app.cell
def __(app):
    """
    ## Step 4: Customizing Field Mappings

    The transformation config defines how SIS columns map to standard schema.
    """
    import marimo as mo

    mo.md("""
    ### Example: Student Field Mapping
    
    **Standard Field** → **Your SIS Column**
    
    ```yaml
    mappings:
      student_id: StudentNumber        # Change to your SIS column name
      first_name: FirstName
      last_name: LastName
      date_of_birth: BirthDate
      grade_level: GradeLevel
      enrollment_status: Status
    ```
    
    ### Common Variations by Vendor
    
    | Field | PowerSchool | Skyward | Infinite Campus |
    |-------|-------------|--------|-----------------|
    | Student ID | STUDENTID | StudentNumber | studentId |
    | First Name | FIRSTNAME | FirstName | firstName |
    | Grade Level | GRADE_LEVEL | Grade | gradeLevel |
    | Status | STATUS | StatusCode | enrollmentStatus |
    
    ### Steps to Customize
    
    1. **Export sample data** from your SIS to understand column names
    2. **Open config/transformation_config.yaml**
    3. **Update mappings** section with your actual column names
    4. **Save the file**
    5. **Run validation** (next notebook)
    """)


@app.cell
def __(app):
    """
    ## Step 5: Batch Mode Selection

    How often will you run extractions?
    """
    import marimo as mo

    batch_modes = {
        "delta": {
            "description": "Incremental - Extract only modified records since last run",
            "frequency": "Daily/Hourly",
            "best_for": "Production environments",
        },
        "additive": {
            "description": "Append - Add all records to existing data",
            "frequency": "Weekly",
            "best_for": "Historical tracking",
        },
        "snapshot": {
            "description": "Replace - Replace entire table with fresh extract",
            "frequency": "Weekly/Monthly",
            "best_for": "Small reference tables",
        },
    }

    mode_choice = mo.ui.dropdown(
        options={k: v["description"] for k, v in batch_modes.items()},
        value="delta",
        label="Select Batch Mode:",
    )

    (
        mo.md(f"""
    ### Batch Mode Comparison
    
    | Mode | Description | Schedule | Use Case |
    |------|-------------|----------|----------|
    | **delta** | Incremental changes | Daily/Hourly | Production with large datasets |
    | **additive** | Append all records | Weekly | Historical snapshots |
    | **snapshot** | Replace entire table | Weekly/Monthly | Small reference data |
    
    Your Choice:
    """),
        mode_choice,
    )


@app.cell
def __(mode_choice):
    """
    ### Your Selection
    """
    import marimo as mo

    mo.md(f"**Selected Batch Mode**: {mode_choice.value}")


@app.cell
def __(app):
    """
    ## Step 6: Privacy & Pseudonymization

    How should we protect sensitive student data?
    """
    import marimo as mo

    mo.md("""
    ### Pseudonymization Rules (Applied at Stage 2B)
    
    | Rule | Effect | Use For | Security |
    |------|--------|---------|----------|
    | **hash** | Deterministic hashing | IDs, DoB | Linkable by authorized users |
    | **mask** | Irreversible masking | Names, addresses | Fully anonymous |
    | **no-op** | Keep unchanged | Grades, codes | Non-sensitive data |
    
    ### Current Privacy Configuration
    
    **PII Fields (Hashed)**:
    - student_id, teacher_id, date_of_birth
    
    **Personal Information (Masked)**:
    - first_name, last_name, phone_number, email_address, addresses
    
    **Non-Sensitive (No Change)**:
    - grade_level, enrollment_status, grades, attendance
    
    ### FERPA Compliance
    
    This package implements FERPA-compliant pseudonymization:
    - ✓ Student IDs are hashed (deterministic for authorized linking)
    - ✓ Names are masked (irreversible)
    - ✓ Dates are protected (birth dates hashed)
    - ✓ Non-sensitive grades/codes remain for analytics
    
    See `docs/PRIVACY_RULES.md` for detailed rationale.
    """)


@app.cell
def __(app):
    """
    ## Step 7: Testing Your Configuration

    Let's validate that your setup is correct.
    """
    import marimo as mo

    mo.md("""
    ### Configuration Validation Checklist
    
    - [ ] **extraction_config.yaml** updated with your SIS details
    - [ ] **transformation_config.yaml** updated with your field mappings
    - [ ] **Environment variables** set for credentials
    - [ ] **Database connection** tested
    - [ ] **SIS query** tested in SIS query tool
    
    ### Testing Steps
    
    **1. Test Database Connection**
    ```python
    import sqlalchemy as sa
    engine = sa.create_engine(
        f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/data_lake"
    )
    with engine.connect() as conn:
        print("✓ Connected to data lake!")
    ```
    
    **2. Test SIS Connection**
    ```python
    import pyodbc
    conn = pyodbc.connect(
        f"Driver={{ODBC Driver 17 for SQL Server}};"
        f"Server={SIS_HOST};Database=pssis;"
        f"UID={SIS_USER};PWD={SIS_PASSWORD}"
    )
    print("✓ Connected to SIS!")
    ```
    
    **3. Test Sample Extraction** (next notebook)
    ```bash
    python -m oss_framework.orchestrator \\
      pipelines/00_extract_sis.json \\
      --limit 100 \\
      --dry-run
    ```
    """)


@app.cell
def __(app):
    """
    ## Next Steps

    Once you've completed this setup:

    1. **Update your configurations** based on your SIS details
    2. **Run notebook 01_data_profiling.py** to explore extracted data
    3. **Run notebook 03_quality_validation.py** to validate quality
    4. **Execute the full pipeline**:
       ```bash
       python -m oss_framework.orchestrator pipelines/00_extract_sis.json
       python -m oss_framework.orchestrator pipelines/01_land_stage1.json
       python -m oss_framework.orchestrator pipelines/02_transform_stage2a.json
       python -m oss_framework.orchestrator pipelines/03_refine_stage2b.json
       python -m oss_framework.orchestrator pipelines/04_aggregate_stage3.json
       ```

    ### Getting Help

    - **Configuration Issues**: See `config/README.md`
    - **Setup Problems**: See `SETUP_GUIDE.md`
    - **Data Schema**: See `SCHEMAS.md`
    - **Troubleshooting**: See `docs/TROUBLESHOOTING.md`
    """
    import marimo as mo

    mo.md("""
    ## Summary
    
    You've learned how to:
    - ✓ Understand the two main configuration files
    - ✓ Identify your SIS system and connection parameters
    - ✓ Set up environment variables for secure credential handling
    - ✓ Customize field mappings for your data source
    - ✓ Choose the right batch mode for your use case
    - ✓ Understand FERPA-compliant privacy rules
    - ✓ Test your configuration before running extractions
    
    **Status**: Configuration setup complete!
    
    **Next Notebook**: `01_data_profiling.py` - Explore sample data
    """)


if __name__ == "__main__":
    app.run()
