---
id: lfed-architecture
type: architecture-design
status: active
title: "System architecture: warehouse → metrics layer → clients"
parent: lfed-goal
---

## Drivers

Student-level data cannot leave the device; published indicators must not be second-guessed by ad-hoc SQL; and the same YAML files must work on a laptop and in a deployed Rill project. Every boundary below exists because of one of those three.

## Shape

```
source systems          local warehouse                        clients
─────────────           ─────────────────                      ───────
AeRIES SIS  ─┐          ┌───────────────────┐   export      ┌──────────────┐
Excel drops  ├─ dlt ──▶ │ DuckDB: main_core │──────────────▶│ Rill project │
CDE files   ─┘          │ main_analytics    │  parquet      │ models       │
                        │ main_staging      │               │ metrics views│──▶ dashboards
                        │ main_privacy_*    │               │ alerts/apis  │
                        └─────────┬─────────┘               └──────────────┘
                                  │ read-only, guarded
                        ┌─────────▼─────────┐
                        │ nl_query (Gradio) │  ← today: raw marts SQL
                        └───────────────────┘
```

`oss_framework/` owns ingestion and modeling (dlt pipelines + a dbt project). `scripts/` orchestrates and exports. `rill_project/` is BI-as-code over the exported tables. `nl_query/` is the natural-language client. `training/` produces the weights `nl_query/` loads. `lfed-app-architecture` is the client that will absorb `nl_query/` and the dashboards into one surface.

The dependency edges worth knowing, because two of them are file-path couplings rather than imports:

| From | To | Kind |
|---|---|---|
| `scripts/run_pipeline.py` | dlt pipelines + `dbt run` + `scripts/export_to_rill.py` | subprocess / file path |
| `scripts/export_to_rill.py` | `rill_project/data/*.parquet` | writes four `main_analytics.rill_cde_*` views out |
| `oss_framework/cli.py` | `scripts/export_to_rill.py` | loads **by relative file path** — works only inside a checkout |
| `nl_query/data_engine.py` | DuckDB warehouse | read-only connection, guarded |
| `training/generate_pairs.py` | `oss_framework/data/analytics.duckdb`, `nl_query/prompts.py` | read-only + **reads the prompts file by path** to seed schema context |
| `rill_project/models/*.yaml` | `data/*.parquet` | `read_parquet` on the exported files |

## Modules

| Spec | Boundary | Owns |
|---|---|---|
| `lfed-mod-data-framework` | `oss_framework/` | dlt connectors + the dbt project (~66 models); the only writer of the warehouse |
| `lfed-mod-pipeline-ops` | `scripts/` | 4-stage orchestration, the four-view Rill export, CI contract tests |
| `lfed-mod-metrics-bi` | `rill_project/` | the four governed CDE indicators as models, metrics views, dashboards, alerts |
| `lfed-mod-nl-query` | `nl_query/` | the SQL guard, prompt context, inference backend, Gradio surface, eval harness |
| `lfed-mod-training` | `training/`, `models/` | schema-curated pair generation validated by execution; the adapters |
| `lfed-app-architecture` | `lfed_app/` (to create) | the unified local generative-UI surface that absorbs the two client roles above |

Adopted in place as nodes: `lfed-docs-instructions` (the Gate 1–6 rule set), `lfed-docs-phase4a` (the two-path warehouse data model), `lfed-docs-known-issues` (the Gate 4 gap and its resolution).

## Decisions

**Two query paths coexist by design.** `docs/PHASE4A_DATA_MODEL_DESIGN.md` (`lfed-docs-phase4a`) keeps CDE staging tables directly queryable *and* a pre-joined `mart_cde_school_accountability` OBT for dashboard-shaped reads, so a question can be answered without joining twelve staging tables. Today the direct path is blocked at the guard: `main_staging` is absent from `DEFAULT_EXPOSED_SCHEMAS` in `nl_query/data_engine.py` while `nl_query/prompts.py` still advertises `main_staging.stg_cde__*` tables the guard will reject — recorded as unresolved in `lfed-docs-phase4a`. `lfed-app-architecture` narrows this: the *governed* path is a structured query against a metrics view, and raw warehouse SQL is the explicitly-marked fallback, chosen by the server rather than the model — which is what that doc's "future Phase 5 router" was reaching for.

