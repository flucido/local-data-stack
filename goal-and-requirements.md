---
id: lfed-goal
type: goal-and-requirements
status: active
title: Local Data Stack (LFED) — goal and requirements
tags: [root, adopted-from-readme]
---

## Goal

Local Data Stack (LFED) puts K-12 school-accountability analytics on an ordinary laptop: district SIS exports and California CDE publication files go into DuckDB through dlt and dbt, governed indicators go into Rill metrics views and dashboards, and a person can ask a question in plain language and get a chart — with no cloud service holding student data and no BI tool standing between them and the warehouse.

## Problem

District accountability questions ("which schools' chronic absenteeism got worse, and how does that line up with EL reclassification?") span CDE downloadable reports and SIS tables that only answer questions the way their publishers designed them to answer. Existing tooling assumes either a cloud warehouse, a fixed dashboard, or a human writing SQL. The data is student-level and re-identifiable, so "upload it and use a hosted assistant" is not an option, and the numbers that count are legally defined indicators with suppression rules — a hand-written query can produce an answer that contradicts the published dashboard.

## Audience

Today: the project author, working the stack end to end on macOS, plus demonstrations of the surface to educators and researchers. District accountability staff and researchers are the intended end users; no external user has run it yet (unconfirmed from files — this is the stated intent in `README.md`, not an observed deployment).

## Driving question

The product bet being tested: **can 2–4B-parameter models running on-device carry a generative-UI analytics product** — generating the query *and* authoring the visualization for each answer — without a cloud call or a workstation GPU? The app that tests this is specced in `lfed-app-architecture`.

The case study that earlier framed this work is explicitly not the driver. Traces and usage logs remain, as product diagnostics and as the evidence base for the question above — not as study instrumentation.

## Capabilities

- **Ingest.** dlt pipelines pull the AeRIES SIS API, import Excel drops, and load CDE pipe-delimited downloadables into Parquet and DuckDB.
- **Model.** A dbt project layers staging → core/features/scoring/analytics marts and a privacy-sensitive schema, pseudonymizes student identifiers, and enforces k≥5 suppression inside the models.
- **Govern.** A Rill project defines four materialized CDE indicators as metrics views with dimensions, measures, and formats, publishes them as dashboards, and carries pipeline-health alerts.
- **Ask.** A local natural-language layer turns a question into SQL using a fine-tuned model, executes it through a read-only guard (allowlisted schemas, blocked privacy tables, SELECT-only, `EXPLAIN` validation, row cap, watchdog timeout), and returns rows, a summary, generated SQL, and CSV.
- **Evaluate.** A gold-SQL eval harness scores a test set against the warehouse; CI runs contract tests over the definition files.
- **Train.** Pair generation that executes every candidate query before keeping it, QLoRA adapters on Modal, and a GGUF export path for Apple Silicon.
- **Generate the interface.** Specified, not yet built: one local app that answers a question with a visualization the model chose — governed numbers resolved through the metrics views, ungoverned ones through marked warehouse queries. See `lfed-app-architecture`.

## Requirements

- **Local by construction.** No cloud calls, no third-party telemetry, agent endpoints bound to loopback. The stack's whole claim is that the data does not leave the machine.
- **Governed numbers come from the metrics layer.** Anything the four CDE indicators can answer is executed as a structured query against a metrics view, not as free-text SQL against a mart. See `lfed-docs-known-issues` for the gap this rule closes.
- **Ungoverned answers are marked.** A warehouse-query answer never looks identical to a governed one: provenance and suppression state are visible in the answer.
- **Small-model budget.** Two local models resident inside one app within roughly 8 GB on a 16 GB machine; the product contract names capability and size class, never a checkpoint.
- **One launch.** The user runs a single command; the warehouse, the metrics layer, the models, and the browser surface come up without the user configuring endpoints, ports, or weights.
- **No result rows in traces.** Trace and usage records capture the question, the generated query, plane, shape, plan acceptance, latency, and rating — not the returned data.

## Non-goals

- Hosted, multi-tenant, or shared deployments; accounts, login, per-school row-level security, and role management in the app surface. Single local user.
- Saved boards, pinned answers, sharing, and anything needing a persistence layer — the first build is a transient ask canvas.
- Packaged `.app`/`.dmg` distribution and non-macOS platform parity.
- Study instrumentation as the reason the app exists: consent tooling, human-review queues, reviewer workflows.
- Retraining the SQL model or choosing the checkpoints; that is `lfed-mod-training`'s work and the app binds to its contract, not its weights.
- A published model-accuracy figure. The eval harness measures against a curated question set on the device; nothing here asserts a generalization claim on real district data.
