# OSS Framework Docker Setup Guide

## Overview

This Docker Compose configuration provides a complete, production-ready deployment environment for the OSS Framework SIS (Student Information System) data pipeline with integrated analytics dashboards.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│           OSS Framework Docker Network              │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌───────────────┐  ┌─────────────┐  ┌───────────┐ │
│  │  PostgreSQL   │  │   Grafana   │  │ Metabase  │ │
│  │   (5432)      │  │   (3000)    │  │ (3001)    │ │
│  └───────────────┘  └─────────────┘  └───────────┘ │
│         ▲                  ▲               ▲        │
│         │                  │               │        │
│  ┌──────┴──────────────────┴───────────────┴──────┐ │
│  │        Python ETL Pipeline Container          │ │
│  │   (transforms & loads data)                   │ │
│  └──────────────────────────────────────────────┘ │
│         ▲                                          │
│         │                                          │
│  ┌──────┴────────────────────────────────────────┐ │
│  │    Data Volumes (Persistent)                 │ │
│  │  - postgres_data                             │ │
│  │  - grafana_data                              │ │
│  │  - metabase_data                             │ │
│  │  - superset_data                             │ │
│  └──────────────────────────────────────────────┘ │
│                                                     │
└─────────────────────────────────────────────────────┘
```

## Services

### 1. PostgreSQL Database (sis-postgres)
**Port**: 5432  
**Image**: postgres:16-alpine  
**Purpose**: 5-stage data warehouse for SIS data

Features:
- Schema: stage_1 (raw), stage_2a (normalized), stage_2b (privacy-refined), stage_3 (analytics)
- Automatic schema initialization from SQL scripts
- Health checks enabled
- Persistent volume storage

### 2. Python ETL Pipeline (sis-pipeline)
**Container**: sis-pipeline  
**Image**: Built from Dockerfile.pipeline  
**Purpose**: Extract, Transform, Load operations

Features:
- Multi-stage Docker build (minimal footprint)
- Non-root user execution (security)
- Depends on PostgreSQL health check
- Logs volume for debugging
- Data volume for processing

### 3. Grafana (sis-grafana)
**Port**: 3000  
**Image**: grafana/grafana:10.2.0  
**Purpose**: Real-time district overview dashboards

Default Credentials:
- Username: admin
- Password: (from GRAFANA_PASSWORD env var, default: admin)

Pre-configured:
- PostgreSQL data source
- District overview dashboard
- Alerts and monitoring

### 4. Metabase (sis-metabase)
**Port**: 3001  
**Image**: metabase/metabase:v0.48.0  
**Purpose**: Self-service analytics platform

Features:
- User-friendly SQL-free interface
- Pre-loaded questions
- Row-level security support
- H2 embedded database

### 5. Apache Superset (sis-superset)
**Port**: 8088  
**Image**: apache/superset:3.0.0  
**Purpose**: Advanced data visualization and exploration

Features:
- Ad-hoc data exploration
- Custom datasets and metrics
- SQL Lab for power users
- Automatic admin user creation

### 6. pgAdmin (sis-pgadmin)
**Port**: 5050  
**Image**: dpage/pgadmin4:7.8  
**Purpose**: Web-based PostgreSQL management

Default Credentials:
- Email: admin@example.com (from PGADMIN_EMAIL)
- Password: admin (from PGADMIN_PASSWORD)

### 7. Prometheus (sis-prometheus)
**Port**: 9090  
**Image**: prom/prometheus:latest  
**Purpose**: Metrics collection and monitoring

Features:
- Scrapes PostgreSQL metrics
- Time-series data storage
- Alerting rules support

## Quick Start

### Prerequisites

- Docker Desktop (v4.0+) or Docker Engine + Docker Compose (v2.0+)
- At least 4GB RAM available
- 20GB free disk space

### 1. Clone and Setup

```bash
cd oss_framework

cp .env.example .env

docker-compose up -d
```

### 2. Verify Services

```bash
docker-compose ps

docker-compose logs postgres
docker-compose logs grafana
```

### 3. Access Services

| Service | URL | Default Credentials |
|---------|-----|-------------------|
| Grafana | http://localhost:3000 | admin / admin |
| Metabase | http://localhost:3001 | admin@example.com / admin |
| Superset | http://localhost:8088 | admin / admin |
| pgAdmin | http://localhost:5050 | admin@example.com / admin |
| Prometheus | http://localhost:9090 | (no auth) |
| PostgreSQL | localhost:5432 | sis_admin / secure_password_change_me |

### 4. Verify Database Schema

```bash
docker-compose exec postgres psql -U sis_admin -d sis_analytics -c "\dt stage_*.*"
```

## Configuration

### Environment Variables

Edit `.env` to customize:

```bash
Database:
DB_NAME=sis_analytics
DB_USER=sis_admin
DB_PASSWORD=secure_password_change_me

Dashboards:
GRAFANA_PASSWORD=admin_change_me
SUPERSET_SECRET_KEY=dev_key_change_in_production

