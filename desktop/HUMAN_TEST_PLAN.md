# Desktop Human-Use Test Plan — Real Query Engine

A repeatable, scored manual test script for the native desktop app's **model-backed query
engine**: you type plain-English questions, the two-hop agent loop generates SQL with the
local LFM3 model, executes it against DuckDB, and renders a Generative UI workspace.

- **Who runs it**: a human at the app window (black-box; no devtools needed).
- **How long**: core run ≈ 15–20 minutes.
- **Output**: a dated results log (template at the bottom) so runs are comparable across
  models and releases.

## Scope

**In scope**
- The real query engine: free-text questions → `run_prompt` → local SLM → Hop 1 SQL →
  self-healing retries → Hop 2 UI binding.
- Fallback behavior when the model server is unreachable (Demo Mode).
- Desktop interaction regression: presets, inspector, filters, table, CSV export.

**Out of scope (non-goals)**
- Automated tests (`cargo test`, `npm --prefix desktop/ui run test` cover those).
- Model quality benchmarking — this measures the *integrated desktop experience*, not
  the model in isolation (the in-process holdout eval does that).
- Latency benchmarking beyond the on-screen Response time pill.

**Design rationale.** Two shapes were considered: a one-time exploratory sweep and a
repeatable scored script. We chose the repeatable script — it is more useful before
releases and against future model swaps — with a curated core (12 tasks) drawn from the
repo's own held-out evaluation questions, plus an optional extended run of all remaining
holdout questions.

## How the engine works (grounding)

```
Question typed → window.sendRustRpc({cmd: "run_prompt"})
  → BM25 top-5 schema pruning (20-table catalog from training/training_schema.json;
    categorical/year columns grounded with live DuckDB sample values)
  → Hop 1: model emits JSON tool call execute_duckdb_query (GBNF-constrained)
  → DuckDB executes (in-memory medallion engine; up to 2 self-healing retries)
  → Hop 2: model emits render_workspace_ui with 1–4 components bound to result columns
  → arrow:// stream → workspace renders
```

- **Model server**: `llama-server` on `127.0.0.1:8080` serving
  `models/lfed-lfm3-1.7b-two-hop-Q8_0.gguf` (full fine-tune of LFM3-1.7B on 3,000
  two-hop K-12 trajectories; temperature 0, GBNF grammar, 384-token budget per hop).
- **Zero Network Egress**: only loopback plain-HTTP endpoints are accepted. Anything
  else (https, non-loopback host) falls back to the keyword-stub backend and the Demo Mode badge.
- **Local data reality**: the catalog advertises 20 tables (`main_core`,
  `main_analytics`, `main_staging`). The in-memory engine materializes the bronze sample
  (8 students, 16 school-summary rows, 10 equity rows, 7 accountability rows) plus
  privacy-filtered copies of populated warehouse tables. SQL that references a
  catalog table which is not materialized locally will fail with a Binder/Catalog
  error — **that is a legitimate outcome to record, not a setup problem**.

**Baseline expectations.** The in-process holdout eval of this model family (30
questions, bf16, `training/holdout_results.json`): 4/30 SQL executed first-pass,
4/30 after self-healing, 5 hard errors, 25/30 valid Hop-2 UI layouts. Expect a realistic
mix of clean answers, retries, and visible failures. The point is to measure the
desktop-integrated reality, not to demand all-pass.

## Setup (unscored checklist)

```bash
# 1. Start the model server (from repo root)
llama-server -m models/lfed-lfm3-1.7b-two-hop-Q8_0.gguf \
  --host 127.0.0.1 --port 8080 -c 8192 -ngl 99 --alias lfed-two-hop

# 2. Confirm it is healthy
curl -sf http://127.0.0.1:8080/health && echo " ok"

# 3. Build the webview bundle (skip if desktop/ui/dist is already current)
npm --prefix desktop/ui run build

# 4. Launch the desktop app
cargo run --manifest-path desktop/Cargo.toml
```

**A1 — Server up.** `/health` returns 200 within a few seconds of launch.

