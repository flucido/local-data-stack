---
id: lfed-mod-nl-query
type: module-design
status: draft
title: nl_query — guarded NL→SQL client and its Gradio surface
parent: lfed-architecture
depends-on: [lfed-mod-training, lfed-mod-data-framework]
---

## Responsibility

Let a person ask a question in plain language and get warehouse rows back, without ever letting a model write to the database or see a re-identification key. Flat package, no subpackages: `app.py` (Gradio UI), `data_engine.py` (connection + guard), `model_inference.py` (backend), `prompts.py` (context), `ui_strings.py` (copy), `eval.py` (harness), `tests/`.

The guard in `data_engine.py` is the artifact this module is really for; the Gradio surface is scaffolding around it and is superseded by `lfed-app-architecture`.

## The guard, as built

```
warehouse path   LFED_WAREHOUSE_DB → data/warehouse.duckdb → oss_framework/data/analytics.duckdb
exposed schemas  core, main_core, analytics, main_analytics, cde, main_cde   (LFED_EXPOSED_SCHEMAS overrides)
blocked schemas  main_privacy_sensitive, information_schema, pg_catalog,  plus any /\bpriv_/
blocked tables   /^_dlt/, /pii_lookup/i
PII columns      dim_students: names, DOB, student_id, ssn, email, phone, address
FORBIDDEN_TOKENS drop delete insert update alter truncate create attach detach pragma
validation       static checks → schema-aware EXPLAIN against the live warehouse
execution        read-only conn, wrapped SELECT * FROM (<sql>) AS _safe LIMIT 1000,
                 watchdog thread calling conn.interrupt() after 10s (default)
```

- **`EXPLAIN` is the real validator.** Forbidden tokens catch intent; `EXPLAIN` catches invented columns and tables, and it is schema-aware because the connection is live.
- **`app.py` overrides the 10-second default to 30 seconds** at execution (`app.py:221`). Anything that inherits `execute_safe` gets 10 s unless it passes its own timeout — a discrepancy the app layer must decide about deliberately rather than inherit by accident.
- **`get_schema_info()` introspects live**, dropping blocked/unexposed schemas, `_dlt*` and pii tables, and PII columns; the static `DEFAULT_SCHEMA` in `prompts.py:66-223` is used only when introspection fails.

## Known drift

- `prompts.py` advertises `main_staging.stg_cde__*` and its system prompt instructs the model to use CDE staging tables, but `main_staging` is **not** in `DEFAULT_EXPOSED_SCHEMAS`. Either the model is being pointed at tables the guard will reject, or the allowlist is missing an entry. Unconfirmed; `lfed-docs-phase4a` expected staging to be visible.
- The metrics views the governed plane is made of appear nowhere in the prompt or schema context — the substance of `lfed-docs-known-issues`.
- `model_inference.py` is transformers + PEFT only (base `unsloth/qwen2.5-coder-14b-instruct-bnb-4bit`, adapter resolved from `LFED_ADAPTER_REPO` → `models/lora-warehouse-r64/` → HF id). The header says the llama.cpp backend was *removed* because it could not reach ZeroGPU's PyTorch-only CUDA emulation, yet `llama-cpp-python` is still declared in the `nl-query` extra and `ui_strings.py:120` tells users a GGUF/llama.cpp option exists. Documented capability, absent implementation.
- No suppression reporting at answer time: k≥5 is applied upstream in dbt (`lfed-mod-data-framework`) and CDE's own `is_suppressed` flag is a column, so a Gradio answer can present a group that was silently dropped.

## Boundary

- Never imports `oss_framework/`; meets the warehouse as a DuckDB file.
- Opens every connection read-only. `create_session()` hard-codes it.
- Retires when `lfed-app-architecture` reaches parity; until then it stays the reference surface and its guard tests stay the contract for anything that executes generated SQL (`tests/test_execution_guard.py`, `test_data_engine.py`, `test_gradio_e2e.py`, `test_model_inference.py`, `test_eval_harness.py`).

## Consumers

`lfed-mod-training` seeds its prompt context from `prompts.py`. `lfed-app-architecture` inherits this module's guard and eval harness rather than reimplementing either.
