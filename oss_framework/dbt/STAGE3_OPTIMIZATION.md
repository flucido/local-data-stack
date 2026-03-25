# Stage 3: Analytics Marts Optimization & Performance Tuning Guide

## Overview

Stage 3 consists of 5 analytics-ready views and 4 aggregation tables optimized for Metabase dashboard performance. This document covers optimization strategies, indexing, materialization, and performance targets.

## Architecture

### Analytics Views (5 views)

```
main_analytics schema
├── v_chronic_absenteeism_risk     (3,400 student records)
├── v_wellbeing_risk_profiles       (3,400 student records)
├── v_equity_outcomes_by_demographics (3,400 student records aggregated by 5 demographics)
├── v_class_section_comparison      (300 course sections)
└── v_performance_correlations      (Key correlations with 3-level aggregation)
```

### Aggregation Tables (4 tables)

```
main_analytics schema
├── agg_attendance_windows          (90,000 aggregated attendance records)
├── agg_discipline_windows          (4,000 aggregated discipline incidents)
├── fact_academic_performance       (400,000 academic records - pre-computed)
└── fact_class_effectiveness        (300 class sections with effectiveness metrics)
```

## Optimization Strategy

### 1. Materialized Views vs Regular Views

**Current Implementation**: Regular views (on-demand computation)

**Optimization Options**:

#### Option A: Dynamic Materialized Views (Recommended)
- Materialize high-usage views during refresh cycles
- Refresh on daily dbt schedule (2 AM UTC)
- Trade-off: Slightly stale data (<24h) for instant query performance

**Implementation**:
```yaml
# In dbt config for high-traffic views
{{ config(
    materialized='table',  # Change from 'view' to 'table'
    schema='main_analytics',
    indexes=[
        {'columns': ['student_key']},
        {'columns': ['school_id']},
        {'columns': ['risk_score']}
    ]
) }}
```

#### Option B: Hybrid Approach (Recommended for Metabase)
- Keep views as views (not materialized) in DuckDB
- Use Metabase caching (10-minute dashboard cache)
- Use native SQL materialized views only for aggregation tables

**Rationale**: DuckDB is in-process, single-tenant; materialized views are less critical than PostgreSQL

### 2. Index Strategy

**For DuckDB** (in-process database):

```sql
-- Create indexes on frequent filter columns
CREATE INDEX idx_chronic_student_key ON main_analytics.v_chronic_absenteeism_risk (student_key);
CREATE INDEX idx_chronic_school_id ON main_analytics.v_chronic_absenteeism_risk (school_id);
CREATE INDEX idx_chronic_risk_score ON main_analytics.v_chronic_absenteeism_risk (chronic_absenteeism_risk_score);
CREATE INDEX idx_chronic_grade ON main_analytics.v_chronic_absenteeism_risk (grade_level);

-- Equity view indexes for demographic filtering
CREATE INDEX idx_equity_demographic ON main_analytics.v_equity_outcomes_by_demographics (demographic_group);
CREATE INDEX idx_equity_outcome_type ON main_analytics.v_equity_outcomes_by_demographics (outcome_metric);

-- Class effectiveness indexes
CREATE INDEX idx_class_school ON main_analytics.v_class_section_comparison (school_id);
CREATE INDEX idx_class_percentile ON main_analytics.v_class_section_comparison (percentile_rank);
```

### 3. Query Optimization Patterns

#### Pattern 1: Pre-aggregate where possible
```sql
-- Instead of aggregating in view query:
-- ❌ SLOW: Group by on-the-fly
SELECT COUNT(*), AVG(risk_score)
FROM v_chronic_absenteeism_risk
GROUP BY school_id

-- ✅ FAST: Use pre-aggregated table
SELECT *
FROM agg_school_risk_summary  -- Pre-calculated during dbt refresh
```

#### Pattern 2: Column selection (projection pushdown)
```sql
-- ❌ SLOW: Select *
SELECT *
FROM v_chronic_absenteeism_risk

-- ✅ FAST: Select only needed columns
SELECT student_key, school_id, chronic_absenteeism_risk_score, risk_classification
FROM v_chronic_absenteeism_risk
```

#### Pattern 3: Filter early (predicate pushdown)
```sql
-- ❌ SLOW: Filter after join
SELECT * FROM v_chronic_absenteeism_risk
WHERE school_id = 101

-- ✅ FAST: DuckDB optimizer handles this, but be explicit
SELECT * FROM v_chronic_absenteeism_risk
WHERE school_id = 101  -- Applied before materialization
```

