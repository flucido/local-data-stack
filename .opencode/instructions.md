# Local Data Stack — Project Instructions

## Project Identity

This is a **local-first, agent-friendly analytics stack** using Rill (BI-as-code)
with DuckDB as the embedded OLAP engine. The project models K-12 education data
with dbt and serves dashboards through Rill Developer / Rill Cloud.

The dashboard layer is aligned with the **California School Dashboard** (CDE
accountability system). Four state indicators are exposed: Chronic Absenteeism,
Suspension Rate, Academic (ELA), and English Learner Progress (ELPI). Each
carries the CDE-pre-computed Status, Change, and Performance Color (Red→Blue)
straight from the CDE downloadable Dashboard data files.

## Core Philosophy

**BI-as-Code.** Every dashboard, metric, and model is defined as YAML + SQL files
in version control. Nothing is GUI-only. This makes the entire analytics stack
readable by AI agents and auditable by humans.

**One metrics layer, many clients.** Measures and dimensions are defined once in
metrics views and consumed by dashboards, AI agents, SQL queries, and external
MCP clients — all resolving the same governed definitions.

**Local-first, cloud-ready.** Develop and verify everything locally with
`rill start`. Deploy to Rill Cloud when ready. The same files work in both
environments. DuckDB embedded locally; MotherDuck or Rill Cloud in production.

**Agent-friendly by design.** YAML definitions, CLI tooling, and Metrics SQL
make this stack naturally consumable by AI agents. Every resource is code an
agent can read, reason about, and edit.

## Project Structure

```
rill_project/
  rill.yaml              # Project config (OLAP engine: duckdb)
  metrics/               # Metrics view YAML files (type: metrics_view)
  dashboards/            # Dashboard YAML files (type: explore or canvas)
  models/                # SQL model definitions
  connectors/            # Data source connector YAML
  data/                  # Local data files (parquet, csv)
  alerts/                # Alert definitions
  apis/                  # Custom API definitions
```

## Development Constraints

### Gate 1: Declarative Only
Everything in `rill_project/` must be defined in YAML + SQL files.
No adding dashboards, measures, or dimensions exclusively through the Rill UI.
The UI is for preview and exploration; definitions live in code.

### Gate 2: Verify Locally First
Before committing any change to `rill_project/`:
```bash
cd rill_project && rill validate   # Must pass with zero errors
rill start                         # Visually confirm dashboards render
```

### Gate 3: No Duplicated Metrics
Every metric is defined exactly once. If the same business concept
appears in two places (e.g., `status_value` in two metrics views),
one must delegate to the other via `parent` or `requires`. The four
CDE Dashboard metrics views each own their indicator's Status/Change/Color
columns — do not recompute these in a second view.

### Gate 4: Agent Queries Use Metrics SQL
AI agents querying data must use Metrics SQL against metrics views,
not raw SQL against underlying tables. This ensures governed, secure
access through the metrics layer.

### Gate 5: Description on Every Resource
Every dimension and measure must have a `description` field.
AI agents cannot infer business meaning from column names alone.

### Gate 6: Deterministic Metrics
Measures must use precise SQL expressions, not natural language
descriptions as their only definition. Use `ai_instructions` for
supplemental context, not as a substitute for SQL.

## Language & Format Standards

- **Dimension/measure names**: `snake_case` (e.g., `chronic_absence_rate`)
- **Display names**: Title Case (e.g., "Chronic Absence Rate")
- **File names**: snake_case (e.g., `chronic_absenteeism_risk.yaml`)
- **Timeseries column**: `_loaded_at` for batch-loaded data
- **OLAP dialect**: DuckDB SQL (standard SQL functions + DuckDB extensions)

## Quality Checklist Per Resource

```
[ ] File is YAML, not GUI-only
[ ] Has description field on metrics view and on each dimension/measure
[ ] display_name uses Title Case
[ ] name uses snake_case
[ ] Measures have format_preset
[ ] Timeseries column specified
[ ] ai_instructions added where domain context helps
[ ] rill validate passes (zero errors)
[ ] rill start renders dashboards correctly
[ ] No duplicated metric definitions

## Metrics SQL Constraints

When writing queries against metrics views, follow these rules:
- No JOINs across metrics views (one metrics view per query)
- No SELECT * (name dimensions/measures explicitly)
- Measure filters use HAVING, not WHERE
- Always include LIMIT for agent-driven queries (default 100)
