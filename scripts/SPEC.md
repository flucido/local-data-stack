---
id: lfed-mod-pipeline-ops
type: module-design
status: draft
title: scripts — pipeline orchestration, Rill export, contract tests
parent: lfed-architecture
---

## Responsibility

Run the stack: drive ingestion and modeling end to end, export the governed tables Rill consumes, and hold the CI gate that keeps definitions and queries honest. Top-level `scripts/`, not an installed package.

```
run_pipeline.py            4-stage orchestrator: stage1 dlt (aeries, excel, cde) →
                           stage2 dbt staging → stage3 seeds + mart_privacy + mart_core +
                           analytics marts → stage4 export
export_to_rill.py          the one current export: exactly four main_analytics.rill_cde_*
                           views → rill_project/data/*.parquet
schedule_pipeline.sh       cron wrapper: lock file, 120-min timeout, logs to oss_framework/logs
contracts/contract_tests.py  CI job: parses the five schema/*.json definitions and runs
                           contract_query_manifest.json queries read-only
performance/               benchmark.py, duckdb_indexes.sql (27 manual CREATE INDEX)
anonymize_aeries.py        one-off: reads ~/Desktop/AeRIES test data/, salted SHA-256
```

## Boundary

- `export_to_rill.py` is the **only** writer into `rill_project/data/`, and the list of exported views is the whole governed surface today — four views, four metrics views, four dashboards. If a governed indicator is not exported here, no client can answer it. Partitioning is deliberately disabled (`export_to_rill.py:64-73`), and the old `v_chronic_absenteeism_risk` / `v_wellbeing_risk_profiles` / `v_class_section_comparison` exports are commented out rather than deleted.
- `oss_framework/cli.py` reaches this module by relative file path, which is why the installed console script only works inside a checkout — noted in `lfed-mod-data-framework`.
- `contract_tests.py` only `json.load`s the schema definitions; the SQL inside those cards is never executed. The CI name promises more than the check delivers: only manifest queries actually run.
- `anonymize_aeries.py` and `contracts/run_query_audit_phase2.sh` are one-off local tools with hardcoded personal paths and output directories, kept for provenance. Not product surface.

## Consumers

`lfed-mod-data-framework` is what it drives; `lfed-mod-metrics-bi` is what it feeds. `lfed-app-architecture` inherits `export_to_rill.py`'s four-view list as the ceiling on what the governed plane can answer, and reads `rill_project/metrics/*.yaml` rather than anything here.