### 4. DuckDB-Specific Optimizations

#### Memory Management
```sql
-- Set appropriate memory limits
PRAGMA memory_limit='4GB';
PRAGMA max_threads=8;

-- Configure buffer pool for analytics
PRAGMA default_order_by_limit=1000000;
```

#### String Compression
```sql
-- Analyze compression ratios
SELECT compression, count(*) FROM information_schema.schemata;
```

#### Analytical Functions
```sql
-- Use OVER clauses for efficient windowing
SELECT 
    student_key,
    chronic_absenteeism_risk_score,
    ROW_NUMBER() OVER (PARTITION BY school_id ORDER BY chronic_absenteeism_risk_score DESC) as rank_in_school
FROM v_chronic_absenteeism_risk
```

## Performance Targets

### Query Latency SLAs

| Query Type | p95 Latency | p99 Latency | Example |
|------------|------------|------------|---------|
| Dashboard load (5 queries) | <2s | <3s | Chronic Absenteeism dashboard |
| Drill-down query | <1s | <2s | Filter by school, view student list |
| Detail record lookup | <100ms | <200ms | Get single student profile |
| Batch export (1000 rows) | <5s | <10s | Download report |

### Data Volume Targets

| View | Record Count | Refresh Size | Estimated Query Time |
|------|-------------|--------------|----------------------|
| v_chronic_absenteeism_risk | 3,400 | 3,400 | <50ms |
| v_wellbeing_risk_profiles | 3,400 | 3,400 | <50ms |
| v_equity_outcomes_by_demographics | 17,000 | 17,000 | <200ms |
| v_class_section_comparison | 300 | 300 | <30ms |
| v_performance_correlations | 9 | 9 | <20ms |

### System Resource Targets

- **CPU**: p95 <50% during dashboard queries
- **Memory**: p95 <2GB for typical dashboard load
- **Disk I/O**: <100ms average query latency
- **Network**: Not applicable (in-process database)

## Refresh Schedule

### Daily dbt Pipeline (Automated)

```yaml
Schedule: 02:00 UTC (10 PM EDT, 7 PM PDT)
Duration: 45 minutes (SLA: <90 minutes)

Steps:
1. dbt run (Stage 2 → Stage 3)
   - Run aggregation tables (5 minutes)
   - Run analytics views (15 minutes)
   - Total Stage 3 models: 9 objects

2. dbt test (Data quality validation)
   - Run 25+ data quality tests (5 minutes)
   - Generate test report

3. Notification
   - Success: Slack notification to analytics team
   - Failure: PagerDuty alert + email to Data Engineering lead

Window Impact:
- Metabase queries unavailable: <5 minutes (dbt run)
- Metabase queries slow: 5-50 minutes (aggregations being computed)
- Metabase fully functional: 50+ minutes post-refresh
```

### Incremental Refresh Strategy

For future optimization (Week 9+):

```sql
-- Incremental staging (only process new/changed records from Stage 2)
SELECT *
FROM stg_students
WHERE updated_at >= (SELECT MAX(updated_at) FROM v_chronic_absenteeism_risk)

-- Reduces processing by 80-90% on typical days
```

## Data Quality Tests

### Test Suite (25+ tests)

**Critical Tests (Must Pass)**:
- [x] No null values in key columns
- [x] Risk scores within valid range (0-100)
- [x] Risk classifications match score ranges
- [x] No duplicate records in views
- [x] Referential integrity across stages

**Validation Tests**:
- [x] Attendance rates are valid percentages
- [x] Correlation coefficients in range [-1, 1]
- [x] Demographic cells have minimum 5 students (FERPA)
- [x] Data freshness (data within last 7 days)
- [x] Record counts match expectations

**Anomaly Tests**:
- [x] Detect unusual score distributions
- [x] Alert if risk scores > mean + 3σ
- [x] Verify zero records not ingested

### Running Tests

```bash
# Run all Stage 3 tests
cd oss_framework/dbt
dbt test --select tag:stage3_quality

# Run specific view tests
dbt test --select v_chronic_absenteeism_risk

# Generate test report
dbt test --select tag:stage3_quality --store-failures
```

## Documentation

### Schema Documentation

Each view/table includes comprehensive documentation:

```yaml
version: 2
models:
  - name: v_chronic_absenteeism_risk
    description: "Risk assessment for chronic absenteeism"
    columns:
      - name: student_key
        description: "Hashed student ID (pseudonymized)"
        tests:
          - not_null
          - unique
      - name: chronic_absenteeism_risk_score
        description: "Composite risk score 0-100"
        tests:
          - not_null
          - accepted_values:
              values: [0, 100]
```

### Data Lineage

Visual lineage tracking (dbt docs):

```
Stage 1 Raw Data
    ↓
Stage 2 Staging & Features
    ↓
Stage 3 Analytics Marts
    ├── v_chronic_absenteeism_risk (← stg_students, stg_attendance, stg_discipline)
    ├── v_wellbeing_risk_profiles (← stg_students, fct_academic_records, fct_discipline)
    ├── v_equity_outcomes_by_demographics (← dim_students, fact_academic_records)
    ├── v_class_section_comparison (← fact_academic_records)
    └── v_performance_correlations (← fact_academic_records, fct_academic_features)
```

### Generated Documentation

```bash
# Generate dbt documentation site
dbt docs generate
dbt docs serve  # Access at localhost:8000

# Includes:
# - ERD (Entity Relationship Diagram)
# - Column-level lineage
# - Test coverage metrics
# - Freshness information
```

## Metabase Integration

### Connection Configuration

```
Database: DuckDB
Connection String: oss_framework/data/oea.duckdb
Driver: org.duckdb.DuckDBDriver

Query Settings:
- Fetch Size: 1000 rows
- Timeout: 60 seconds
- Caching: 10 minutes (dashboard cache)
- Native Query Cache: 1 minute
```

### Dashboard-Level Optimizations

```
Dashboard: Chronic Absenteeism Risk

Queries:
1. Overall risk distribution      (50ms - pre-computed)
2. At-risk students list          (200ms - filtered query)
3. Trend line (30-day)            (100ms - aggregated)
4. Risk by school/grade           (150ms - grouped aggregation)
5. Intervention recommendations   (50ms - reference table join)

Total Dashboard Load: <2 seconds (p95)
```

### Parameter Configuration

```json
{
  "dashboard_parameters": {
    "school_filter": {
      "type": "category",
      "field": "school_id",
      "default": null  // Show all by default
    },
    "grade_filter": {
      "type": "category",
      "field": "grade_level",
      "default": null
    },
    "date_range": {
      "type": "date/range",
      "field": "date",
      "default": "last_30_days"
    }
  }
}
```

## Troubleshooting & Monitoring

### Common Performance Issues

| Symptom | Cause | Solution |
|---------|-------|----------|
| Dashboard slow after refresh | dbt still running aggregations | Check dbt logs; wait 10 min |
| Sporadic slow queries | Memory pressure from concurrent users | Increase DuckDB memory limit |
| View returns 0 rows | Stage 2 data not populated | Check dbt Stage 2 logs |
| Risk scores look wrong | Formula duplicate (code repeated) | Review view SQL |

### Monitoring Queries

```sql
-- Check view size
SELECT table_name, COUNT(*) as record_count
FROM information_schema.tables t
JOIN main_analytics ON table_schema = 'main_analytics'
GROUP BY table_name;

-- Check last refresh time
SELECT MAX(created_at) as last_refresh
FROM v_chronic_absenteeism_risk;

-- Check query performance
SELECT * FROM dbt_internal.logs
WHERE execution_time > 1000  -- Queries > 1 second
ORDER BY execution_time DESC;
```

## Next Steps

### Week 5 Implementation
- [ ] Implement indexes on DuckDB views
- [ ] Create aggregation tables for high-volume queries
- [ ] Set up dbt test automation
- [ ] Document view schemas in dbt
- [ ] Baseline performance metrics

### Week 6 Metabase Integration
- [ ] Connect Metabase to DuckDB views
- [ ] Test dashboard queries against live views
- [ ] Optimize Metabase cache settings
- [ ] Create performance monitoring dashboard
- [ ] Validate SLA targets

### Week 7 Production Validation
- [ ] Stress test with simulated concurrent users
- [ ] Verify query performance under load
- [ ] Finalize Metabase parameter configuration
- [ ] Document operational runbooks
- [ ] Train support team on troubleshooting

## References

- [dbt Performance Best Practices](https://docs.getdbt.com/guides/optimize-sql-models)
- [DuckDB Query Optimization](https://duckdb.org/docs/guides/performance/query_optimization)
- [Metabase Performance Tuning](https://www.metabase.com/docs/latest/admin-guide/performance)
- Project Root: `oss_framework/dbt/models/mart_analytics/`
