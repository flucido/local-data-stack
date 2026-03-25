# Operational Runbooks - Post-Launch Support

## Overview

Comprehensive operational procedures for managing the local-data-stack analytics platform. These runbooks are designed for 24/7 support operations of Docker-based services (Rill + JupyterLab) with DuckDB backend.

**Architecture**: 100% local stack with no cloud dependencies. All data processing happens on-premises with DuckDB, dbt, and Rill.

---

## 1. Incident Response Runbook

### 1.1 Rill Dashboard Not Loading

**Severity**: High
**SLA**: 1 hour resolution

**Diagnosis**:
```bash
# Check Rill container status
docker-compose ps rill
docker-compose logs -f rill --tail=100

# Check DuckDB file accessibility
ls -lh oss_framework/data/oea.duckdb
du -sh oss_framework/data/oea.duckdb

# Check Rill service health
curl -f http://localhost:9009/health || echo "Rill not responding"

# Check for port conflicts
lsof -i :9009
```

**Common Causes & Solutions**:

| Symptom | Cause | Solution |
|---------|-------|----------|
| 502 Bad Gateway | Rill container crashed | `docker-compose restart rill` |
| Empty dashboard | dbt refresh failed | Check `dbt logs` for errors; manually re-run dbt |
| Slow load (>10s) | Large DuckDB file | Check `PRAGMA database_size;` and consider partitioning |
| Connection refused | Port conflict | Change `RILL_PORT` in `.env` and restart |
| File not found | DuckDB path misconfigured | Verify `DUCKDB_DATABASE_PATH` in `.env` matches volume mount |

**Resolution Steps**:
1. Identify affected dashboards (check Rill logs)
2. Determine if issue is Rill service or DuckDB database
3. Check if data refresh is running (`docker-compose logs jupyter` for dbt activity)
4. Restart Rill if needed: `docker-compose restart rill`
5. Verify fix: Test dashboard load at http://localhost:9009
6. Document incident with timeline and root cause

**Escalation**:
- If not resolved in 30 min → page on-call database engineer
- If not resolved in 1 hour → page infrastructure lead

---

### 1.2 Data Quality Issues

**Severity**: Medium
**SLA**: 4 hours resolution

**Detection**:
- Automated tests fail during dbt refresh
- Users report data doesn't match expected values
- Unusual distributions in risk scores
- Missing data for recent dates

**Diagnosis**:
```bash
# Check dbt test results (run inside Jupyter container)
docker-compose exec jupyter dbt test --profiles-dir /home/jovyan/work/oss_framework/dbt

# Check data freshness in DuckDB
docker-compose exec jupyter python3 -c "
import duckdb
conn = duckdb.connect('/home/jovyan/data/oea.duckdb')
print('Latest attendance:', conn.execute('SELECT MAX(date) FROM mart_core.fact_attendance').fetchone())
print('Student count:', conn.execute('SELECT COUNT(DISTINCT student_key) FROM mart_core.dim_students').fetchone())
conn.close()
"

# Check for duplicate records
docker-compose exec jupyter python3 -c "
import duckdb
conn = duckdb.connect('/home/jovyan/data/oea.duckdb')
result = conn.execute('SELECT student_key, COUNT(*) as cnt FROM mart_core.dim_students GROUP BY student_key HAVING cnt > 1').fetchall()
print('Duplicates:', result if result else 'None')
conn.close()
"
```

**Resolution Steps**:
1. Identify which dbt model/table is affected
2. Check dbt logs for transformation errors: `docker-compose logs jupyter | grep ERROR`
3. If source data issue: contact data collection team
4. If transformation error:
   - Fix dbt model in `oss_framework/dbt/models/`
   - Re-run: `docker-compose exec jupyter dbt run --select <model-name>`
5. Verify data quality tests pass
6. Alert users once fixed

**Root Cause Analysis**:
- Did data format change in source system?
- Was dbt code modified recently?
- Check git history: `git log --oneline oss_framework/dbt/models/`

---

### 1.3 High Query Latency

**Severity**: Medium
**SLA**: 2 hours resolution

**Detection**:
- Rill dashboards slow to load (>5 seconds)
- Users reporting sluggish interface
- High CPU usage on host machine

