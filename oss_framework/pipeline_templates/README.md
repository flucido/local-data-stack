# Pipeline Templates Documentation

## Overview

The OSS Framework provides 4 primary JSON-based pipeline templates for education analytics data processing. These templates are designed to be:

- **Language-agnostic**: Can run on Azure Synapse, Airflow, Dagster, etc.
- **Parameterized**: All paths, database connections, and configs injected at runtime
- **Modular**: Each stage can run independently or as part of the main orchestrator
- **Reusable**: Adapt to any data source by modifying parameters

## Pipeline Architecture

```
0_main_orchestrator
├── 1_preland_copy_raw_data
├── 2_land_ingest_data
├── 3_ingest_transform_normalize
├── 4_refine_pseudonymize_aggregate
└── validate_data_quality
```

Each pipeline builds on the previous stage, with explicit error handling and parameter injection.

---

## Pipeline Details

### 0_main_orchestrator.json

**Purpose**: Orchestrate entire data pipeline across all stages

**Key Features**:
- Sequential execution with dependency management
- Parameter validation before processing
- Parallel execution where possible (currently sequential for safety)
- Error handling and rollback support
- Success/failure notifications

**Required Parameters**:
```json
{
  "workspace": "production",
  "environment": "prod",
  "batch_mode": "delta",
  "notification_webhook": "https://example.com/webhook"
}
```

**Expected Inputs**:
- Raw data from external sources (pre-landing zone)

**Expected Outputs**:
- Populated Stage 1, Stage 2A, Stage 2B, and Stage 3 schemas
- Success notification to webhook

**Execution Time**: 2-4 hours (depending on data volume)

**Example Usage**:
```bash
# Run with environment-specific parameters
python run_pipeline.py \
  --pipeline 0_main_orchestrator.json \
  --workspace production \
  --environment prod \
  --batch_mode delta
```

---

### 1_preland_copy_raw_data.json

**Purpose**: Copy raw data from external systems without transformation

**Key Features**:
- Parallel copying from multiple sources (SIS, LMS, Directory)
- Error retry logic (configurable)
- Logging and audit trails
- Automatic cleanup of old pre-landing data

**Required Parameters**:
```json
{
  "workspace": "production",
  "environment": "prod",
  "sis_api_endpoint": "https://sis.example.com/api/v1",
  "lms_api_endpoint": "https://lms.example.com/api/v2",
  "directory_api_endpoint": "https://directory.example.com/api/v1"
}
```

**Data Sources**:
- Student Information System (SIS) - REST API
- Learning Management System (LMS) - REST API  
- Directory Service (Active Directory, Okta) - REST API

**Output Location**:
```
/pre_landing/
├── sis/
│   ├── students_{timestamp}.json
│   ├── courses_{timestamp}.json
│   └── enrollment_{timestamp}.json
├── lms/
│   └── engagement_{timestamp}.json
└── directory/
    └── users_{timestamp}.json
```

**Retention**: 7-30 days (configurable per environment)

**Execution Time**: 15-60 minutes (API-dependent)

---

### 2_land_ingest_data.json

**Purpose**: Organize pre-landing data into Stage 1 (raw, queryable tables)

**Key Features**:
- Organize by entity type (students, courses, enrollment, etc.)
- Support for delta, additive, and snapshot batch modes
- Schema validation against metadata
- Automatic cleanup of old pre-landing data

**Required Parameters**:
```json
{
  "workspace": "production",
  "environment": "prod",
  "batch_mode": "delta",
  "preland_retention_days": 30
}
```

**Batch Modes**:

**Delta** (Recommended for transactional data):
```
Load only changed records since last execution
- Identify: WHERE _updated_date > last_load_time
- Upsert into Stage 1
- Fast, efficient, recommended for daily runs
```

**Additive** (For event logs, engagement data):
```
Append-only, no updates
- Only INSERT new events
- Better for time-series analysis
- Used for engagement, attendance, assessment logs
```

**Snapshot** (Full replacement):
```
Replace entire dataset
- TRUNCATE and RELOAD
- Used when partial loads unavailable
- Higher resource usage
```

**Output Schema** (PostgreSQL example):
```sql
CREATE TABLE stage1_landing.students (
    student_key VARCHAR PRIMARY KEY,
    student_id VARCHAR,
    first_name VARCHAR,
    last_name VARCHAR,
    date_of_birth DATE,
    grade_level INT,
    school_id VARCHAR,
    _loaded_date TIMESTAMP,
    _source_system VARCHAR
);

CREATE TABLE stage1_landing.engagement_events (
    event_key VARCHAR PRIMARY KEY,
    student_id VARCHAR,
    event_type VARCHAR,
    event_timestamp TIMESTAMP,
    course_id VARCHAR,
    _loaded_date TIMESTAMP
);
```

