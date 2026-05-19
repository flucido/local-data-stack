# Production Deployment Guide - Local Data Stack

## Overview

This document now covers the supported local-first production surface only: a managed host deployment for Stage 1 Parquet data, DuckDB/dbt transformations, and the supported Rill analytics layer.

The repository no longer documents a full multi-service runtime stack here. Historical references to JupyterLab, monitoring add-ons, and large Docker Compose production topologies have been removed because they are archived and not part of the current supported operational path.

---

## Supported Production Shape

- Deploy on a controlled local or on-prem host.
- Persist Stage 1 Parquet data and the DuckDB database on durable local storage.
- Run the local-first runtime that this repository actively supports: Stage 1 ingestion into Parquet, DuckDB raw views plus dbt transformations, optional Parquet export when a downstream consumer needs file output, and Rill as the active analytics application surface.
- Use backups, host-level monitoring, and standard reverse-proxy/network controls that match your environment.

Archived deployment notes may still exist elsewhere in the repository, but they are reference-only and should not be treated as current deployment instructions.

---

## Minimum Readiness Checklist

### Infrastructure

- [ ] Production host provisioned with sufficient CPU, memory, and disk for DuckDB plus Parquet storage
- [ ] Durable local storage configured for the DuckDB database and Stage 1 data
- [ ] HTTPS termination and network access controls configured for the supported application surface
- [ ] Backup destination configured and tested

### Application and Data

- [ ] Repository cloned to the target host
- [ ] `.env` populated with production values
- [ ] Python dependencies installed
- [ ] Initial Stage 1 ingestion completed successfully
- [ ] DuckDB integrity verified before go-live
- [ ] dbt or downstream transformation steps validated if they are part of the deployment

### Operations

- [ ] Rollback procedure documented
- [ ] Backup and restore procedure tested
- [ ] Support ownership assigned
- [ ] Any archived runbooks used during planning are clearly treated as reference-only

---

## Baseline Deployment Flow

### 1. Prepare the host

```bash
git clone <repository-url> /opt/local-data-stack
cd /opt/local-data-stack
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 2. Configure environment

Create a production `.env` with, at minimum, the active local-first paths and credentials required for Stage 1 ingestion, DuckDB/dbt processing, and Rill access.

Example shape:

```bash
DUCKDB_DATABASE_PATH=./oss_framework/data/oea.duckdb
STAGE1_PATH=./oss_framework/data/stage1
AERIES_API_KEY=<production-key>
PRIVACY_SALT=<generated-secret>
```

### 3. Load or refresh data

```bash
source .venv/bin/activate
python3 oss_framework/scripts/run_stage1_ingestion.py
python3 oss_framework/scripts/sync_raw_views_from_stage1.py
```

If your deployment depends on downstream dbt models, the supported handoff is: Stage 1 ingestion writes Parquet, `sync_raw_views_from_stage1.py` refreshes DuckDB raw views over those Parquet files, then dbt runs against DuckDB. Export Parquet after dbt only when a downstream consumer requires file-based outputs.

### 4. Verify local data assets

```bash
duckdb ./oss_framework/data/oea.duckdb "PRAGMA integrity_check;"
python3 -m pytest oss_framework/tests/test_stage1_dlt_pipelines.py -v
```

### 5. Start the supported application surface

Start the supported local-first application surface: keep DuckDB and dbt on the host for data processing, run any required Parquet export step for downstream file consumers, and serve analytics through Rill. Keep the process manager, reverse proxy, and service supervision aligned with your host environment rather than assuming an archived Docker Compose topology.

---

## Backup and Recovery

- Take regular filesystem-level backups of the DuckDB database and Stage 1 Parquet directories.
- Prefer snapshot or copy-on-write backups when available.
- Validate backup restoration on a non-production host before relying on the procedure.
- Keep at least one known-good rollback point before major ingestion or model refreshes.

---

## Security Notes

- Restrict access to the production host and data directories.
- Protect secrets in `.env` and rotate them through your normal operational process.
- Terminate TLS at the approved reverse proxy or ingress layer.
- Apply standard host patching, logging, and least-privilege controls.

See `SECURITY.md` for repository-wide security guidance.

---

## Archived References

- `../archive/legacy-docs/OPERATIONAL_RUNBOOKS.md` is archived/reference-only.

Do not use archived material as the source of truth for current production topology or supported runtime components.

---

## Go-Live Checks

- [ ] Stage 1 ingestion succeeds on the target host
- [ ] DuckDB integrity check passes
- [ ] Backups complete successfully
- [ ] Restore procedure has been tested recently
- [ ] Supported application surface is reachable behind the intended network controls
- [ ] Operational ownership is assigned for incidents and data refreshes

---

**Last Updated**: 2026-05-18  
**Version**: 1.1.0 (local-data-stack)