**Diagnosis**:
```bash
# Check DuckDB query performance
docker-compose exec jupyter python3 -c "
import duckdb
conn = duckdb.connect('/home/jovyan/data/oea.duckdb')
conn.execute('PRAGMA enable_profiling;')
result = conn.execute('SELECT * FROM mart_core.fact_attendance WHERE school_year = 2024 LIMIT 100').fetchall()
print(conn.execute('PRAGMA last_profiling_output').fetchone())
conn.close()
"

# Check DuckDB file size and fragmentation
docker-compose exec jupyter ls -lh /home/jovyan/data/oea.duckdb

# Check container resource usage
docker stats --no-stream rill jupyter

# Check active queries (if Rill has query log)
docker-compose logs rill | grep -i "query" | tail -20
```

**Common Causes & Solutions**:

| Cause | Solution |
|-------|----------|
| dbt refresh running | Wait for completion; adjust refresh schedule |
| Missing indexes | Review query plan; add indexes if needed |
| Large table scans | Optimize dbt model with filters/partitions |
| Database file bloated | Run `CHECKPOINT` to compact database |
| High concurrent users | Increase Docker container memory limits |

**Resolution Steps**:
1. Identify slow queries (use Rill query logs or DuckDB profiling)
2. Get execution plan: `EXPLAIN <query>`
3. If query inefficient: Optimize dbt model or add indexes
4. If database fragmented: Run `CHECKPOINT` to compact
5. If resource constrained: Increase Docker memory (`docker-compose.yml` resource limits)
6. Re-test query latency

---

### 1.4 dbt Refresh Failure

**Severity**: High
**SLA**: 2 hours resolution

**Detection**:
- dbt run fails (check Jupyter logs)
- Slack notification: "❌ dbt refresh failed" (if configured)
- Data freshness warning (data >24h old)

**Diagnosis**:
```bash
# Check Jupyter container logs
docker-compose logs jupyter --tail=100 | grep -i error

# Run dbt debug manually
docker-compose exec jupyter bash -c "cd /home/jovyan/work/oss_framework/dbt && dbt debug"

# Test specific model
docker-compose exec jupyter bash -c "cd /home/jovyan/work/oss_framework/dbt && dbt run --select <model-name>"
```

**Common Errors & Solutions**:

```
ERROR: Database connection failed
  → Check DuckDB file permissions: ls -l oss_framework/data/oea.duckdb
  → Verify DUCKDB_DATABASE_PATH in .env matches volume mount
  → Check if file is locked by another process

ERROR: Insufficient disk space
  → Check: df -h
  → Clean up old backups in data/backups/
  → Expand disk if needed

ERROR: dbt model parsing failed
  → Check YAML syntax in schema.yml
  → Verify references in upstream models
  → Run: dbt parse

ERROR: Test assertion failed
  → Review test definition
  → Check actual vs expected data
  → Decide if test is correct or data is incorrect
```

**Resolution Steps**:
1. Check logs for specific error message
2. Fix root cause (syntax, data, connectivity, etc.)
3. Re-run refresh: `docker-compose exec jupyter dbt run --full-refresh`
4. Monitor: `docker-compose logs -f jupyter`
5. Verify data freshness once complete
6. Document incident

---

## 2. Maintenance Procedures

### 2.1 Database Backup Verification

**Frequency**: Daily (automated), Manual weekly verification
**Duration**: 15 minutes

```bash
#!/bin/bash
# Weekly backup verification script

echo "=== Backup Verification Report ==="
echo "Date: $(date)"

# List recent backups
echo ""
echo "Recent Backups:"
ls -lht data/backups/*.duckdb | head -10

# Test backup integrity
echo ""
echo "Testing backup integrity..."
LATEST_BACKUP=$(ls -t data/backups/*.duckdb | head -1)

docker-compose exec jupyter python3 -c "
import duckdb
try:
    conn = duckdb.connect('${LATEST_BACKUP}', read_only=True)
    count = conn.execute('SELECT COUNT(*) FROM mart_core.dim_students').fetchone()[0]
    print(f'✅ Backup is valid ({count} students)')
    conn.close()
except Exception as e:
    print(f'❌ Backup corrupted: {e}')
"

# Check backup age
echo ""
echo "Backup Freshness:"
find data/backups -name "oea_backup_*.duckdb" -mtime -1 | wc -l | xargs echo "Backups in last 24h:"

echo ""
echo "=== Verification Complete ==="
```

---

### 2.2 Docker Stack Health Check

