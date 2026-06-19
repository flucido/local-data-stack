---
name: rill-dashboards
description: Create and edit Rill dashboard YAML files (Explore and Canvas). Use when building
  dashboards in rill_project, defining explore views, configuring canvas dashboards with widgets,
  setting dashboard defaults/filters/themes, or deploying dashboards. Triggers on "dashboard",
  "explore", "canvas", "rill dashboard", "create dashboard", "add chart", "dashboard filter",
  "dashboard theme", "dashboard defaults", or when working with files in
  rill_project/dashboards/ or rill_project/metrics/.
metadata:
  version: 1.0.0
  source: https://docs.rilldata.com/developers/build/dashboards
---

# Rill Dashboards

You are an expert in Rill dashboard configuration. Rill offers two dashboard types:
**Explore** (opinionated, single metrics view, interactive slice-and-dice) and
**Canvas** (custom layouts, multiple metrics views, flexible widgets).

**Project context:** This project (`local-data-stack`) uses DuckDB as the OLAP engine.
Dashboard YAML files live in `rill_project/dashboards/` (`type: explore` or
`type: canvas`). Metrics view YAML files live in `rill_project/metrics/`
(`type: metrics_view`) and are referenced by dashboards via `metrics_view: <name>`.

## Choosing Dashboard Type

| | Explore | Canvas |
|---|---|---|
| **Metrics views** | Single | Multiple |
| **Layout** | Fixed, opinionated | Custom, drag-and-drop |
| **Visualizations** | Auto-generated (line chart, leaderboard, pivot) | Manual widget selection |
| **Best for** | Interactive data exploration, ad-hoc analysis | Curated dashboards, executive views |
| **YAML type** | `type: explore` | `type: canvas` |

## Explore Dashboards

Explore dashboards provide interactive slice-and-dice over a single metrics view.
They auto-generate time-series charts, leaderboards, and pivot tables.

### Basic Structure

```yaml
# Explore Dashboard YAML
# Reference: https://docs.rilldata.com/reference/project-files/explore-dashboards
type: explore
title: "Dashboard Title"
description: "Description of this dashboard"
metrics_view: my_metrics_view    # References a metrics view by name

dimensions:
  - dimension_1
  - dimension_2

measures:
  - measure_1
  - measure_2

defaults:
  time_range: P3M
  comparison_mode: time
  measures:
    - measure_1
    - measure_2
  dimensions:
    - dimension_1
```

### Field Selection

Use wildcards, lists, regex, or exclusion patterns to control which dimensions/measures appear:

```yaml
dimensions: "*"                          # All dimensions
dimensions:
  - revenue
  - orders
dimensions:
  expr: "^public_.*$"                    # Regex match
dimensions:
  exclude:
    - internal_id                        # All except these
```

### Time Configuration

```yaml
time_ranges:
  - PT15M      # 15 minutes
  - PT1H       # 1 hour
  - P7D        # 7 days
  - P1M        # 1 month
  - rill-TD    # Today
  - rill-WTD   # Week-to-date

time_zones:
  - America/New_York
  - America/Chicago
  - UTC

lock_time_zone: true              # Lock to first time_zone (UTC if none specified)
allow_custom_time_range: false    # Hide custom time range picker
```

### Defaults

```yaml
defaults:
  time_range: P1M                  # ISO 8601 duration or Rill extension
  comparison_mode: time            # "none", "time", or "dimension"
  comparison_dimension: region     # When comparison_mode is "dimension"
  measures:
    - revenue
    - orders
  dimensions:
    - region
    - product
```

### Themes (Inline)

```yaml
theme:
  colors:
    primary: "#1d4ed8"            # hex, named color, or hsl()
    secondary: "#f59e0b"
  light:
    primary: "#2563eb"
    secondary: "#d97706"
    kpi-positive: "#059669"       # Override default (gray)
    kpi-negative: "#dc2626"       # Override default (red)
  dark:
    primary: "#3b82f6"
    secondary: "#fbbf24"
    kpi-positive: "#10b981"
    kpi-negative: "#ef4444"
```

### Security

```yaml
security:
  access: "{{ .user.email }} IS NOT NULL"   # Grant access condition
```

### Embedded View Configuration

```yaml
embeds:
  hide_pivot: true               # Hide pivot table in embedded mode
```

## Canvas Dashboards

Canvas dashboards let you combine multiple metrics views into custom layouts
with individual widget components.

### Basic Structure

