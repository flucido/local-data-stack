# Spec: Query History, Comparisons & On-Demand Dashboards

**Status:** DRAFT — for review. Nothing in this document is built.
**Targets:** `product` branch (primary, local-first) and `main` (Space demo, reduced scope)
**Author context:** Captured from design discussion 2026-06-12

---

## 1. Problem Statement

Today, Kasualdad LFED is a single-shot tool: ask a question, get SQL + a table,
and the result evaporates when you ask the next question. Real district/school
workflows are not single-shot:

- An admin runs several related queries and needs to **see them together**
  (e.g., chronic absenteeism by school, then the same filtered to ELL students).
- Districts have a **standard set of questions they always need answered**
  (compliance reporting, board packets, monthly attendance reviews).
- Leadership makes **ad-hoc requests** ("can you pull discipline by grade for
  the board meeting?") that deserve a visual, not a raw table.

Three capabilities fall out of this:

1. **Session query history** — every query in a session accumulates and is revisitable.
2. **Saved results / comparison** — mark specific results to keep and view side by side.
3. **Dashboards** — two flavors:
   - **Standard Dashboard**: a fixed, curated set of recurring queries that
     refresh on demand and render as charts.
   - **Ephemeral Dashboard**: promote any ad-hoc query result into a chart
     on a scratch dashboard, built up during a session.

---

## 2. Goals / Non-Goals

### Goals
- Keep every query of a session visible and restorable (question, SQL, results, timing).
- Let the user mark results as "saved" for side-by-side comparison.
- Render query results as charts (bar/line/scatter/stat-card) without model changes.
- Standard Dashboard: one click re-runs a curated query set and refreshes all charts.
- Ephemeral Dashboard: "push to dashboard" any result; arrange a scratch board.
- Local-first: all persistence is local files (DuckDB/JSON). No cloud dependency.
- Identical core UX on `product` (full) and `main`/Space (session-only subset).

### Non-Goals (this iteration)
- Multi-user accounts, auth, or sharing between users.
- Scheduled/automatic refresh (cron) — refresh is always user-initiated.
- Exports (PDF/PNG/CSV) — note as future work, design must not preclude it.
- LLM choosing chart types (heuristics + manual override instead — no retraining).
- Editing SQL in saved queries (re-run as-is only; editing is future work).
- Real student data ingestion — still operating on the seed schema.

---

## 3. Feature 1: Session Query History

### Behavior
- Every successful `handle_query` run appends a **HistoryEntry** to session state.
- Failed runs (validation errors, model errors) are also recorded, flagged as
  failed — useful to see what didn't work.
- History panel (left column, below examples, or a separate tab) shows entries
  newest-first: `#7 · 09:42 · "chronic absentee ELL students…" · 23 rows · ✅`
- Clicking an entry **restores** its SQL + result table + chart into the main
  output panels (does not re-run; shows the stored result).
- A "Re-run" affordance on each entry executes the stored SQL again (no LLM
  call — SQL is already known; this is fast and deterministic).
- History caps at N entries per session (suggest N=50) — oldest evicted.

### Data model

```python
@dataclass
class HistoryEntry:
    id: str                # uuid4
    timestamp: datetime
    question: str          # natural-language input
    sql: str               # cleaned SQL (post extract_sql)
    columns: list[str]
    rows: list[list]       # result data (capped — see below)
    row_count: int         # true count (rows may be truncated)
    status: str            # "ok" | "validation_error" | "model_error" | "timeout"
    error: str | None
    elapsed_gen_s: float   # LLM generation time
    elapsed_exec_s: float  # DuckDB execution time
    saved: bool            # marked for comparison (Feature 2)
    chart_spec: ChartSpec | None  # set when pushed to dashboard (Feature 4)
```

- **Result size cap:** store at most 500 rows per entry in memory (the UI
  already caps at 1000). Full re-materialization is always possible via re-run.
- Session state container: `gr.State(SessionStore)` where `SessionStore` holds
  `entries: list[HistoryEntry]` plus dashboard state (Feature 4).

### Persistence
- **Space (`main`):** memory only (`gr.State`). Lost on tab close. This is fine
  for a demo and avoids the ephemeral-filesystem problem.
- **Local (`product`):** in addition to session state, append each entry to
  `~/.kasualdad/history.duckdb` (table `query_history`, same fields, rows as
  a JSON column or a separate `history_results` table). On app start, the
  History panel offers "Load previous session" — explicit, not automatic, to
  keep startup predictable.

### Open questions for review
- [ ] Should restoring a history entry overwrite the current main panel, or
      open in a secondary panel? (Spec assumes overwrite — simplest.)
- [ ] Is 50 entries the right cap?
- [ ] Local: auto-load last session vs. explicit "Load previous"? (Spec: explicit.)

---

## 4. Feature 2: Saved Results & Comparison

### Behavior
- Each history entry has a **"★ Save"** toggle. Saved entries:
  - Never evicted by the history cap.
  - Appear in a **Comparison panel** (separate tab or collapsible section).
- Comparison panel renders saved entries as **cards in a responsive grid**
  (2 columns desktop): each card = question, SQL (collapsed accordion),
  result table, and chart (if a chart spec exists).
- No artificial limit of 2 — compare as many as saved, scrolling. (The "A/B
  pin slots" alternative was considered and rejected: the card grid covers
  the 2-item case and scales beyond it.)
- "Unsave" removes from comparison (entry stays in history).
- **Local (`product`):** saved entries persist in `history.duckdb`
  (`saved = true`) and are restored on "Load previous session".

### Comparison affordances (v1 = visual only)
- Cards sit side by side; the human does the comparing.
- Future (explicitly out of scope, design should allow): computed diff when
  two saved results share a column shape ("Lincoln Elementary: 435 → 451, +3.7%").

### Open questions for review
- [ ] Tab ("Compare") vs. collapsible section under results? (Spec: tab —
      keeps the main query flow clean.)
- [ ] Should "Save" prompt for a label/note? (Spec: optional free-text label,
      defaults to the question.)

---

## 5. Feature 3: Charting Layer

The substrate both dashboards and comparison cards build on.

### Chart selection — heuristic, with manual override

No model/prompt changes. A pure function maps a result DataFrame to a chart:

```
infer_chart(df) -> ChartSpec
```

| Result shape | Chart | Example |
|---|---|---|
| 1 row × 1 numeric col | **Stat card** (big number) | "How many students chronically absent?" |
| `school_year` (or other ordinal/temporal col) + 1 numeric | **Line** | enrollment trend |
| 1 categorical + 1 numeric, ≤ ~25 categories | **Bar** (sorted desc) | enrollment per school |
| 1 categorical + 2+ numerics | **Grouped bar** | avg GPA by chronic-absence flag |
| 2 numeric cols | **Scatter** | absences vs GPA |
| Anything else (wide, many text cols, >25 categories) | **Table only** | raw listings |

- Ordinal detection: column named `school_year`/`year`/`term`/`*_date`, or
  values matching `YYYY-YYYY` / date patterns.
- Every chart includes a **chart-type dropdown override** (Auto / Bar / Line /
  Scatter / Table) and x/y column pickers that appear when override is manual.

```python
@dataclass
class ChartSpec:
    kind: str            # "stat" | "bar" | "line" | "scatter" | "table"
    x: str | None
    y: str | list[str] | None
    color: str | None    # optional group-by column
    title: str           # defaults to the question text
    inferred: bool       # False if user overrode
```

### Rendering
- Use **native Gradio plot components** (`gr.BarPlot`, `gr.LinePlot`,
  `gr.ScatterPlot`) — they take pandas DataFrames directly, are interactive
  (tooltips), and need no extra dependencies. Stat card = styled `gr.HTML`
  or `gr.Markdown`.
- Fallback: if a spec can't render (e.g., column vanished after re-run),
  degrade to table + warning, never error.
- Keep matplotlib/plotly out of v1. If custom viz is needed later, `gr.Plot`
  is the escape hatch; nothing in this design blocks it.

### Open questions for review
- [ ] Gradio native plots vs. plotly via `gr.Plot`? Native = zero deps and
      consistent theming; plotly = more chart types (pie, heatmap, dual-axis).
      (Spec: native for v1.)
- [ ] Color palette: derive from the existing ResearchMono theme (#4589FF
      primary). Need a categorical ramp — propose IBM Carbon palette to match
      the IBM Plex typography.

---

## 6. Feature 4a: Standard Dashboard (fixed query set)

The "queries schools always have to have" board.

### Behavior
- A **"Dashboard" tab** with a grid of chart tiles, one per standard query.
- **"Refresh all"** button: runs every standard query **directly as SQL**
  (no LLM — the SQL is pre-authored and versioned), executes via the existing
  `execute_safe()` guard, re-renders all tiles. CPU-only, fast (<1s total).
- Each tile: title, chart, "last refreshed" timestamp, expandable SQL + table.
- Per-tile refresh also available.

### Standard query definitions
- Stored as a **versioned config file** in the repo: `dashboards/standard.json`
  (or `.yaml`). Each item:

```json
{
  "id": "chronic-absence-by-school",
  "title": "Chronic Absenteeism by School",
  "description": "Current-year chronic absence rate per school",
  "sql": "SELECT school_name, ... FROM attendance WHERE ...",
  "chart": {"kind": "bar", "x": "school_name", "y": "chronic_pct"},
  "order": 1
}
```

- Config-as-file means: reviewable in git, district-customizable later
  (a district edits/ships its own `standard.json`), and no DB migration story.
- **Seed set (proposal — review/edit this list):**
  1. Chronic absenteeism rate by school (current year) — bar
  2. Enrollment trend, all years — line
  3. Enrollment by school (current year) — bar
  4. Discipline incidents by school (current year) — bar
  5. Average GPA: chronic vs non-chronic absentees — grouped bar
  6. ELL / SpEd / Econ-disadvantaged counts — grouped bar or 3 stat cards
  7. District total enrollment (current year) — stat card
  8. Suspension days by school — bar

### Refresh semantics
- v1: refresh = re-run against the seeded (deterministic) DB → identical
  results every time on the demo. The value shows when real data arrives
  (product): refresh reflects the latest local data files.
- Refreshed results are **not** auto-added to history (they're not user
  queries). Open question below.

### Open questions for review
- [ ] Should standard-query runs land in history too? (Spec: no — noise.)
- [ ] JSON vs YAML for the config? (Spec: JSON — stdlib, no new dep.)
- [ ] Does the standard set need year-picker parameterization in v1, or
      hardcode "current year" per query? (Spec: hardcode v1; parameterized
      queries are a natural v2.)

## 7. Feature 4b: Ephemeral Dashboard (ad-hoc board)

The "principal asked for something" board.

### Behavior
- After any query, a **"📌 Push to dashboard"** button next to the result.
- Pushing: runs `infer_chart()` on the result, adds a tile to the **"Scratch
  Board"** (second section of the Dashboard tab, or its own tab).
- Tiles on the scratch board can be: re-charted (type override), removed,
  reordered (v1: simple up/down buttons; drag-and-drop is not native to
  Gradio — do not attempt in v1).
- Tiles hold a **snapshot** of the result (like HistoryEntry) plus the SQL,
  so "Refresh tile" re-runs the SQL without the LLM.
- **Space (`main`):** scratch board is session-only.
- **Local (`product`):** "Save board…" persists the tile list (SQL + chart
  specs, *not* result snapshots) to `~/.kasualdad/boards/<name>.json`. A saved
  board re-runs its queries on load — boards are *live definitions*, while
  saved comparisons are *frozen snapshots*. This distinction matters:
  comparisons answer "what did it say then", boards answer "what does it say now".
- A saved scratch board is structurally identical to `standard.json` →
  **"promote to standard"** is just copying tiles into the standard config.
  This is the bridge between the two dashboard flavors and the most
  product-shaped idea in this spec: ad-hoc requests that recur become
  standard reporting, captured from real usage instead of guessed upfront.

### Open questions for review
- [ ] Max tiles on scratch board? (Spec: 12, soft warning after.)
- [ ] Should "push to dashboard" auto-switch to the Dashboard tab? (Spec: no —
      show a toast/status "Added to board (4 tiles)"; stay in query flow.)

---

## 8. UI Layout (proposed)

```
┌──────────────────────────────────────────────────────────────┐
│  🏫 Kasualdad LFED                                           │
│  [ Query ]  [ Compare (3) ]  [ Dashboard ]                    │  ← gr.Tabs
├──────────────────────────────────────────────────────────────┤
│ QUERY TAB                                                     │
│ ┌───────────────┐  ┌────────────────────────────────────┐    │
│ │ question box   │  │ Generated SQL (accordion)          │    │
│ │ [Run Query]    │  │ Chart        ← NEW (auto, override)│    │
│ │ status         │  │ Results table                      │    │
│ │ examples       │  │ [★ Save] [📌 Push to dashboard]    │    │
│ │ ──────────     │  └────────────────────────────────────┘    │
│ │ History  ← NEW │                                            │
│ │  #7 …  ✅ ★    │                                            │
│ │  #6 …  ✅      │                                            │
│ └───────────────┘                                            │
├──────────────────────────────────────────────────────────────┤
│ COMPARE TAB: grid of saved-result cards (q, sql, chart, tbl) │
├──────────────────────────────────────────────────────────────┤
│ DASHBOARD TAB:                                               │
│   Standard Board   [Refresh all]   (tiles from standard.json)│
│   Scratch Board    [Save board…]   (pushed tiles)            │
└──────────────────────────────────────────────────────────────┘
```

- Tabs are the main structural change to `app.py`. Current two-column query
  layout survives intact inside the Query tab.

---

## 9. Architecture & Module Plan

New modules (keeping the existing thin-controller pattern):

| Module | Responsibility | GPU? |
|---|---|---|
| `session_store.py` | `HistoryEntry`, `SessionStore`, save/evict logic; (product) DuckDB persistence | No |
| `charting.py` | `ChartSpec`, `infer_chart()`, spec→Gradio-component mapping | No |
| `dashboards.py` | Load/validate `standard.json`, run query sets via `execute_safe`, board save/load (product) | No |
| `app.py` | Tabs, wiring, callbacks (grows; consider splitting `ui_*.py` if >500 lines) | `handle_query` only |

Key constraints:
- **Only `handle_query` touches the GPU.** History restore, re-run, refresh,
  chart re-rendering, dashboards — all pure CPU/DuckDB. This matters on
  ZeroGPU (no quota burn) and keeps everything else instant.
- Re-run paths bypass the LLM entirely (stored SQL → `execute_safe`).
- `gr.State` is per-session and serialized between events — `SessionStore`
  must be a plain dataclass/dict tree (no DB connections or model handles).
- Existing `data_engine.execute_safe()` is reused unmodified for every
  execution path (user query, re-run, tile refresh, standard refresh).

### Branch strategy
- Build on `product` first (it's the real target and has no ZeroGPU
  constraints to work around), then port to `main` minus local persistence
  (drop `~/.kasualdad/*` writes; everything else is identical).
- Shared core (`session_store.py`, `charting.py`, `dashboards.py`) should be
  written persistence-optional so the port is a config flag, not a fork.

---

## 10. Phasing (suggested build order)

| Phase | Scope | Value unlocked |
|---|---|---|
| **P1** | Session history (record, list, restore, re-run) | Multi-query workflow |
| **P2** | Charting layer (`infer_chart` + chart in Query tab + override) | Visual results |
| **P3** | Save ★ + Compare tab (cards grid) | Side-by-side comparison |
| **P4** | Standard Dashboard (`standard.json`, refresh-all) | Recurring reporting |
| **P5** | Ephemeral Dashboard (push, scratch board, save/load board, promote) | Ad-hoc → standard pipeline |
| **P6** | Local persistence (history.duckdb, boards dir, load-previous-session) | Cross-session memory (product only) |

Each phase is independently shippable and demoable. P1+P2 alone already
transform the feel of the app. P4 and P5 can swap order; P5 depends on P2+P3
machinery, P4 only on P2.

---

## 11. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| `gr.State` payloads get heavy (many entries × 500 rows) | Row cap per entry; consider capping stored rows at 100 for history, full only for saved |
| Gradio native plots can't express a needed chart | `gr.Plot` + plotly escape hatch; ChartSpec is renderer-agnostic |
| Dashboard refresh on Space hits ZeroGPU queue | It doesn't — refresh is SQL-only, no GPU decorator |
| `app.py` becomes a monolith | Split UI builders per tab (`ui_query.py`, `ui_dashboard.py`, …) when it crosses ~500 lines |
| Drag-and-drop expectations for boards | Explicitly v1 = up/down reorder; set expectation in UI copy |
| Schema drift breaks saved SQL / standard queries | Tile refresh failures degrade to error-on-tile, never crash the board; standard.json is versioned with the schema in the same repo |

---

## 12. Decision Log (to fill during review)

- [ ] History restore: overwrite main panel? ____
- [ ] History cap N=50? ____
- [ ] Load-previous-session: explicit? ____
- [ ] Compare: tab vs section? ____
- [ ] Save label prompt? ____
- [ ] Native Gradio plots vs plotly? ____
- [ ] Standard set: approve/edit the 8 seed queries ____
- [ ] Standard refresh in history? ____
- [ ] JSON config? ____
- [ ] Year parameterization deferred? ____
- [ ] Scratch board tile cap 12? ____
- [ ] Auto-switch tab on push? ____
- [ ] Build order P1→P6 approved? ____