**Frequency**: 4x daily
**Duration**: 10 minutes

```bash
#!/bin/bash
# Daily health check script

echo "=== Production Health Check ==="
echo "Timestamp: $(date -Iseconds)"
echo ""

# Container status
echo "CONTAINER STATUS:"
docker-compose ps | grep -v "Up" && echo "⚠️ Non-running containers detected" || echo "✅ All containers running"

# Disk usage
echo ""
echo "DISK USAGE:"
df -h . | grep -E "Filesystem|/$"

# DuckDB file size
echo ""
echo "DUCKDB SIZE:"
du -sh oss_framework/data/oea.duckdb

# Container memory usage
echo ""
echo "MEMORY USAGE:"
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"

# Check Rill accessibility
echo ""
echo "RILL STATUS:"
curl -s -o /dev/null -w "HTTP %{http_code}" http://localhost:9009/ && echo " - Rill accessible" || echo " - ⚠️ Rill not responding"

# Recent errors
echo ""
echo "RECENT ERRORS (Last 10 min):"
docker-compose logs --since=10m 2>&1 | grep -i error | tail -5

echo ""
echo "=== Health Check Complete ==="
```

---

### 2.3 Monthly Maintenance Window

**Frequency**: Last Sunday each month, 2 AM local time
**Duration**: 1-2 hours
**Downtime**: ~30 minutes (planned)

**Procedure**:

```bash
#!/bin/bash
# Monthly maintenance script

set -e

MAINTENANCE_START=$(date -Iseconds)
echo "📋 Starting monthly maintenance at $MAINTENANCE_START"

# 1. Database optimization
echo "1️⃣ Running database optimization..."
docker-compose exec jupyter python3 -c "
import duckdb
conn = duckdb.connect('/home/jovyan/data/oea.duckdb')
conn.execute('CHECKPOINT')
conn.execute('PRAGMA optimize_database')
print('✅ Database optimized')
conn.close()
"

# 2. Create pre-update backup
echo "2️⃣ Creating pre-update backup..."
BACKUP_FILE="data/backups/oea_backup_$(date +%Y%m%d_%H%M%S)_pre_update.duckdb"
cp oss_framework/data/oea.duckdb "$BACKUP_FILE"
echo "✅ Backup created: $BACKUP_FILE"

# 3. Update container images
echo "3️⃣ Updating container images..."
docker-compose pull
docker-compose up -d --force-recreate

# 4. Run dbt refresh
echo "4️⃣ Running dbt refresh..."
docker-compose exec jupyter bash -c "cd /home/jovyan/work/oss_framework/dbt && dbt run --full-refresh"

# 5. Verify system health
echo "5️⃣ Verifying system health..."
./scripts/health-check.sh

# 6. Cleanup old backups (keep last 30 days)
echo "6️⃣ Cleaning up old backups..."
find data/backups -name "oea_backup_*.duckdb" -mtime +30 -delete
echo "✅ Old backups removed"

MAINTENANCE_END=$(date -Iseconds)
echo "✅ Maintenance complete at $MAINTENANCE_END"
echo "Duration: $(( ($(date +%s) - $(date -d $MAINTENANCE_START +%s)) / 60 )) minutes"

# 7. Send notification (if webhook configured)
if [ -n "$SLACK_WEBHOOK_URL" ]; then
  curl -X POST -H 'Content-type: application/json' \
    --data "{\"text\":\"✅ Monthly maintenance completed successfully\"}" \
    $SLACK_WEBHOOK_URL
fi
```

---

## 3. Performance Tuning

### 3.1 Slow Dashboard Performance

**Symptoms**: Rill dashboards taking >5 seconds to load

**Optimization Steps**:

```bash
# 1. Identify slow queries in Rill logs
docker-compose logs rill | grep -E "query|duration" | tail -50

# 2. Analyze query plan in DuckDB
docker-compose exec jupyter python3 -c "
import duckdb
conn = duckdb.connect('/home/jovyan/data/oea.duckdb')
result = conn.execute('EXPLAIN ANALYZE SELECT * FROM mart_core.fact_attendance WHERE school_year = 2024 LIMIT 100').fetchall()
for row in result:
    print(row[0])
conn.close()
"

# 3. Check for missing indexes (DuckDB auto-creates some, but check query plan)
# Note: DuckDB primarily uses columnar storage, not traditional indexes

# 4. Optimize dbt models with materialized tables
# In oss_framework/dbt/models/<model>.sql, add:
# {{ config(materialized='table') }}

# 5. Run CHECKPOINT to compact database
docker-compose exec jupyter python3 -c "
import duckdb
conn = duckdb.connect('/home/jovyan/data/oea.duckdb')
conn.execute('CHECKPOINT')
print('✅ Database compacted')
conn.close()
"

# 6. Monitor improvement
docker-compose logs rill --since=5m | grep "query"
```

