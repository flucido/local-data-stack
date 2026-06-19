---
name: rill-metrics-view
description: Create and edit Rill metrics view YAML files. Use when defining dimensions, measures, time series,
  or any metrics view configuration in the rill_project. Triggers on "metrics view", "define measure",
  "add dimension", "create metric", "timeseries", "rill metric", or when working with
  rill_project/**/*.yaml files containing type: metrics_view. Also use when the user asks about
  Rill semantic layer, OLAP aggregations, or dashboard data sources.
metadata:
  version: 1.0.0
  source: https://docs.rilldata.com/developers/build/metrics-view
---

# Rill Metrics Views

You are an expert in Rill metrics view configuration. Your goal is to create and edit
metrics view YAML files that define measures, dimensions, and time series for Rill dashboards.

**Project context:** This project (`local-data-stack`) uses DuckDB as the OLAP engine
and follows the "One Big Table" (OBT) approach. Metrics views live under
`rill_project/` (check for a `metrics` directory or inline definitions in dashboard files).

## File Structure

A metrics view YAML file uses this skeleton:

```
# Metrics View YAML
# Reference: https://docs.rilldata.com/reference/project-files/metrics-views
version: 1
type: metrics_view
model: <model_name>           # Use 'model' for DuckDB/Rill-managed ClickHouse
timeseries: <timestamp_column> # The time column powering charts
display_name: "Human Readable Name"
description: "Description of this metrics view"

dimensions:
  - name: unique_dim_name
    display_name: "Display Name"
    column: column_name
    description: "What this dimension represents"

measures:
  - name: unique_measure_name
    display_name: "Display Name"
    expression: SUM(column_name)
    description: "What this measure calculates"
    format_preset: humanize    # optional
```

Files go under `rill_project/` — either in a `metrics/` subdirectory if one exists,
or inline within dashboard YAML files.

## Key Concepts

### Underlying Model vs Table

Since this project uses **DuckDB** (see `rill_project/rill.yaml`), always use `model`
— not `table`. The `model` property references a Rill model that was ingested from
source data. Only use `table` + `connector` for self-managed external OLAP engines
(Snowflake, BigQuery, self-hosted ClickHouse, etc.).

### Time Series

- `timeseries` must reference a column of type `TIMESTAMP`, `TIME`, or `DATE`
- If your source has dates in another format, transform them in the model first
- **`smallest_time_grain`**: limits minimum time resolution (e.g., `day`, `hour`)
  - Valid: `millisecond`, `second`, `minute`, `hour`, `day`, `week`, `month`, `quarter`, `year`
- **`first_day_of_week`**: 1=Monday through 7=Sunday
- **`first_month_of_year`**: 1=January through 12=December
- **`watermark`**: SQL expression defining the data freshness boundary
  - Example: `"MAX(__TIME) - INTERVAL 3 DAYS"`
  - Common: `"MAX(__TIME) - INTERVAL 1 DAY"` for daily batch processing
- **`max_query_time_range`**: ISO 8601 duration limiting max query span (e.g., `P90D`, `P1Y`)

### Dimensions

Dimensions are the "who, what, and where" — categorical columns for segmentation and filtering.

```yaml
dimensions:
  - name: category             # Stable identifier (required)
    display_name: "Category"   # Human-readable label
    column: product_category   # Column name from the model (use column OR expression, not both)
    description: "Product category for segmentation"
    type: categorical          # Optional: "categorical", "geo", or "time" (auto-inferred if omitted)
    tags: ["product", "segment"]  # Optional
```

- Use `column` for direct column references
- Use `expression` for SQL expressions (e.g., `string_split(domain, '.')`)
- Never use both `column` and `expression` on the same dimension
- **`unnest: true`**: Expands array/multi-valued dimensions; filters auto-switch to "contains"
- **`uri`**: Set to `true` or a SQL expression to make dimension values clickable links
- **Lookup dimensions**: Use `lookup_table`, `lookup_key_column`, `lookup_value_column` together

### Measures

Measures are the "how much" and "how many" — numeric calculations using SQL aggregates.

```yaml
measures:
  - name: total_revenue              # Stable identifier (required)
    display_name: "Total Revenue"    # Human-readable label
    expression: SUM(revenue)         # SQL aggregate expression (required)
    description: "Total revenue generated"
    format_preset: currency_usd      # Optional formatting

  - name: avg_order_value
    display_name: "Avg Order Value"
    expression: CAST(SUM(revenue) AS FLOAT) / CAST(COUNT(DISTINCT order_id) AS FLOAT)

  - name: high_value_orders
    display_name: "Orders > $100"
    expression: COUNT(*) FILTER (WHERE order_val > 100)  # Filtered aggregate (engine-dependent)
```

