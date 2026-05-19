# Archive

This directory contains legacy and unsupported repository material retained for reference only.

## What belongs here

- Azure and Synapse provisioning assets
- legacy Kubernetes deployment assets
- old Postgres, Grafana, Superset, pgAdmin, and Prometheus stack files
- stale source code tied to retired runtime paths
- legacy tests and documentation that do not validate the supported local-first workflow

## Support policy

Nothing under `archive/` is part of the supported product surface.

The supported architecture is the local-first workflow described in the root `README.md`:

`dlt -> DuckDB/dbt -> Parquet export -> Rill`

Files under `archive/` may be historically useful, but they should not be referenced by active onboarding, CI, or deployment paths.
