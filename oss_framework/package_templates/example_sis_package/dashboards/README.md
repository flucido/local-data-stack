# Dashboard Integration Guide

## Overview

This directory contains dashboard templates for three popular open-source BI tools:
- **Grafana** - Real-time monitoring and time-series analytics
- **Superset** - Modern data visualization and exploration
- **Metabase** - Simple, accessible BI for everyone

All dashboards connect to the Stage 3 analytics database, which contains fully de-identified, aggregated data suitable for public reporting.

---

## Quick Start

### Prerequisites

1. PostgreSQL database with Stage 3 analytics views populated
2. One of the following BI tools installed:
   - Grafana (v9.0+)
   - Apache Superset (v1.5+)
   - Metabase (v45+)

### Database Setup

```bash
# Verify Stage 3 schema and views exist
psql -h your_database -U user -d stage_3_db -c "\dt stage_3.*"

# Expected tables:
# - district_summary
# - grade_level_performance
# - department_performance
# - term_trends
# - at_risk_aggregates
# - course_utilization
# - advanced_track_performance
# - special_programs_impact
# - competency_mastery_trends
```

---

## Grafana Setup

### Installation

```bash
# Using Docker (recommended)
docker run -d -p 3000:3000 \
  -e GF_SECURITY_ADMIN_PASSWORD=admin \
  -v grafana-storage:/var/lib/grafana \
  grafana/grafana:latest

# Or install locally: https://grafana.com/grafana/download
```

### Connecting Data Source