Pipeline:
LOG_LEVEL=INFO
```

### Custom Database Initialization

Add SQL scripts to `docker/init-db/` with naming convention `NN_description.sql`:
- `00_stage1_raw.sql` - Raw data tables
- `01_stage2a_normalized.sql` - Normalized views
- `02_stage2b_privacy.sql` - Privacy-refined views
- `03_stage3_analytics.sql` - Analytics views

Scripts execute in numerical order on first startup.

## Common Operations

### Start Services

```bash
docker-compose up -d
```

### Stop Services

```bash
docker-compose down
```

### Stop and Remove Volumes (WARNING: Deletes all data!)

```bash
docker-compose down -v
```

### View Logs

```bash
docker-compose logs -f postgres
docker-compose logs -f pipeline
docker-compose logs -f grafana
```

### Access PostgreSQL CLI

```bash
docker-compose exec postgres psql -U sis_admin -d sis_analytics
```

### Run Python Pipeline

```bash
docker-compose exec pipeline python -m pytest tests/ -v
```

### Rebuild Images

```bash
docker-compose build --no-cache
```

## Production Deployment

### Security Checklist

- [ ] Change all default passwords in `.env`
- [ ] Enable SSL/TLS for all services
- [ ] Set `GF_USERS_ALLOW_SIGN_UP=false` in Grafana
- [ ] Configure database backups
- [ ] Set resource limits for containers
- [ ] Use secrets management (Docker Secrets, Vault)
- [ ] Enable audit logging
- [ ] Configure firewall rules

### Persistence

All data is stored in named volumes:
- `postgres_data`: Database files
- `grafana_data`: Dashboard configurations
- `metabase_data`: Metabase settings
- `superset_data`: Superset configurations

### Backup Strategy

```bash
# Backup PostgreSQL database
docker-compose exec postgres pg_dump -U sis_admin sis_analytics > backup.sql

# Backup all volumes
docker run --rm -v sis_postgres_data:/data -v $(pwd):/backup \
  alpine tar czf /backup/backup.tar.gz /data
```

### Resource Limits

Add to docker-compose.yml services:

```yaml
services:
  postgres:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G
```

## Troubleshooting

### PostgreSQL Won't Start

```bash
docker-compose logs postgres
docker volume ls
docker volume rm $(docker volume ls -q)
docker-compose up postgres
```

### Port Already in Use

```bash
# Find process using port
lsof -i :5432

# Change port in docker-compose.yml
ports:
  - "5433:5432"
```

### Out of Memory

```bash
# Check Docker resources
docker stats

# Increase Docker Desktop memory:
- Settings > Resources > Memory
- Set to 6GB+ for production
```

### Pipeline Container Exits

```bash
docker-compose logs pipeline
# Check error messages and database connectivity
```

## Scaling

### Horizontal Scaling

For production, use Kubernetes (see Phase 3.2):

```bash
kubectl apply -f k8s/postgres-deployment.yaml
kubectl apply -f k8s/pipeline-deployment.yaml
```

### Vertical Scaling

Increase PostgreSQL resources:

```yaml
postgres:
  environment:
    POSTGRES_INITDB_ARGS: "-c shared_buffers=4GB -c max_connections=200"
```

## Monitoring

### PostgreSQL Health

```bash
docker-compose exec postgres pg_isready -U sis_admin -d sis_analytics
```

### Container Resources

```bash
docker stats
```

### Prometheus Metrics

- Query: http://localhost:9090
- Targets: http://localhost:9090/targets

## Performance Optimization

### Database

```sql
-- Create indexes
CREATE INDEX idx_enrollments_grade ON stage_1.enrollment(grade_numeric);

-- Vacuum and analyze
VACUUM ANALYZE;

-- Check query plans
EXPLAIN ANALYZE SELECT * FROM stage_1.enrollment;
```

### Docker

```yaml
postgres:
  command: >
    -c shared_buffers=4GB
    -c effective_cache_size=12GB
    -c work_mem=10MB
    -c maintenance_work_mem=1GB
```

## Next Steps

1. **Load Data**: Import SIS data using Python ETL pipeline
2. **Create Dashboards**: Configure Grafana panels
3. **Set Up Alerts**: Configure notification channels
4. **Deploy to Kubernetes**: Use Phase 3.2 manifests
5. **Enable SSL**: Configure HTTPS certificates

## Support & Troubleshooting

For issues:
1. Check logs: `docker-compose logs [service]`
2. Verify connectivity: `docker-compose exec [service] [command]`
3. Review documentation
4. Check GitHub Issues

## Related Documentation

- [Docker Documentation](https://docs.docker.com/)
- [PostgreSQL 16 Docs](https://www.postgresql.org/docs/16/)
- [Grafana Dashboard Docs](https://grafana.com/docs/grafana/)
- [Metabase Guide](https://www.metabase.com/docs/)
- [Superset Documentation](https://superset.apache.org/docs/)