**Execution Time**: 30-120 minutes (batch size dependent)

---

### 3_ingest_transform_normalize.json

**Purpose**: Transform and normalize Stage 1 into Stage 2A (flattened, standard schema)

**Key Features**:
- JSON flattening for nested structures
- Schema normalization (snake_case naming)
- Data type validation and casting
- Deduplication where needed
- Data quality reporting

**Required Parameters**:
```json
{
  "workspace": "production",
  "environment": "prod"
}
```

**Transformations Applied**:
- Flatten nested JSON (e.g., address objects → separate columns)
- Normalize field names (CamelCase → snake_case)
- Type casting (string dates → DATE type)
- Remove duplicates (if any)
- Add metadata columns (_normalized_date, _rule_version)

**Input** (Stage 1):
```sql
SELECT student_id, {complex_json_object}, _loaded_date FROM stage1_landing.students
```

**Output** (Stage 2A):
```sql
CREATE TABLE stage2a_ingested.students (
    student_key VARCHAR PRIMARY KEY,
    student_id VARCHAR,
    first_name VARCHAR,
    last_name VARCHAR,
    date_of_birth DATE,
    grade_level INT,
    school_id VARCHAR,
    address_street VARCHAR,  -- Flattened
    address_city VARCHAR,     -- Flattened
    address_state VARCHAR,    -- Flattened
    address_zip VARCHAR,      -- Flattened
    _loaded_date TIMESTAMP,
    _normalized_date TIMESTAMP
);
```

**Execution Time**: 30-90 minutes

---

### 4_refine_pseudonymize_aggregate.json

**Purpose**: Apply business logic, privacy rules, and aggregations. Creates Stage 2B (refined) and Stage 3 (published views)

**Key Features**:
- Privacy rule application (hash, mask, no-op)
- Feature engineering (aggregations, ratios, indicators)
- Dimension table creation (star schema)
- Fact table creation (aggregated metrics)
- Published SQL views for BI consumption

**Required Parameters**:
```json
{
  "workspace": "production",
  "environment": "prod",
  "metadata_version": "latest",
  "stage1_retention_years": 2
}
```

**Privacy Rules** (from metadata):
```csv
Entity,Attribute,DataType,Pseudonymization,Description
students,student_id,VARCHAR,hash,Student ID - hashed
students,first_name,VARCHAR,mask,First name - masked
students,grade_level,INT,no-op,Grade level - not sensitive
students,socioeconomic_status,VARCHAR,hash,SES - hashed
```

**Stage 2B Output** (Refined tables):
```sql
CREATE TABLE stage2b_refined.dim_students (
    student_key VARCHAR PRIMARY KEY,
    student_hash VARCHAR,  -- Hashed student_id
    grade_level INT,
    school_id VARCHAR,
    special_education BOOLEAN,
    english_learner BOOLEAN
);

CREATE TABLE stage2b_refined.fact_engagement (
    engagement_key VARCHAR PRIMARY KEY,
    student_hash VARCHAR,
    month_year DATE,
    event_count INT,
    avg_duration_minutes FLOAT,
    resource_access_count INT
);
```

**Stage 3 Output** (Published views):
```sql
CREATE VIEW stage3_published.v_engagement_by_school AS
SELECT
    school_id,
    month_year,
    COUNT(DISTINCT student_hash) as active_students,
    AVG(event_count) as avg_events_per_student,
    ROUND(100.0 * SUM(CASE WHEN event_count > 0 THEN 1 ELSE 0 END) 
        / COUNT(DISTINCT student_hash), 1) as engagement_pct
FROM stage2b_refined.fact_engagement
GROUP BY school_id, month_year;
```

**Execution Time**: 60-180 minutes (feature engineering dependent)

---

## Parameter Injection System

All parameters are injected at runtime from configuration files:

**Environment Configuration** (`config/prod.yaml`):
```yaml
workspace: production
environment: prod
database:
  host: prod-db.example.com
  port: 5432
  database: education_analytics_prod
pipelines:
  batch_mode: delta
  preland_retention_days: 30
  stage1_retention_years: 2
```

**Runtime Parameter Resolution**:
```json
{
  "pipeline": "0_main_orchestrator.json",
  "parameters": {
    "workspace": "${WORKSPACE}",          // From env var or config
    "environment": "${ENVIRONMENT}",      // From env var or config
    "batch_mode": "${BATCH_MODE}",        // From config with fallback
    "notification_webhook": "${WEBHOOK}"  // From secrets manager
  }
}
```

