---
id: lfed-docs-known-issues
type: architecture-design
status: draft
title: "Known issue: the NL-to-SQL layer bypasses the metrics views"
parent: lfed-architecture
depends-on: [lfed-mod-nl-query, lfed-mod-metrics-bi]
tags: [adopted, gate-4, governance]
---

# Known Issue: NL-to-SQL Model Does Not Know About Rill Metrics Views

> **Adopted as a spec node** — this is the owning record for the Gate 4 gap. Content is the
> original, unedited, except the *Resolution* section below, which corrects what has since been
> decided. `status: draft` until the owner reviews it.

## Status

**Open** — documented 2026-06-23. Not blocking the current integration
but must be addressed before the NL-to-SQL layer is considered fully
integrated with the Rill dashboards.

## Background

The project instructions (`.opencode/instructions.md`, Gate 4) state:

> AI agents querying data must use Metrics SQL against metrics views,
> not raw SQL against underlying tables.

The current NL-to-SQL model was trained on raw DuckDB tables:
- `main_core.dim_students`, `main_core.fact_attendance`, etc.
- `main_analytics.mart_cde_school_accountability`
- `main_staging.stg_cde__*`

It does NOT know about Rill metrics views:
- `rill_project/metrics/cde_chronic_absenteeism.yaml`
- `rill_project/metrics/cde_suspension.yaml`
- `rill_project/metrics/cde_ela.yaml`
- `rill_project/metrics/cde_elpac.yaml`

## Impact

The model generates raw DuckDB SQL that bypasses the governed metrics
layer. This means:
1. Metric definitions could diverge between the model's SQL and the
   Rill metrics view definitions.
2. No row-level security or access control from the metrics layer.
3. Dashboard and NL-to-SQL results may disagree for the same question.

## Options to Resolve

1. **Prompt engineering only** — Add Rill metrics view schemas to the
   prompt and instruct the model to use Metrics SQL. Low effort, but
   the model was not trained on Metrics SQL syntax.

2. **Retrain with Metrics SQL pairs** — Generate new training pairs that
   use Metrics SQL against the Rill metrics views. Higher effort, but
   produces a model that natively speaks the governed layer.

3. **Translation layer** — Keep the model generating raw SQL, but add a
   post-processing step that maps raw SQL to equivalent Metrics SQL.
   Complex and brittle.

## Recommendation

Option 2 (retrain) is the right long-term path, but only after the eval
harness is in place so we can measure the improvement. This should be a
follow-up plan after the current integration is complete.

## Resolution (decided later, supersedes the options above)

None of the three options was taken. `lfed-app-architecture` closes the gap at the
server instead of at the model: a plane router decides whether a question is answerable
from a metrics view, and for governed questions the model emits a **structured metrics
query** — view, dimensions, measures, filters, order, limit — whose value sets are the
view's own metadata, executed by Rill. The model never writes Metrics SQL and never picks
the plane, so a governed answer cannot drift from the dashboard by construction. Questions
the router cannot resolve fall to raw marts SQL, visibly marked as ungoverned.

Two consequences for this record:

- Retrain toward Metrics SQL is **not** required for the app, and is no longer the
  blocking path. It stays `lfed-mod-training`'s option, not the frontend's dependency.
- The eval harness this document makes a precondition now has a governed-plane mode
  (`lfed-mod-app-diagnostics`) that scores governed-versus-marts agreement — which is
  the measurement Option 2 was waiting for, running without the retrain.

## References

- `.opencode/instructions.md` — Gate 4
- `rill_project/metrics/` — the four metrics views the model should learn
- `training/generate_pairs.py` — the training data generator (would need
  a Metrics SQL mode)