**Supported aggregates:** `AVG`, `COUNT`, `MAX`, `MIN`, `SUM`, `STDDEV`, `VARIANCE`,
`APPROX_COUNT_DISTINCT`, `APPROX_QUANTILE`, `STDDEV_POP`, `STDDEV_SAMP`, `VAR_POP`, `VAR_SAMP`

**Format presets:**
- `humanize` (default) — rounds to K, M, B
- `none` — raw output
- `currency_usd` — $ with 2 decimal places
- `currency_eur` — € with 2 decimal places
- `percentage` — converts rate to % with sign
- `interval_ms` — milliseconds to human-readable duration

**`format_d3`**: Use a d3-format string (e.g., `".2f"`, `",.2r"`, `"$,"`) instead of preset.
A measure cannot have both `format_preset` and `format_d3`.

**`lower_is_better: true`**: Inverts positive/negative coloring for metrics like bounce rate or error count.

**`valid_percent_of_total: true`**: Enables percent-of-total rendering for this measure.

### Measure Types

- **`type: simple`** (default) — basic aggregation via `expression`
- **`type: derived`** — calculation referencing other measures via `requires`
- **`type: time_comparison`** — period-over-period analysis

### Referencing Measures (Derived)

```yaml
measures:
  - name: total_revenue
    expression: SUM(revenue)
  - name: total_orders
    expression: COUNT(DISTINCT order_id)
  - name: revenue_per_order
    expression: total_revenue / NULLIF(total_orders, 0)
    type: derived
    requires:
      - name: total_revenue
      - name: total_orders
```

### Window Functions

```yaml
measures:
  - name: running_total
    expression: SUM(revenue)
    window: true           # Shorthand for time-partitioned
  - name: cumulative_all
    expression: SUM(revenue)
    window: all            # Non-partitioned (all rows)
  - name: custom_window
    expression: SUM(revenue)
    window:
      partition: true
      order: date_col
      frame: "range between unbounded preceding and current row"
```

## Field Selectors (Regex / Exclude Patterns)

When specifying subsets of dimensions or measures (in derived metrics views or dashboards),
use these selector patterns:

```yaml
# Select specific fields
dimensions:
  - field_a
  - field_b

# Wildcard (all fields)
dimensions: "*"

# Regex match
dimensions:
  expr: "^public_.*$"

# All except specific fields
dimensions:
  exclude:
    - internal_id
    - raw_json
```

## Derived Metrics Views

Use `parent` to inherit from a base metrics view, then selectively include/exclude:

```yaml
version: 1
type: metrics_view
display_name: "Executive Summary"
parent: base_metrics_view         # Inherit from parent
parent_dimensions: "*"            # Include all parent dimensions
parent_measures:
  exclude:                        # Exclude specific measures
    - granular_detail_metric
```

## Security (Row-Level / Field-Level Access)

```yaml
security:
  access: "{{ .user.email }} IS NOT NULL"   # Grant access condition
  row_filter: "region = '{{ .user.attributes.region }}'"  # Row-level filter
  include:
    - if: "{{ .user.role }} = 'admin'"
      names: "*"
  exclude:
    - if: "{{ .user.role }} != 'admin'"
      names:
        - profit_margin
        - internal_cost
```

## Rollups (Pre-aggregated Query Acceleration)

```yaml
rollups:
  - model: my_hourly_rollup
    time_grain: hour
    dimensions: "*"
    measures: "*"
```

## Inline Explore Views

A metrics view can define an inline explore dashboard directly:

```yaml
explore:
  name: my_explore
  display_name: "Data Explorer"
  description: "Interactive exploration"
  defaults:
    time_range: P3M
    comparison_mode: time
    measures: "*"
    dimensions: "*"
```

## Metrics SQL (Querying Metrics Views)

Metrics SQL is a SQL dialect that lets you query metrics views as if they were tables.
It transpiles to native OLAP SQL, handling measure expansion, GROUP BY inference,
and security filtering automatically.

**Source:** https://www.rilldata.com/blog/introducing-metrics-sql-a-sql-based-semantic-layer-for-humans-and-agents

### Querying via CLI

```bash
# Local project
rill query --local --resolver metrics_sql --properties sql="<Metrics SQL query>"

# Rill Cloud project
rill query --project my-project --resolver metrics_sql --properties sql="<Metrics SQL query>"
```

### Querying via HTTP API

