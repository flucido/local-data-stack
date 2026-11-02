---
id: lfed-mod-data-framework
type: module-design
status: draft
title: oss_framework — dlt ingestion and the dbt warehouse
parent: lfed-architecture
---

## Responsibility

Turn source-of-record data — the AeRIES SIS API, Excel drops, and California CDE pipe-delimited downloadables — into a DuckDB warehouse of modeled tables, and define the privacy rules that the modeling enforces. This is the only module that writes the warehouse.

`oss_framework/` is also the pip-installable half of the repo (`pyproject.toml` ships `oss_framework*` and the `export-to-rill` console script) and carries `package_templates/example_sis_package/`, the blueprint for generating a new SIS connector package. That dual identity — LFED's own data layer *and* a reusable framework template — is why the directory nests `utilities/oss_framework/`.

## Layers

```
connectors/    SISConnector base + canonical schema + aeries mapping
pipelines/     dlt: aeries_dlt_pipeline, excel_imports_dlt_pipeline,
               cde_data_pipeline, aeries_to_parquet   → stage1 Parquet
dbt/           66 models: staging/{aeries,cde} → mart_core, mart_features,
               mart_scoring, mart_analytics, mart_privacy, exports/
metadata/      7 CSV attribute/pseudonymization tables read by MetadataManager
config/        duckdb_config.get_production_connection() — memory cap, threads
data/          stage1/2/3 placeholders + analytics.duckdb (gitignored)
tests/         stage1 dlt, transformations, batch, education validation,
               public-release sanitization
```

## Boundary

- Writes to `oss_framework/data/analytics.duckdb` (dbt profile default, `DUCKDB_DATABASE_PATH` overridable) and to `data/` Parquet. Nothing outside this module may write the warehouse; readers open it read-only.
- **Never** imports `nl_query/` or top-level `scripts/`. `cli.py:39-49` reaching `scripts/export_to_rill.py` by *relative file path* is the one exception and a known wart: the installed console script only works inside a checkout, because the wheel ships no `scripts/`.
- `oss_framework/scripts/` holds twelve Week-1 pre-dlt one-offs (orchestrator, raw-view sync, `stage1_generate_sample_parquet`). They are referenced only by historical docs and are not imported by the dlt pipelines. Treat as archival.

## Decisions and defects to know

- **k≥5 lives in models.** `check_k_anonymity` is defined as a macro and referenced by no model yml; enforcement is instead `HAVING COUNT(...) >= 5` inside `mart_core/core/dim_student_demographics.sql:48` and `fact_attendance_daily.sql:54`. Groups below five are dropped upstream, so no client downstream can count them or report them as suppressed. A generic `test_k_anonymity.sql` exists alongside.
- **`cde_data_pipeline` default data dir disagrees with its docs**: `cde_data_pipeline.py:209` uses `CDE_DATA_PATH` or `data/raw`, while `data/cde_raw/README.md` documents `data/cde_raw/` as the drop folder. Unconfirmed which the owner intends; either way the mismatch is a silent-empty-ingest trap.
- `mart_analytics/exports/rill_*.sql` is a legacy export layer (see `lfed-architecture` Out of scope) that still refs `v_*` views the current export path no longer ships.
- Training dependencies are undeclared: pair generation pulls `dspy`, `modal`, and `vllm` lazily and none appear in `pyproject.toml`. See `lfed-mod-training`.

## Consumers

`lfed-mod-pipeline-ops` drives it, `lfed-mod-nl-query` and `lfed-app-architecture` read the warehouse through the guard, `lfed-mod-metrics-bi` consumes the four exported `rill_cde_*` views as Parquet. The data model itself — staging-table-direct-query plus the `mart_cde_school_accountability` OBT — is owned by `lfed-docs-phase4a`.