**Privacy suppression lives in the models, not the clients.** dbt enforces k≥5 (`HAVING COUNT(...) >= 5`) when building marts, and CDE exports carry their own `is_suppressed` (`'*'` marker) and `is_small_n` (n<11) flags. Consequence, and a trap for new clients: rows the warehouse dropped cannot be recovered downstream, and nothing in `nl_query/` reports suppression at answer time — the app must surface both regimes rather than imply it applies them.

**The guard is a client-side invariant, not a warehouse capability.** Read-only connections plus schema allowlist, blocked privacy schemas (`main_privacy_sensitive`, anything matching `priv_`), blocked table patterns (`^_dlt`, `pii_lookup`), column-level PII exclusions, forbidden write tokens, `EXPLAIN` validation, a 1000-row cap, and a 10-second watchdog (default; the Gradio app overrides to 30 s). Any new client inherits this module rather than re-implementing it.

**Metrics views are the only definition of a governed indicator.** Rill YAML is the source of truth for labels, measures, formats, and dimension descriptions, so a client that needs metric semantics reads that YAML instead of restating it — the reason the app fetches view metadata at runtime.

**Model identity is not an interface.** `nl_query/model_inference.py` wraps transformers+PEFT behind a class shaped like `llama_cpp.Llama` specifically so the backend can be swapped; the app binds to a SQL-generation contract, not a checkpoint. See `lfed-app-inference`.

## Invariants

- No cloud call in the data path. `dlt`, DuckDB, dbt, Rill, and the model all run locally; `lfed-docs-instructions`' "deploy to Rill Cloud when ready" is an option, never a requirement of the local path.
- No Python-package imports between `oss_framework/`, `nl_query/`, and top-level `scripts/`; `oss_framework/` and `nl_query/` meet only through the DuckDB file. The single cross-module code load is `oss_framework/cli.py`'s file-path exec of `scripts/export_to_rill.py` (dependency table above) — a checkout-only coupling, not an import edge.
- The natural-language client opens the warehouse read-only. Nothing that a model generated may mutate it.
- A dashboard number and a natural-language answer for the same indicator must not be able to disagree, because both resolve through the same metrics view. (`lfed-docs-known-issues` records that today they can.)
- Governance rules are enforced where they can be: privacy joins stay in `main_privacy_sensitive`, which no client is allowlisted to see.

## Out of scope

- Cross-module operational concerns — pipeline scheduling and CI contract tests — stay inside `lfed-mod-pipeline-ops`.
- Superseded surfaces are recorded here once, and not re-listed in the module specs that contain them: `schema/*.json` holds legacy interactive-dashboard card specs — the files themselves are only parse-validated by `scripts/contracts/contract_tests.py`, but their SQL is duplicated into `scripts/contracts/contract_query_manifest.json`, which CI executes against the warehouse, so retiring the legacy `main_analytics.v_*` views breaks the contract-tests job; `oss_framework/dbt/models/exports/rill_*.sql` is a legacy export layer beside the current four `rill_cde_*` views; the repo-root `test_rill_integration.py` (five metrics views that do not exist in `rill_project/metrics/`) and `test_uat.py` (Dash apps on ports 8050–8054 that no longer exist) are archival candidates, while `pyproject.toml`'s `testpaths = ["oss_framework/tests", "."]` still collects them on a bare `pytest`. `docs/superpowers/` and `hackathonDocs/` are history and input, not specs.
- The unified app's process topology, envelope contract, and renderer catalog belong to `lfed-app-architecture`; this document describes only the seam it plugs into.