```yaml
# Canvas Dashboard YAML
# Reference: https://docs.rilldata.com/reference/project-files/canvas-dashboards
type: canvas
title: "Executive Dashboard"
description: "Custom dashboard combining multiple data sources"

columns: 24         # Grid columns (default 24)
gap: 2              # Gap between widgets (default 2)

defaults:
  filters:
    my_metrics_view: "region IN ('US', 'CA') AND status = 'active'"
    another_view: "country = 'US'"

items:
  - component: kpi
    x: 0
    y: 0
    width: 6
    height: 3
    properties:
      metrics_view: my_metrics_view
      measure: total_revenue

  - component: line_chart
    x: 0
    y: 3
    width: 12
    height: 6
    properties:
      metrics_view: my_metrics_view
      x: timestamp_col
      y:
        - total_revenue
        - total_cost
      filter: "status = 'active'"
```

### Available Widget Components

**Data Components:**
- `kpi` — Big number with delta/trend indicator
- `leaderboard` — Ranked list with bar visualization
- `table` — Tabular data display

**Chart Components:**
- `bar_chart` — Vertical or horizontal bars
- `line_chart` — Time series or categorical line charts
- `area_chart` — Filled area visualization
- `stacked_bar` — Stacked bar chart
- `grouped_bar` — Grouped bar chart
- `heatmap` — Color-intensity matrix
- `scatter_chart` — Scatter / bubble plot
- `pie_chart` — Pie or donut chart
- `funnel` — Funnel visualization
- `markdown` — Rich text / markdown content
- `image` — Image display
- `iframe` — Embedded web content

### Global Filter Bar

Toggle under Canvas properties to give viewers access to time and dimension filters.
Filters can be set globally (applies to all widgets) or locally (per-widget):

```yaml
# Global filter bar is a UI toggle; no YAML needed for the bar itself

# In widget properties, set local filters:
properties:
  metrics_view: my_view
  measure: revenue
  filter: "country = 'US'"     # Local filter (Metrics SQL WHERE expression)
```

### Default Filters

Apply default filters that pre-filter data when the dashboard loads:

```yaml
defaults:
  filters:
    # Key = metrics view name; value = Metrics SQL WHERE expression
    sales_metrics: "country IN ('US', 'CA') AND revenue > 1000"
    support_metrics: "status = 'open'"
```

## Common Properties (All Dashboard Types)

All Rill resource YAML files support these properties:

- `name` — Inferred from filename, can be set manually
- `refs` — List of resource references
- `dev` — Property overrides for development environment
- `prod` — Property overrides for production environment

```yaml
dev:
  metrics_view: dev_metrics_view    # Use different view in dev
prod:
  security:
    access: "{{ .user.role }} = 'viewer'"
```

## Dashboard Security

Dashboards can have their own access control (in addition to metrics view security):

```yaml
security:
  access: "{{ .user.email }} IS NOT NULL"          # Who can view
```

Row-level filtering is applied at the metrics view level, not the dashboard level.

## Project Conventions

Based on the existing codebase:

1. **File naming**: `<snake_case_description>.yaml` (e.g., `chronic_absenteeism_risk.yaml`)
2. **File header**: Include a comment block with description and data source
   ```yaml
   # Dashboard Title
   # Source: metrics view <metrics_view_name>
   # Brief description of what this dashboard monitors
   ```
3. **Metrics views live in `rill_project/metrics/`** as separate files
   (`type: metrics_view`) and are referenced from dashboards via
   `metrics_view: <name>` — this project does NOT inline metrics views inside
   dashboard files.
4. **DuckDB SQL**: Available for expressions and filters
5. **Timeseries**: Often `_loaded_at` for batch-loaded data
6. **`format_preset`**: Used on all measures — common values are `humanize`, `percentage`, `currency_usd`
7. **`label`** vs **`display_name`**: This project uses `label` (note: `display_name` is the newer field;
   both work but check existing files for consistency)

## Workflow

When asked to create or modify a dashboard:

1. Determine which dashboard type fits the use case (Explore for exploration, Canvas for curated views)
2. Check existing dashboard files in `rill_project/dashboards/` for conventions
   and metrics view files in `rill_project/metrics/` for available views
3. For Explore dashboards: reference an existing metrics view by name
4. For Canvas dashboards: define components with x/y/width/height grid positions
5. Set appropriate default time ranges and filters
6. Add `description` fields
7. If the dashboard needs inline metrics view definition, follow the `rill-metrics-view` skill
8. Test with `rill start` from the `rill_project/` directory
9. Preview before deploying to Rill Cloud

## Deployment

```bash
# Run locally
cd rill_project && rill start

# Validate files
cd rill_project && rill validate

# Deploy to Rill Cloud
cd rill_project && rill deploy
```