---

### 3.2 High Memory Usage

**Symptoms**: Docker containers using >3GB memory, slow queries

**Optimization Steps**:

```bash
# 1. Check memory usage by container
docker stats --no-stream

# 2. Adjust Docker Compose resource limits
# Edit docker-compose.yml:
#   rill:
#     deploy:
#       resources:
#         limits:
#           memory: 2G
#         reservations:
#           memory: 1G

# 3. Restart with new limits
docker-compose down && docker-compose up -d

# 4. Monitor improvement
docker stats --no-stream
```

---

## 4. Data Quality Monitoring

### 4.1 Daily Data Quality Checklist

```bash
#!/bin/bash
# Run daily after dbt refresh

echo "=== Data Quality Report ==="

# 1. Check record counts
docker-compose exec jupyter python3 -c "
import duckdb
conn = duckdb.connect('/home/jovyan/data/oea.duckdb')

tables = ['mart_core.dim_students', 'mart_core.fact_attendance', 'main_main_analytics.v_chronic_absenteeism_risk']
for table in tables:
    count = conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
    print(f'{table}: {count:,} records')

conn.close()
"

# 2. Check for nulls in key columns
docker-compose exec jupyter python3 -c "
import duckdb
conn = duckdb.connect('/home/jovyan/data/oea.duckdb')
result = conn.execute('''
    SELECT COUNT(*) as null_key_columns
  FROM main_main_analytics.v_chronic_absenteeism_risk
    WHERE student_key IS NULL OR school_id IS NULL
''').fetchone()[0]
print(f'Null key columns: {result}')
conn.close()
"

# 3. Check risk score distribution
docker-compose exec jupyter python3 -c "
import duckdb
conn = duckdb.connect('/home/jovyan/data/oea.duckdb')
result = conn.execute('''
    SELECT
        FLOOR(chronic_absenteeism_risk_score / 10) * 10 as score_range,
        COUNT(*) as count
  FROM main_main_analytics.v_chronic_absenteeism_risk
    GROUP BY FLOOR(chronic_absenteeism_risk_score / 10) * 10
    ORDER BY score_range
''').fetchall()
print('Risk Score Distribution:')
for row in result:
    print(f'  {row[0]}-{row[0]+9}: {row[1]:,} students')
conn.close()
"

# 4. Check data freshness
HOURS_OLD=$(docker-compose exec jupyter python3 -c "
import duckdb
from datetime import datetime
conn = duckdb.connect('/home/jovyan/data/oea.duckdb')
max_date = conn.execute('SELECT MAX(created_at) FROM mart_core.fact_attendance').fetchone()[0]
hours = (datetime.now() - max_date).total_seconds() / 3600 if max_date else 999
print(int(hours))
conn.close()
" 2>/dev/null)

if [ $HOURS_OLD -gt 24 ]; then
  echo "⚠️ WARNING: Data is $HOURS_OLD hours old"
else
  echo "✅ Data is current ($HOURS_OLD hours old)"
fi
```

---

## 5. On-Call Procedures

### 5.1 On-Call Escalation

```
TIER 1: Help Desk (1st response, 15 min SLA)
├─ Troubleshoot common issues
├─ Restart Docker containers
└─ Escalate to Tier 2 if unresolved

TIER 2: Data Engineering (1 hour SLA)
├─ Diagnose system issues
├─ Check dbt logs, data quality
├─ Fix dbt models or queries
└─ Escalate to Tier 3 if critical

TIER 3: Infrastructure (1 hour SLA)
├─ Docker host health
├─ DuckDB file corruption recovery
├─ Resource scaling (CPU/memory/disk)
└─ Incident commander decides escalation

INCIDENT COMMANDER:
└─ Called for Critical/P1 issues
    - Rill dashboard down for >30 min
    - Data incorrect/missing
    - Security incident
```