**A2 — App up.** The window *District Student Analytics Workspace* opens (~1360×860)
and the first starter report (*Multi-Year School Enrollment*) auto-loads with data
(`Records shown` > 0 in the header).

**A3 — Real engine confirmed live.** Type any question from B1–B8 and press **Get
answer** (⌘/Ctrl+Enter also submits). You are on the real engine when all three hold:

1. The answer takes **seconds** (Response time pill shows ~1,500–15,000 ms). An
   instant (< 500 ms) answer means the keyword stub answered, not the model.
2. **No "Demo Mode (Offline Sample Assistant)" badge** appears in the header.
3. The SQL under **Show technical details** is *not* one of the four canned queries
   and varies when you rephrase the question.

> Troubleshooting: if the Demo Mode badge appears unexpectedly, check `/health` first;
> then check that `LFED_SLM_ENDPOINT` is unset or a loopback `http://` URL — any other
> value is rejected on purpose and falls back to Demo Mode.

## Scoring rubric

Record **one row per task** in the results log: task id, the question typed, result,
latency (from the Response time pill), rows (from Records shown), notes.

- **Pass** — a workspace renders with rows > 0; the SQL in the inspector is read-only
  (`SELECT`/`WITH`); every column referenced by the Layout Specification appears in the
  Result Summary columns; the answer plausibly addresses the question.
- **Partial** — any of: succeeded only after self-healing (Response time elevated,
  typically > 6,000 ms, or the answer eventually rendered after visible delay); rendered
  with 0 rows for a question that implies data; the SQL answers a *different* question
  than asked; a scalar answer rendered in an awkward component.
