# Data Deep Dive — Design Spec

**Date:** 2026-06-17
**Branch:** `nl-query-integration`
**Prior commits:** `5827245` (dead code removal), `0951db6` (NL-query + CDE staging)

---

## Goal

Test and validate both data pipelines (CDE and Aeries) and ensure student data anonymization is correct, after significant changes across ingestion, dbt models, and the NL-query layer.

---

## Phase 1: CDE Pipeline Testing

CDE data is aggregate school/district-level — no student PII. Safe to test without privacy prerequisites.

### 1A. Source file inventory

Catalog files in `data/` against the 24 CDE domains in `cde_data_pipeline.py`. For each domain:
- Which source files exist
- File format vs expected format
- Missing domains

### 1B. Pipeline dry run

Run `cde_data_pipeline.py` in discovery mode. Verify:
- Glob patterns match expected files
- File format detection (txt, xlsx, zip with caret-delimited)
- BOM stripping and suppression handling (`*` → null)
- No import errors from deleted `src/` references

### 1C. dbt CDE staging build

Run `dbt build` scoped to CDE staging models (`stg_cde__*`). Verify:
- All 14 new staging models compile
- Source references resolve to actual files/tables
- Schema matches (column names, types, nullability)
- No broken cross-references from the connector framework refactor

### 1D. CDE analytics mart build

Run `dbt build` for `mart_cde_school_accountability` and any CDE-fed downstream models. Verify:
- Joins and aggregations produce results
- Rill models that depend on CDE data still resolve

---

## Phase 2: Aeries Privacy Audit

Aeries is student-level PII. Audit the anonymization pipeline before testing data flow.

### 2A. PII field trace

Trace every student-identifiable field through the dbt DAG:
- Aeries staging: identify PII columns (name, DOB, address, student_id, etc.)
- Core (`dim_students`): what gets hashed, what flows through raw
- Analytics marts: verify no PII leaks into `hex_ready` or aggregation models
- Identify any join key that could re-identify across tables

### 2B. Hash implementation review

Review `oss_framework/dbt/macros/hash_pii.sql` and `hash_pii_secure.sql`:
- Current hash algorithm: MD5 (flagged as weak)
- Salt handling: is `PII_SALT` env var properly consumed?
- Evaluate SHA-256 upgrade path
- Check `dbt_project.yml` vars for hash configuration

### 2C. NL-query schema exposure

Review `nl_query/data_engine.py`:
- Confirmed blocked schemas: `main_privacy_sensitive`
- Exposed schemas: `core`, `analytics`, `cde`
- Verify no view/materialization path circumvents the block
- Check that `dim_students` exposed columns are safe

### 2D. Apply privacy fixes

Any gaps found in 2A-2C get fixed. Likely candidates:
- SHA-256 migration from MD5
- Column-level access control in exposed schemas
- Documentation of privacy guarantees

---

## Phase 3: Aeries Pipeline Testing

Only after Phase 2 fixes are applied.

### 3A. Pipeline code review

Review `aeries_dlt_pipeline.py` for changes from the connector refactor:
- Verify it still works with the `SISConnector` factory
- Check for any deleted `src/` or `aeries_column_mappings.py` references

### 3B. Synthetic data test

Run pipeline in test/synthetic mode:
- Verify connector factory returns `AeriesConnector` without crash
- Verify no `ModuleNotFoundError` on imports

### 3C. dbt Aeries models build

Run `dbt build` for Aeries staging → core → analytics with available data.

---

## Deliverables

Per phase:
- **Phase 1:** CDE pipeline passes end-to-end, dbt CDE models build clean
- **Phase 2:** Privacy audit report + fixes committed
- **Phase 3:** Aeries pipeline runs without import/crash errors, dbt models build

---

## Non-goals

- Adding new CDE domains beyond the 24 already configured
- Connecting to a live Aeries API instance
- Performance optimization of dbt models
- NL-query model retraining or prompt engineering
