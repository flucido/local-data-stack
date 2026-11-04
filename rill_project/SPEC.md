---
id: lfed-mod-metrics-bi
type: module-design
status: draft
title: rill_project — governed metrics views and dashboards
parent: lfed-architecture
depends-on: [lfed-mod-data-framework]
---

## Responsibility

Own the definition of every governed indicator. Four CDE state indicators — Chronic Absenteeism, Suspension, ELA achievement, and English Learner Progress — are declared here as models, metrics views, and dashboards, and this module is the only place those numbers are defined. Gates 1–6 in `lfed-docs-instructions` are this module's rule set.

```
rill.yaml                 olap_connector: duckdb, compiler: rillv1
models/*.yaml             4 materialized models, each read_parquet('data/cde_*.parquet')
metrics/*.yaml            4 metrics views: dimensions, measures, format_preset, descriptions
dashboards/*.yaml         4 dashboards over those views
alerts/*.yaml             data freshness, dbt test failures, pipeline health
apis/api.yaml             API definition
```

## Boundary

- Ingests Parquet exported by `lfed-mod-pipeline-ops` (the four `main_analytics.rill_cde_*` views) and serves dashboards plus Metrics SQL. It does not touch SIS source systems and does not open the warehouse DuckDB directly.
- The Status / Change / Performance-Color columns come **pre-computed from the CDE files**; this module must not recompute them, per Gate 3. Grain of the chronic-absenteeism view is `cds_code × academic_year × student_group × aggregate_level`.
- Governance rules are declared, not enforced by code here: nothing in this module prevents a client from bypassing the metrics views. That enforcement is `lfed-app-architecture`'s job, which is why Gate 4 could be violated without anything failing — see `lfed-docs-known-issues`.

## Known state to fix

- **`apis/api.yaml` is a template, not a working API.** It still holds the scaffold `select measure, dimension from metrics_view` against a view that does not exist. `lfed-app-architecture`'s governed plane depends on a real Rill metrics API surface, so this file is the work item. *(Unconfirmed whether it was ever intended to ship.)*
- No metrics view declares a `timeseries` column, so time-axis behaviour in dashboards and any trend answer depends on `academic_year` as an ordinary dimension. Consequence for the app: a "by year" question is a dimension grouping, not a time series, and the renderer's line/area intents should not imply continuous time.
- `alerts/data_freshness_alert.yaml` references `analytics.fct_student_grades`, a table not in the current warehouse. A stale alert on a local-first stack is worse than no alert: it trains the operator to ignore the alert channel.
- Several dimensions and measures in `metrics/cde_chronic_absenteeism.yaml` (`school_name`, `district_name`, `county_name`, `is_charter`, `is_dass`) carry no `description`, violating Gate 5 — and the app's plane router matches questions against exactly that metadata, so missing descriptions degrade routing, not just docs.

## Consumers

Dashboards for humans; `lfed-docs-known-issues` records the gap between this module's governed surface and the NL→SQL client; `lfed-app-architecture` reads view metadata at runtime and executes every governed query through Rill rather than restating any of it.