- **Fail** — the red error banner appears (e.g. "SQL execution failed after 2
  self-healing retries: …"), no workspace renders, components are empty, or the SQL is
  not read-only.

Robustness tasks (X-group) have their own inverted criteria — see each task.

## Core tasks

### B. Held-out query tasks (the real engine)

Type each question **exactly** as quoted. For each: watch the header pills, open
**Show technical details** to review the SQL and layout, and check the rendered
workspace before scoring.

#### B1 — Aggregate by group
- **Type:** `What is the average GPA by race/ethnicity in 2023-2024?`
- **Exercises:** grouped aggregate; pruner should select the equity tables.
- **Likely SQL:** `AVG(gpa)` grouped by race on `main_analytics.equity_by_race` or
  `v_equity_outcomes_by_demographics`.
- **Expect:** a category chart or table with one row per racial group; FilterBar
  multi-select on the race column.

#### B2 — Conditional across facts
- **Type:** `What's the average attendance rate for students with at least one suspension in 2023-2024?`
- **Exercises:** joining discipline and attendance facts; WHERE on a count/flag.
- **Likely SQL:** `main_core.fact_discipline` joined to `fact_attendance` /
  `dim_students`.
- **Expect:** either a scalar KPI (single number), or a self-healing sequence if the
  discipline fact table is not materialized locally — record which happened.

#### B3 — Multi-year trend
- **Type:** `How has chronic absenteeism changed from 2021-22 to 2023-24?`
- **Exercises:** temporal comparison across academic years.
- **Likely SQL:** year-filtered aggregate on `main_analytics.mart_cde_school_accountability`
  or `main_staging.stg_cde__chronic_absenteeism`.
- **Expect:** a time-series chart with `academic_year` on the X axis.

#### B4 — Categorical bucketing
- **Type:** `Categorize students by attendance rate: 'Severe' (<80%), 'At Risk' (80-90%), 'Satisfactory' (>90%) for 2023-2024`
- **Exercises:** CASE expression construction.
- **Likely SQL:** `CASE` buckets over `main_core.fact_attendance`, grouped.
- **Expect:** a category breakdown (bar chart or table) with the three labeled buckets.

#### B5 — Reporting-category domain
- **Type:** `What are the total suspensions and suspension rates by reporting category across schools in 2023-24?`
- **Exercises:** CDE reporting-category vocabulary; the same domain the keyword stub
  hard-coded.
- **Likely SQL:** grouped aggregate on `main_analytics.mart_cde_school_accountability`
  (`reporting_category_label`).
- **Expect:** one row per reporting category, two measures.

#### B6 — Deliberately vague
- **Type:** `How are our students doing?`
- **Exercises:** graceful handling of an underspecified question.
- **Expect:** *any* sane overview answer (school summary, attendance, GPA). Score Pass
  if the answer is a defensible interpretation with data; Partial if the answer is
  technically valid but obviously unrelated; record what it chose.

#### B7 — Scalar statistic
- **Type:** `What attendance rate puts a student in the bottom quartile in 2023-2024?`
- **Exercises:** percentile/quantile SQL; single-row result.
- **Likely SQL:** `QUANTILE`/`PERCENTILE` over `main_core.fact_attendance`.
- **Expect:** a one-row, one-value result rendered as a KPIGrid.

#### B8 — Explicit table reference
- **Type:** `Show active student counts and average age by grade level from dim_student_demographics`
- **Exercises:** following an explicit table name in the question.
- **Likely SQL:** aggregate on `main_core.dim_student_demographics`.
- **Expect:** valid SQL naming that exact table. If the table is not materialized
  locally, watch the self-healing path and record the outcome.

### K. Keyword-route parity (4 quick tasks)

The deterministic stub answered four canned scenarios by keyword. With the real engine
running, these same asks go to the model — this group checks the real engine covers at
least the stub's territory. Type each, score each.

| # | Type this | The stub's canned answer was |
|---|-----------|------------------------------|
| K1 | `Show school enrollment, GPA and attendance trends by year` | school_summary multi-year table |
| K2 | `Compare equity outcomes by race` | equity_by_race table |
| K3 | `Show CDE subgroup accountability rates` | accountability chronic-absent + suspension table |
| K4 | `What is the average attendance rate for English Learners in 2023-2024?` | EL-filtered attendance average |

**Expect:** each answer addresses the scenario (even if the SQL differs from the canned
version). Latency in seconds, no Demo Mode badge.

## Edge cases

#### X1 — Gibberish (robustness)
- **Type:** `asdfgh qwerty zxcv`
- **Exercises:** grammar-forced tool call on nonsense; the failure path.
- **Pass criteria (inverted):** the app stays responsive and ends in a *readable*
  outcome — either a red error banner after self-healing retries, or a workspace with
  whatever the model produced. **Fail only if** the app hangs, crashes, or shows a raw
  unhandled error. Record which outcome occurred.

#### X2 — Off-domain question (robustness)
- **Type:** `What is the capital of France?`
- **Exercises:** the model cannot refuse; the GBNF grammar forces a warehouse tool call.
- **Pass criteria (inverted):** same as X1 — a clean, readable outcome; no hang or
  crash. Record what the engine did with an unanswerable question.

#### X3 — Empty input (UI guard)
- **Action:** with the question box empty (or whitespace-only), confirm **Get answer**
  stays disabled. Type a real question; it enables. No scoring — just note ✓/✗.

## Fallback and recovery

#### F1 — Server-down fallback, then recovery
1. Stop llama-server (Ctrl-C its terminal, or `kill <pid>`).
2. In the app, ask: `Show enrollment for each school`
3. **Expect:** the **Demo Mode (Offline Sample Assistant)** badge appears in the
   header, the answer is instant (canned enrollment SQL), and the SQL in the inspector
   is the canned multi-year query.
4. Restart llama-server (setup command, step 1). Wait for `/health` to return 200.
5. Ask the same question again.
6. **Expect:** the Demo Mode badge is gone, latency returns to seconds, and the SQL
   differs from the canned query.
- **Pass:** both halves behave as described. **Partial:** fallback works but recovery
  does not (or vice versa). **Fail:** neither.

## Interaction regression (model-independent)

#### R1 — Starter reports
- **Action:** click all three preset buttons — *Multi-Year School Enrollment*,
  *Equity Outcomes by Race*, *CDE Subgroup Accountability*.
- **Pass:** each renders a workspace with rows > 0 and the `Records shown` pill
  updates; the selected button stays highlighted; answers are instant (these bypass
  the model).

#### R2 — Technical details inspector
- **Action:** with any result open, toggle **Show technical details**.
- **Pass:** the drawer shows three labeled blocks — *Generated SQL Query*,
  *Result Summary*, *Layout Specification* — as formatted JSON, and toggling hides it
  again.

#### R3 — Zero-LLM filter latency
- **Action:** on the *Multi-Year School Enrollment* preset, change a FilterBar control
  (e.g. click a school pill or adjust a range).
- **Pass:** the view updates immediately, the filter area shows **Updated in <N>ms**
  with N < 15, and `Records shown` changes to the matching row count.

#### R4 — Data table interactivity
- **Action:** in the DataTable, click a column header to sort (click again for the
  opposite direction); then click **Download CSV**.
- **Pass:** rows re-sort both directions; a `school_data_export.csv` file downloads
  containing the visible rows and columns.

## Optional extended run

The remaining 22 held-out questions (`training/holdout_traces.jsonl`). Same rubric, one
row each. Run these when you want a fuller quality picture (≈ 5–10 minutes).

<details>
<summary>Extended question list</summary>

1. For English Learners, what's the relationship between attendance rate and GPA in 2023-2024?
2. What is the average GPA for students with 3 or more discipline incidents in 2023-2024?
3. Show enrollment for each school across the last 3 years
4. Has average GPA improved from 2022-2023 to 2023-2024?
5. Group students by GPA: 'Honor Roll' (3.5+), 'On Track' (2.0-3.4), 'Below' (<2.0) for 2023-2024
6. Which students are both chronically absent AND failing (GPA below 2.0) in 2023-2024?
7. Show chronic absenteeism rates, excluding suppressed data, for 2023-24
8. For All Students: chronic absent rate, suspension rate, and SBAC proficiency in one query for 2023-24
9. What is the average chronic absenteeism by county for 2023-24?
10. Which schools reported physical restraints in 2023-24?
11. Top 3 schools with highest chronic absenteeism in each county for 2023-24
12. Which schools have the highest percentage of high-risk students?
13. Show the suspension rate gap between Black and White students
14. Which schools had zero suspensions in 2023-24?
15. Show student count and average chronic absenteeism risk score by risk level in 2023-2024
16. Compare average GPA and percentage with good attendance by race/ethnicity for English Learners
17. Which districts had the highest free meal eligibility percentage in 2023-24?
18. Show total homeless student enrollment and doubled-up housing counts by county in 2023-24
19. What is the average CAASPP mean scale score and standard met/exceeded percentage by subgroup in 2023-24?
20. Compare school-level average GPA, attendance rate, and high-risk percentage across all schools in school_summary
21. How many discipline incidents and total suspension days occurred by incident type and severity in 2023-2024?
22. Compare chronic absenteeism rates across academic years for English Learners vs Socioeconomically Disadvantaged students

</details>

## Results log template

Copy this into `desktop/test-runs/YYYY-MM-DD-<tester>.md` and fill it in during the run.

```markdown
# Desktop human test run — YYYY-MM-DD

- Tester: <name>
- Model: models/lfed-lfm3-1.7b-two-hop-Q8_0.gguf
- llama-server: <version> — flags: -c 8192 -ngl 99 (port 8080)
- App commit: <git rev-parse --short HEAD>
- Mode confirmed real (A3): yes/no

| Task | Question (short) | Result | Latency (ms) | Rows | Notes |
|------|------------------|--------|--------------|------|-------|
| B1   | avg GPA by race  | Pass   | 4,120        | 10   | chart + filter rendered |
| ...  |                  |        |              |      |       |

## Summary
- Pass / Partial / Fail: X / Y / Z (core)
- Failure types seen (from error banner text): BinderError / Parser / Catalog / other
- Overall impressions:
```

When the run is complete, tally the failure **error types** — Binder/Catalog errors point
at schema-pruning or table-materialization gaps; Parser errors point at training data;
clean-but-wrong answers point at prompt/context issues.