---

### 5.2 Incident Communication Template

```
Subject: [INCIDENT] Analytics Platform - [Issue Summary]
Severity: [CRITICAL/HIGH/MEDIUM/LOW]
Status: [INVESTIGATING/IDENTIFIED/MITIGATING/RESOLVED]

IMPACT:
- Affected users: [number]
- Affected dashboards: [list]
- Duration: [start time to now]

ROOT CAUSE:
[Once identified]

MITIGATION:
[Actions being taken]

ETA:
[Estimated time to resolution]

Next Update: [time in minutes]
```

---

## 6. Disaster Recovery

### 6.1 Database Recovery from Backup

**RTO**: 4 hours | **RPO**: 1 day

```bash
#!/bin/bash
# Database recovery procedure

set -e

BACKUP_FILE=$1  # e.g., data/backups/oea_backup_20260127_030000.duckdb

if [ -z "$BACKUP_FILE" ]; then
  echo "Usage: $0 <backup-file>"
  exit 1
fi

if [ ! -f "$BACKUP_FILE" ]; then
  echo "❌ Backup file not found: $BACKUP_FILE"
  exit 1
fi

echo "🔄 Starting database recovery from: $BACKUP_FILE"

# 1. Stop services
echo "1️⃣ Stopping services..."
docker-compose down

# 2. Backup current database (in case recovery fails)
echo "2️⃣ Creating safety backup of current database..."
if [ -f "oss_framework/data/oea.duckdb" ]; then
  cp oss_framework/data/oea.duckdb "oss_framework/data/oea.duckdb.before_recovery.$(date +%Y%m%d_%H%M%S)"
fi

# 3. Restore from backup
echo "3️⃣ Restoring database..."
cp "$BACKUP_FILE" oss_framework/data/oea.duckdb

# 4. Verify integrity
echo "4️⃣ Verifying database integrity..."
docker-compose run --rm jupyter python3 -c "
import duckdb
try:
    conn = duckdb.connect('/home/jovyan/data/oea.duckdb')
    count = conn.execute('SELECT COUNT(*) FROM mart_core.dim_students').fetchone()[0]
    print(f'✅ Database is valid ({count} students)')
    conn.close()
except Exception as e:
    print(f'❌ Database validation failed: {e}')
    exit(1)
"

# 5. Restart services
echo "5️⃣ Restarting services..."
docker-compose up -d

# 6. Verify services
echo "6️⃣ Verifying services..."
sleep 10
curl -f http://localhost:9009/health && echo "✅ Rill is healthy" || echo "⚠️ Rill not responding"

echo "✅ Database recovery complete"
```

---

## 7. Reference Information

### 7.1 Key Contacts

```
HELP DESK:
  Email: helpdesk@yourdomain.com
  Phone: 1-888-OEA-HELP
  Hours: 7 AM - 6 PM weekdays

ON-CALL ENGINEER:
  Page: https://pagerduty.com/incidents
  Escalation: ops-lead@yourdomain.com

INCIDENT COMMANDER:
  Name: [CIO or Data Director]
  Phone: [phone]
  Email: [email]
```

---

### 7.2 Useful Commands

```bash
# View logs
docker-compose logs -f rill
docker-compose logs -f jupyter
docker-compose logs --since=1h

# Restart services
docker-compose restart rill
docker-compose restart jupyter
docker-compose down && docker-compose up -d

# Access shells
docker-compose exec rill sh
docker-compose exec jupyter bash

# View resource usage
docker stats
docker-compose ps

# DuckDB CLI access
docker-compose exec jupyter python3 -c "import duckdb; conn = duckdb.connect('/home/jovyan/data/oea.duckdb'); conn.execute('.help').fetchall()"

# Run dbt commands
docker-compose exec jupyter bash -c "cd /home/jovyan/work/oss_framework/dbt && dbt run"
docker-compose exec jupyter bash -c "cd /home/jovyan/work/oss_framework/dbt && dbt test"
```

---

## For More Information

- Setup Guide: `docs/SETUP.md`
- Architecture Overview: `docs/ARCHITECTURE.md`
- Rill Dashboard Guide: `docs/RILL_GUIDE.md`
- Security Policy: `SECURITY.md`
- dbt Documentation: `oss_framework/dbt/dbt_project.yml`
- Docker Compose Configuration: `docker-compose.yml`