---

## Error Handling & Retry Logic

Each pipeline includes:

**Automatic Retries**:
```json
{
  "retryPolicy": {
    "maxAttempts": 3,
    "backoffFactor": 2,
    "initialInterval": 60
  }
}
```

**Failure Handling**:
```
On_Failure:
1. Log detailed error with timestamp and context
2. Rollback any partial writes (if applicable)
3. Send alert notification
4. Create incident ticket (optional)
5. Pause pipeline (manual resume required)
```

**Success Criteria**:
```
Each stage validates:
- Row counts (no unexpected drops)
- Schema conformance
- Data quality metrics
- Dependency completion
```

---

## Implementation Guide

### Prerequisites

1. Database (PostgreSQL, Snowflake, BigQuery, etc.)
2. Cloud storage (Azure Blob, S3, GCS, etc.)
3. Pipeline orchestrator (Apache Airflow, Azure Synapse, Dagster, etc.)
4. Python environment for Marimo notebooks
5. Configuration files (environment-specific)

### Setup Steps

1. **Clone templates**:
   ```bash
   cp oss_framework/pipeline_templates/*.json /your/pipelines/directory
   ```

2. **Customize parameters**:
   ```bash
   # Edit config/your_environment.yaml
   # Set database, storage, API endpoints
   ```

3. **Deploy pipeline definitions**:
   ```bash
   # For Azure Synapse
   az synapse pipeline create --name 0_main_orchestrator \
     --workspace myworkspace \
     --definition @pipeline_templates/0_main_orchestrator.json
   ```

4. **Test with sample data**:
   ```bash
   python run_pipeline.py \
     --pipeline 0_main_orchestrator.json \
     --environment test \
     --batch_mode snapshot
   ```

5. **Monitor execution**:
   ```bash
   # Check logs
   tail -f /var/log/analytics/pipeline.log
   
   # Monitor database growth
   SELECT stage, COUNT(*) as row_count FROM monitoring.stage_lineage GROUP BY stage;
   ```

---

## Monitoring & Observability

Each pipeline tracks:

**Lineage**:
```sql
SELECT 
    pipeline_name,
    stage,
    input_rows,
    output_rows,
    execution_time_minutes,
    status,
    error_message
FROM monitoring.pipeline_execution
ORDER BY execution_timestamp DESC;
```

**Data Quality**:
```sql
SELECT 
    stage,
    entity_type,
    metric_name,
    metric_value,
    threshold_value,
    status  -- PASS/FAIL/WARNING
FROM monitoring.data_quality_metrics
WHERE execution_date = CURRENT_DATE;
```

**Alerts**:
- Pipeline failures (immediate)
- Data volume anomalies (warning)
- Schema validation failures (blocker)
- Execution time exceeding threshold (warning)

---

## Troubleshooting

### Common Issues

**Issue**: Pipeline hangs at stage 2
- **Cause**: API timeout or large data volume
- **Solution**: Increase timeout, enable pagination, use snapshot batch mode

**Issue**: Schema validation fails
- **Cause**: Unexpected field added to source system
- **Reason**: Source system changed, needs metadata update
- **Solution**: Update metadata.csv, redeploy, re-run

**Issue**: Pseudonymization produces duplicate hashes
- **Cause**: Multiple student records with same ID
- **Solution**: Data quality issue upstream, add deduplication logic

**Issue**: Memory overflow on large aggregations
- **Cause**: Insufficient executor memory for feature engineering
- **Solution**: Split aggregation across multiple notebooks, or increase resources

---

## Best Practices

1. **Always test new transformations** with snapshot batch mode on test environment first
2. **Validate schema changes** before deploying to production
3. **Monitor pipeline execution** and set alerts for failures
4. **Document custom transformations** in notebook comments
5. **Version control** all pipeline definitions and configurations
6. **Maintain audit trails** for compliance and debugging
7. **Use parameter injection** - never hardcode paths or credentials
8. **Plan for scale** - test with 2-3x expected data volume

---

## Next Steps

1. Review and customize parameter templates for your environment
2. Adapt pre-landing API endpoints to your data sources
3. Create environment-specific configuration files (dev, test, staging, prod)
4. Test pipelines with sample data
5. Implement monitoring and alerting
6. Set up automated scheduling (daily, incremental)

---

**Document Version**: 1.0  
**Last Updated**: January 27, 2026