```bash
curl -X POST "https://admin.rilldata.com/v1/orgs/{org}/projects/{project}/runtime/api/metrics-sql" \
  -H "Authorization: Bearer $RILL_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"sql": "<Metrics SQL query>"}'
```

### Basic Query Patterns

```sql
-- Top N by measure
SELECT country, revenue FROM revenue_metrics ORDER BY revenue DESC LIMIT 10

-- Filter on a dimension
SELECT country, revenue FROM revenue_metrics
WHERE product_category = 'Electronics' ORDER BY revenue DESC LIMIT 10

-- Filter on a computed dimension (expression-based)
SELECT country, revenue FROM revenue_metrics
WHERE product_category = 'Electronics' ORDER BY revenue DESC LIMIT 10
```

### Subquery with HAVING (Measure Filtering)

Measure filters MUST use `HAVING`, not `WHERE`. `WHERE` applies pre-aggregation
against the underlying table (dimension filters only). Filtering on a measure
requires `HAVING`.

```sql
-- Show order volume for countries where total revenue exceeded $10,000
SELECT country, order_volume
FROM revenue_metrics
WHERE country IN
  (SELECT country
   FROM revenue_metrics
   HAVING revenue > 10000)
```

### Time Range Expressions

```sql
SELECT country, revenue
FROM revenue_metrics
WHERE order_date > time_range_start('7D as of watermark')
  AND order_date <= time_range_end('7D as of watermark')
```

### Window Function Queries

Window measures defined in the metrics view (with `window` config) are
queried like any other measure. The metrics layer produces a two-level
query: inner subquery computes the base aggregate, outer applies the window.

```sql
SELECT order_date, revenue_7day_avg FROM revenue_metrics
```

### Metrics SQL Limitations

These are intentional design constraints, not oversights:

1. **No JOINs across metrics views.** Each Metrics SQL query targets exactly one
   metrics view. Cross-view analysis requires a joined/denormalized model.
2. **No `SELECT *`.** Dimensions and measures must be named explicitly for
   governance and performance (avoid unnecessary column scans).
3. **Measure filters MUST use `HAVING`, not `WHERE`.** `WHERE` filters are
   pre-aggregation against the raw table — only dimension filters are valid there.
   Measure conditions (e.g., `total_spend > 100`) must use `HAVING` syntax
   (typically via the subquery pattern shown above).
4. **Metrics SQL is a restricted SQL subset.** Not all operators/expressions
   are supported yet.

### AI Instructions

Add `ai_instructions` to metrics views to give AI agents domain context
that cannot be inferred from schema alone:

```yaml
ai_instructions: |
  Financial year begins February 1.
  Use "booking_date" not "event_date" for sales reporting.
  Revenue figures should always be reported in USD.
```

### How Transpilation Works

Metrics SQL passes through three layers before hitting the OLAP engine:

1. **Parser** — validates syntax
2. **Query Compiler** — resolves names against metrics view definition,
   classifies measures/dimensions, infers GROUP BY
3. **Executor** — applies security filters and semantic rewrites, produces
   parameterized OLAP SQL (against DuckDB, ClickHouse, Snowflake, or Druid)

Key transformations:
- `FROM` clause is rewritten to the underlying model/table
- Measure names expand to their aggregate expressions
- `GROUP BY` is inferred from selected dimensions
- Dimension filter expressions are expanded transparently
- Literals become parameterized arguments (SQL injection safety)

## Project Conventions

Based on the existing codebase, follow these patterns:

1. **Model names** reference models defined in `rill_project/models/` or via dbt sources
2. **Dimension names** use `snake_case` identifiers
3. **Display names** use Title Case for labels
4. **File naming**: `<descriptive_snake_case>.yaml` for metrics view files
5. **Timeseries column** is often `_loaded_at` for batch-loaded data
6. Always include `version: 1` and `type: metrics_view` at the top
7. DuckDB SQL functions are available for expressions (no engine-specific ClickHouse/Druid syntax)

## Workflow

When asked to create or modify a metrics view:

1. Check `rill_project/rill.yaml` for the OLAP engine (DuckDB)
2. Look at existing metrics view files in `rill_project/metrics/` for conventions
3. Inspect the referenced model to confirm column names before writing dimensions/measures
4. Use `name` (snake_case) and `display_name` (Title Case) for all fields
5. Add `description` fields for documentation
6. Choose appropriate `format_preset` values for measures
7. Set `timeseries` to the appropriate timestamp column
8. When filtering dimensions/measures for a dashboard, use the field selector patterns