1. **Open Grafana** (http://localhost:3000)
2. **Go to Configuration → Data Sources**
3. **Click "Add data source"**
4. **Select PostgreSQL** and configure:
   ```
   Host: your_db_host:5432
   Database: stage_3_db
   User: analytics_user
   Password: ****
   SSL Mode: require (or disable)
   ```
5. **Save & Test**

### Importing Dashboard

1. **Download** `grafana_district_overview.json`
2. **In Grafana**, click **+** → **Import**
3. **Paste JSON content** or upload file
4. **Select Data Source**: PostgreSQL (from step 3)
5. **Click Import**

### Dashboard Features

**SIS District Overview Dashboard** includes:

- **Key Metrics Cards** (Top Row):
  - Active Students (count)
  - District Average GPA (0.0-4.0)
  - District Attendance Rate (%)
  - Students at Risk (count)

- **Charts**:
  - Performance by Grade Level (line chart)
  - Enrollment Trends by Term (time-series)
  - Risk Indicators Summary (table)

### Custom Queries

Edit any panel to customize queries:

```sql
-- Example: Performance by specific grade level
SELECT 
  grade_level,
  student_count,
  avg_gpa,
  avg_attendance_rate,
  failure_rate_percent
FROM stage_3.grade_level_performance
WHERE grade_level BETWEEN 9 AND 12
ORDER BY grade_level;
```

### Alerts and Notifications

Set up alerts for key metrics:

1. **Edit Panel** → **Alert** tab
2. **Create condition**: e.g., "If attendance < 90%"
3. **Configure notification**: Email, Slack, webhook
4. **Save**

### Refresh Rates

Recommended refresh intervals by dashboard:

- **District Overview**: 6-12 hours (data usually updated daily)
- **Real-time Monitoring**: 1-5 minutes (for operational dashboards)
- **Historical Trends**: 24 hours

---

## Superset Setup

### Installation

```bash
# Using Docker (recommended)
docker run -d -p 8088:8088 \
  -e SUPERSET_ADMIN_USERNAME=admin \
  -e SUPERSET_ADMIN_PASSWORD=admin \
  apache/superset:latest

# Or: pip install apache-superset
# Then: superset db upgrade && superset run -p 8088
```

### Connecting Data Source

1. **Open Superset** (http://localhost:8088)
2. **Login** with admin credentials
3. **Go to Data → Databases**
4. **Click "+ Database"**
5. **Configure PostgreSQL**:
   ```
   Database Name: SIS Analytics
   SQLALCHEMY_URI: postgresql://user:password@host:5432/stage_3_db
   ```
6. **Test Connection** and **Save**

### Importing Datasets

1. **Download** `superset_datasets.json`
2. **Open Terminal** in Superset container/environment
3. **Import via API**:
   ```bash
   superset import-objects -i superset_datasets.json
   ```

### Or Manually Create Datasets

1. **Data → Datasets → "+ Dataset"**
2. **Select Database**: SIS Analytics
3. **Select Table**: e.g., `stage_3.grade_level_performance`
4. **Create Dataset**
5. **Edit Columns** to set field types and filters
6. **Save**

### Creating Charts and Dashboards

**Example: Grade Level Performance Chart**

1. **Data → Datasets → Grade Level Performance**
2. **Create Chart**
3. **Visualization Type**: Line Chart
4. **Settings**:
   - X-axis: grade_level
   - Y-axis: avg_gpa (left), failure_rate_percent (right)
   - Filters: none
5. **Save**

**Example: At-Risk Students Dashboard**

1. **Dashboards → "+ Dashboard"**
2. **Add Chart**: "At-Risk Students by Category"
3. **Add Chart**: "At-Risk Percentage Trend"
4. **Save Dashboard**

### Dataset Metrics

Pre-defined metrics available for all datasets:

- **District Summary**: count_students, avg_gpa, avg_attendance
- **Grade Performance**: total_students, avg_performance_gpa, avg_attendance
- **Department Performance**: total_courses, total_enrollments, avg_grade
- **Term Trends**: total_students, failure_rate_percent
- **At-Risk**: total_at_risk, avg_percent_at_risk

---

## Metabase Setup

### Installation

```bash
# Using Docker (recommended)
docker run -d -p 3000:3000 \
  -e MB_DB_TYPE=postgres \
  -e MB_DB_DBNAME=metabase \
  -e MB_DB_HOST=localhost \
  -e MB_DB_USER=postgres \
  -e MB_DB_PASS=password \
  metabase/metabase:latest

# Or download JAR: https://www.metabase.com/start/
# java -jar metabase.jar
```

### Connecting Database

1. **Open Metabase** (http://localhost:3000)
2. **Setup → Admin → Databases**
3. **Add Database**
4. **PostgreSQL Configuration**:
   ```
   Name: SIS Analytics
   Host: your_db_host
   Port: 5432
   Database: stage_3_db
   Username: analytics_user
   Password: ****
   ```
5. **Save**

### Syncing Data Model

1. **Go to Admin → Data Model**
2. **Select Database**: SIS Analytics
3. **Click Sync database schema**
4. **Wait for sync to complete** (should recognize Stage 3 tables)

### Importing Questions

1. **Download** `metabase_questions.json`
2. **Collections → Create New → Import**
3. **Upload JSON file**
4. **Select Database**: SIS Analytics
5. **Import**

### Or Create Questions Manually

**Example: Average GPA by Grade**

1. **+ New → Question**
2. **Simple question**
3. **Data**: stage_3.grade_level_performance
4. **Columns**: grade_level, avg_gpa, student_count
5. **Summarize**: Count of rows (or leave as-is)
6. **Visualize**
7. **Save** as "Average GPA by Grade"

**Example: At-Risk Dashboard**

1. **+ New → Dashboard**
2. **Add question**: "At-Risk Students by Category"
3. **Add question**: "Chronically Absent by Grade"
4. **Add question**: "Academic Risk Summary"
5. **Save** as "At-Risk Students Overview"

### Row-Level Security (RLS)

Set up role-based access:

1. **Admin → Settings → Authentication → Google Sign-in** (or other SSO)
2. **Enable RLS**:
   - Teachers see only their students
   - Admins see all data
   - Researchers see aggregates only

```sql
-- Example: RLS policy for teachers
SELECT *
FROM stage_3.grade_level_performance
WHERE grade_level IN (SELECT DISTINCT grade_level FROM teacher_assignments WHERE teacher_id = current_user_id)
```

---

## Dashboard Comparison

| Feature | Grafana | Superset | Metabase |
|---------|---------|----------|----------|
| **Setup Difficulty** | Medium | Medium | Easy |
| **Real-time Dashboards** | ✓ Excellent | ✓ Good | - Scheduled |
| **Ad-hoc Exploration** | - Limited | ✓ Excellent | ✓ Very Good |
| **Row-Level Security** | ✓ | ✓ | ✓ |
| **SQL Editor** | ✓ | ✓ | ✓ |
| **Alerts** | ✓ Excellent | - | - |
| **Mobile** | ✓ | ✓ | ✓ |
| **Open Source** | ✓ | ✓ | ✓ |

---

## Performance Optimization

### Query Optimization

1. **Create Indexes** on frequently queried columns:
   ```sql
   CREATE INDEX idx_grade_perf_grade ON stage_3.grade_level_performance(grade_level);
   CREATE INDEX idx_term_trends_term ON stage_3.term_trends(term);
   CREATE INDEX idx_at_risk_category ON stage_3.at_risk_aggregates(risk_category);
   ```

2. **Materialized Views** for complex aggregations:
   ```sql
   CREATE MATERIALIZED VIEW v_performance_dashboard AS
   SELECT * FROM stage_3.grade_level_performance;
   
   REFRESH MATERIALIZED VIEW v_performance_dashboard;
   ```

3. **Query Caching**:
   - Grafana: Panel cache TTL
   - Superset: Query cache
   - Metabase: Question caching

### Data Refresh Strategy

```
Stage 1: Daily (e.g., 2 AM)
Stage 2A: With Stage 1
Stage 2B: With Stage 1
Stage 3: With Stage 1
Dashboard Refresh: 6-24 hours (after Stage 3 refresh)
```

---

## Security Best Practices

### Database Security

1. **Create Read-Only User**:
   ```sql
   CREATE USER dashboard_user WITH PASSWORD 'strong_password';
   GRANT USAGE ON SCHEMA stage_3 TO dashboard_user;
   GRANT SELECT ON ALL TABLES IN SCHEMA stage_3 TO dashboard_user;
   ALTER DEFAULT PRIVILEGES IN SCHEMA stage_3 GRANT SELECT ON TABLES TO dashboard_user;
   ```

2. **Restrict Access**:
   - Firewall: Allow only dashboard servers
   - SSL: Require encrypted connections
   - VPN: Connect via secure tunnel

### Dashboard Security

1. **Authentication**:
   - Require login for all dashboards
   - Use SSO (SAML, OAuth) where possible
   - Regular password rotation

2. **Authorization**:
   - Role-based access (admin, teacher, researcher)
   - Limit data based on role
   - Audit access logs

3. **Data Privacy**:
   - All PII is already pseudonymized in Stage 3
   - Never expose Stage 1 or 2B data
   - Log all data access

---

## Common Troubleshooting

### Connection Issues

**Error: "could not connect to server"**
```bash
# Test database connection
psql -h your_db_host -U analytics_user -d stage_3_db -c "SELECT 1;"

# Check firewall
nc -zv your_db_host 5432

# Verify credentials in dashboard config
```

**Error: "SSL connection error"**
```
Try setting SSL Mode to "disable" or "allow"
Or provide CA certificate if required
```

### Data Issues

**No data showing in dashboard**
```sql
-- Verify data exists in Stage 3
SELECT COUNT(*) FROM stage_3.district_summary;
SELECT COUNT(*) FROM stage_3.grade_level_performance;

-- Check if views were created successfully
\dv stage_3.*  -- PostgreSQL
```

**Slow queries**
```bash
# Enable query logging
# Analyze slow queries
EXPLAIN ANALYZE SELECT * FROM stage_3.grade_level_performance;

# Add indexes if needed
CREATE INDEX idx_name ON table_name(column);
```

### Dashboard Issues

**Dashboard not loading**
- Refresh browser cache (Ctrl+Shift+R)
- Check browser console for errors (F12)
- Verify data source is connected

**Metrics show as null**
- Check if data exists in source tables
- Verify aggregation settings in metric definition
- Check for null values in source data

---

## Maintenance

### Regular Tasks

**Weekly**:
- Monitor dashboard load times
- Check for errors in logs
- Verify data freshness

**Monthly**:
- Review and clean up unused questions/dashboards
- Update documentation
- Audit user access

**Quarterly**:
- Performance tuning (indexes, queries)
- Update BI tool versions
- Review and optimize SQL queries
- Privacy and security audit

### Backup Strategy

```bash
# Backup Grafana dashboards
curl -H "Authorization: Bearer $GRAFANA_API_TOKEN" \
  http://localhost:3000/api/search \
  > grafana_dashboards_backup.json

# Backup Superset metadata
docker exec superset superset export-dashboards -f superset_backup.json

# Backup Metabase
docker exec metabase java -jar metabase.jar dump > metabase_backup.sql
```

---

## Advanced Features

### Grafana: Custom Variables

```
Variable Name: grade_level
Type: Query
Query: SELECT DISTINCT grade_level FROM stage_3.grade_level_performance ORDER BY grade_level
```

### Superset: Drill-Down

1. Create base chart (Grade Performance)
2. Create detail chart (Grade + Department)
3. Configure drill-down in dashboard

### Metabase: Filters

1. Add Filter to Dashboard
2. Select: grade_level
3. Link to: All questions using grade_level
4. Users can now filter across all questions

---

## Support and Resources

- **Grafana Docs**: https://grafana.com/docs/
- **Superset Docs**: https://superset.apache.org/docs/
- **Metabase Docs**: https://www.metabase.com/learn/
- **PostgreSQL Docs**: https://www.postgresql.org/docs/

---

## File Reference

| File | Tool | Purpose |
|------|------|---------|
| grafana_district_overview.json | Grafana | Pre-built district overview dashboard |
| superset_datasets.json | Superset | Pre-configured datasets with metrics |
| metabase_questions.json | Metabase | Pre-built questions and charts |
| README.md | All | Setup and integration guide |

---

**Document Version**: 1.0  
**Last Updated**: 2024  
**Maintained By**: Analytics Team  
**Next Review**: When upgrading BI tools or dashboard requirements change
