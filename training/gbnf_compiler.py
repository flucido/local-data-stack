"""
gbnf_compiler.py — Canonical Two-Hop Tool Schemas, GBNF Grammar Compiler, and Semantic Validator.

Implements Recommendation #4 from the Sovereign Local-First Analytics & Generative UI blueprint:
  1. Canonical JSON tool schemas for Hop 1 (`execute_duckdb_query`), Hop 1b (`duckdb_execution_error`),
     Turn 2 tool input (`duckdb_result_summary`), and Hop 2 (`render_workspace_ui`).
  2. Static Hop 1 GBNF grammar (`compile_hop1_gbnf()`) enforcing valid JSON tool call structure
     and a read-only `SELECT` or `WITH` SQL prefix.
  3. Dynamic Hop 2 GBNF grammar (`compile_hop2_gbnf(columns)`) injecting the exact DuckDB output
     column names into the `.gbnf` `column-name` rule so a 1.5B-3B model is physically incapable
     of hallucinating column names, component types, or invalid JSON properties.
  4. Deterministic structural and semantic validation (`validate_hop1_call`, `validate_hop2_call`)
     used both at runtime and as the verification / GRPO reward gate during training.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

# ── Canonical Component & Control Constants ────────────────────────────

CANONICAL_COMPONENTS = (
    "KPIGrid",
    "TimeSeriesChart",
    "CategoryBarChart",
    "BudgetVarianceChart",
    "DataTable",
    "FilterBar",
)

VALUE_FORMATS = ("currency", "percent", "integer", "decimal", "raw")
FILTER_CONTROL_TYPES = ("date_range", "multi_select", " single_select", "numeric_range", "search")
FILTER_CONTROL_TYPES_CLEAN = (
    "date_range",
    "multi_select",
    "single_select",
    "numeric_range",
    "search",
)
TIMESERIES_VARIANTS = ("line", "area", "stacked_bar", "bar")
CATEGORY_BAR_VARIANTS = ("horizontal", "vertical", "grouped", "stacked")
SORT_DIRECTIONS = ("asc", "desc")

TEMPORAL_TYPE_KEYWORDS = ("DATE", "TIME", "TIMESTAMP", "INTERVAL")
NUMERIC_TYPE_KEYWORDS = (
    "INT",
    "BIGINT",
    "SMALLINT",
    "TINYINT",
    "HUGEINT",
    "DOUBLE",
    "FLOAT",
    "REAL",
    "DECIMAL",
    "NUMERIC",
)

# ── Canonical JSON Tool Schemas (OpenAI / HF `tools` format) ───────────

EXECUTE_DUCKDB_QUERY_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "execute_duckdb_query",
        "description": (
            "Execute a read-only DuckDB SELECT or WITH query against the local analytical "
            "warehouse and return a compact result metadata summary."
        ),
        "parameters": {
            "type": "object",
            "required": ["explanation", "sql"],
            "additionalProperties": False,
            "properties": {
                "explanation": {
                    "type": "string",
                    "description": "Concise 1-sentence explanation of the query grain, filters, and aggregations.",
                },
                "sql": {
                    "type": "string",
                    "description": "Valid read-only DuckDB SQL starting with SELECT or WITH.",
                },
            },
        },
    },
}

RENDER_WORKSPACE_UI_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "render_workspace_ui",
        "description": (
            "Render 1 to 4 interactive Generative UI workspace panels bound to the columns "
            "of the executed DuckDB query."
        ),
        "parameters": {
            "type": "object",
            "required": ["title", "narrative_summary", "components"],
            "additionalProperties": False,
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Short dashboard view title.",
                },
                "narrative_summary": {
                    "type": "string",
                    "description": "1-2 sentence analytical takeaway grounded in the result summary.",
                },
                "components": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 4,
                    "items": {
                        "oneOf": [
                            {
                                "type": "object",
                                "required": ["component", "metrics"],
                                "additionalProperties": False,
                                "properties": {
                                    "component": {"const": "KPIGrid"},
                                    "metrics": {
                                        "type": "array",
                                        "minItems": 1,
                                        "maxItems": 4,
                                        "items": {
                                            "type": "object",
                                            "required": ["label", "value_column", "value_format"],
                                            "additionalProperties": False,
                                            "properties": {
                                                "label": {"type": "string"},
                                                "value_column": {"type": "string"},
                                                "value_format": {
                                                    "type": "string",
                                                    "enum": list(VALUE_FORMATS),
                                                },
                                                "delta_column": {"type": "string"},
                                            },
                                        },
                                    },
                                },
                            },
                            {
                                "type": "object",
                                "required": [
                                    "component",
                                    "chart_variant",
                                    "x_column",
                                    "y_columns",
                                    "value_format",
                                ],
                                "additionalProperties": False,
                                "properties": {
                                    "component": {"const": "TimeSeriesChart"},
                                    "chart_variant": {
                                        "type": "string",
                                        "enum": list(TIMESERIES_VARIANTS),
                                    },
                                    "x_column": {"type": "string"},
                                    "y_columns": {
                                        "type": "array",
                                        "minItems": 1,
                                        "maxItems": 3,
                                        "items": {"type": "string"},
                                    },
                                    "series_column": {"type": "string"},
                                    "value_format": {"type": "string", "enum": list(VALUE_FORMATS)},
                                },
                            },
                            {
                                "type": "object",
                                "required": [
                                    "component",
                                    "chart_variant",
                                    "category_column",
                                    "value_columns",
                                    "value_format",
                                ],
                                "additionalProperties": False,
                                "properties": {
                                    "component": {"const": "CategoryBarChart"},
                                    "chart_variant": {
                                        "type": "string",
                                        "enum": list(CATEGORY_BAR_VARIANTS),
                                    },
                                    "category_column": {"type": "string"},
                                    "value_columns": {
                                        "type": "array",
                                        "minItems": 1,
                                        "maxItems": 3,
                                        "items": {"type": "string"},
                                    },
                                    "series_column": {"type": "string"},
                                    "value_format": {"type": "string", "enum": list(VALUE_FORMATS)},
                                },
                            },
                            {
                                "type": "object",
                                "required": [
                                    "component",
                                    "category_column",
                                    "actual_column",
                                    "budget_column",
                                    "value_format",
                                ],
                                "additionalProperties": False,
                                "properties": {
                                    "component": {"const": "BudgetVarianceChart"},
                                    "category_column": {"type": "string"},
                                    "actual_column": {"type": "string"},
                                    "budget_column": {"type": "string"},
                                    "variance_column": {"type": "string"},
                                    "value_format": {"type": "string", "enum": list(VALUE_FORMATS)},
                                },
                            },
                            {
                                "type": "object",
                                "required": ["component", "columns"],
                                "additionalProperties": False,
                                "properties": {
                                    "component": {"const": "DataTable"},
                                    "columns": {
                                        "type": "array",
                                        "minItems": 1,
                                        "items": {"type": "string"},
                                    },
                                    "default_sort": {
                                        "type": "object",
                                        "required": ["column", "direction"],
                                        "additionalProperties": False,
                                        "properties": {
                                            "column": {"type": "string"},
                                            "direction": {
                                                "type": "string",
                                                "enum": list(SORT_DIRECTIONS),
                                            },
                                        },
                                    },
                                },
                            },
                            {
                                "type": "object",
                                "required": ["component", "controls"],
                                "additionalProperties": False,
                                "properties": {
                                    "component": {"const": "FilterBar"},
                                    "controls": {
                                        "type": "array",
                                        "minItems": 1,
                                        "maxItems": 4,
                                        "items": {
                                            "type": "object",
                                            "required": ["column", "control_type", "label"],
                                            "additionalProperties": False,
                                            "properties": {
                                                "column": {"type": "string"},
                                                "control_type": {
                                                    "type": "string",
                                                    "enum": list(FILTER_CONTROL_TYPES_CLEAN),
                                                },
                                                "label": {"type": "string"},
                                            },
                                        },
                                    },
                                },
                            },
                        ]
                    },
                },
            },
        },
    },
}

CANONICAL_TOOLS: list[dict[str, Any]] = [
    EXECUTE_DUCKDB_QUERY_TOOL,
    RENDER_WORKSPACE_UI_TOOL,
]


# ── GBNF Grammar Compilation ───────────────────────────────────────────


def _escape_gbnf_literal(value: str) -> str:
    """Escape a string literal so it can be embedded inside a GBNF rule."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"\\"{escaped}\\""'


def compile_hop1_gbnf() -> str:
    """Compile the static Hop 1 (`execute_duckdb_query`) GBNF grammar.

    Enforces:
      - Exact JSON envelope: `{"tool": "execute_duckdb_query", "arguments": {"explanation": "...", "sql": "..."}}`
      - Read-only SQL start (`SELECT ` or `WITH `) so the model can never emit
        markdown prose or mutating DDL/DML statements.
    """
    return r"""# Hop 1 GBNF Grammar: execute_duckdb_query
# Enforces valid JSON tool call and read-only SELECT / WITH prefix

root ::= ws "{" ws "\"tool\"" ws ":" ws "\"execute_duckdb_query\"" ws "," ws "\"arguments\"" ws ":" ws arguments ws "}" ws

arguments ::= "{" ws "\"explanation\"" ws ":" ws string ws "," ws "\"sql\"" ws ":" ws sql-string ws "}"

sql-string ::= "\"" sql-prefix sql-char* "\""
sql-prefix ::= ("SELECT" | "select" | "WITH" | "with") " "
sql-char ::= [^"\\\x7F\x00-\x1F] | "\\" (["\\bfnrt] | "u" [0-9a-fA-F]{4})

string ::= "\"" char* "\""
char ::= [^"\\\x7F\x00-\x1F] | "\\" (["\\bfnrt] | "u" [0-9a-fA-F]{4})

ws ::= [ \t\n\r]*
"""


def compile_hop2_gbnf(columns: list[str] | None = None) -> str:
    """Compile the dynamic Hop 2 (`render_workspace_ui`) GBNF grammar.

    Args:
        columns: Exact list of column names returned by DuckDB in Hop 1.
                 When provided, the `column-name` rule is restricted to those
                 exact column strings, making column hallucination impossible.
                 If empty or None, falls back to a general `string` rule.
    """
    if columns:
        deduped = list(dict.fromkeys(col for col in columns if col))
        col_rule = " | ".join(_escape_gbnf_literal(c) for c in deduped)
    else:
        col_rule = "string"

    return f"""# Hop 2 GBNF Grammar: render_workspace_ui
# Dynamically constrains component schemas and DuckDB output column bindings

root ::= ws "{{" ws "\\"tool\\"" ws ":" ws "\\"render_workspace_ui\\"" ws "," ws "\\"arguments\\"" ws ":" ws arguments ws "}}" ws

arguments ::= "{{" ws "\\"title\\"" ws ":" ws string ws "," ws "\\"narrative_summary\\"" ws ":" ws string ws "," ws "\\"components\\"" ws ":" ws component-list ws "}}"

component-list ::= "[" ws component (ws "," ws component){{0,3}} ws "]"

component ::= kpi-grid | time-series-chart | category-bar-chart | budget-variance-chart | data-table | filter-bar

kpi-grid ::= "{{" ws "\\"component\\"" ws ":" ws "\\"KPIGrid\\"" ws "," ws "\\"metrics\\"" ws ":" ws "[" ws kpi-metric (ws "," ws kpi-metric){{0,3}} ws "]" ws "}}"
kpi-metric ::= "{{" ws "\\"label\\"" ws ":" ws string ws "," ws "\\"value_column\\"" ws ":" ws column-name ws "," ws "\\"value_format\\"" ws ":" ws value-format (ws "," ws "\\"delta_column\\"" ws ":" ws column-name)? ws "}}"

time-series-chart ::= "{{" ws "\\"component\\"" ws ":" ws "\\"TimeSeriesChart\\"" ws "," ws "\\"chart_variant\\"" ws ":" ws ts-variant ws "," ws "\\"x_column\\"" ws ":" ws column-name ws "," ws "\\"y_columns\\"" ws ":" ws col-list-1-3 (ws "," ws "\\"series_column\\"" ws ":" ws column-name)? ws "," ws "\\"value_format\\"" ws ":" ws value-format ws "}}"
ts-variant ::= "\\"line\\"" | "\\"area\\"" | "\\"stacked_bar\\"" | "\\"bar\\""

category-bar-chart ::= "{{" ws "\\"component\\"" ws ":" ws "\\"CategoryBarChart\\"" ws "," ws "\\"chart_variant\\"" ws ":" ws cat-variant ws "," ws "\\"category_column\\"" ws ":" ws column-name ws "," ws "\\"value_columns\\"" ws ":" ws col-list-1-3 (ws "," ws "\\"series_column\\"" ws ":" ws column-name)? ws "," ws "\\"value_format\\"" ws ":" ws value-format ws "}}"
cat-variant ::= "\\"horizontal\\"" | "\\"vertical\\"" | "\\"grouped\\"" | "\\"stacked\\""

budget-variance-chart ::= "{{" ws "\\"component\\"" ws ":" ws "\\"BudgetVarianceChart\\"" ws "," ws "\\"category_column\\"" ws ":" ws column-name ws "," ws "\\"actual_column\\"" ws ":" ws column-name ws "," ws "\\"budget_column\\"" ws ":" ws column-name (ws "," ws "\\"variance_column\\"" ws ":" ws column-name)? ws "," ws "\\"value_format\\"" ws ":" ws value-format ws "}}"

data-table ::= "{{" ws "\\"component\\"" ws ":" ws "\\"DataTable\\"" ws "," ws "\\"columns\\"" ws ":" ws col-list-any (ws "," ws "\\"default_sort\\"" ws ":" ws sort-spec)? ws "}}"
sort-spec ::= "{{" ws "\\"column\\"" ws ":" ws column-name ws "," ws "\\"direction\\"" ws ":" ws ("\\"asc\\"" | "\\"desc\\"") ws "}}"

filter-bar ::= "{{" ws "\\"component\\"" ws ":" ws "\\"FilterBar\\"" ws "," ws "\\"controls\\"" ws ":" ws "[" ws filter-control (ws "," ws filter-control){{0,3}} ws "]" ws "}}"
filter-control ::= "{{" ws "\\"column\\"" ws ":" ws column-name ws "," ws "\\"control_type\\"" ws ":" ws control-type ws "," ws "\\"label\\"" ws ":" ws string ws "}}"
control-type ::= "\\"date_range\\"" | "\\"multi_select\\"" | "\\"single_select\\"" | "\\"numeric_range\\"" | "\\"search\\""

value-format ::= "\\"currency\\"" | "\\"percent\\"" | "\\"integer\\"" | "\\"decimal\\"" | "\\"raw\\""

col-list-1-3 ::= "[" ws column-name (ws "," ws column-name){{0,2}} ws "]"
col-list-any ::= "[" ws column-name (ws "," ws column-name)* ws "]"

column-name ::= {col_rule}

string ::= "\\"" char* "\\""
char ::= [^"\\\\\\x7F\\x00-\\x1F] | "\\\\" (["\\\\bfnrt] | "u" [0-9a-fA-F]{{4}})

ws ::= [ \\t\\n\\r]*
"""


# ── Structural & Semantic Validation ───────────────────────────────────


def _is_temporal_column(col_name: str, col_type: str) -> bool:
    upper_type = col_type.upper()
    if any(k in upper_type for k in TEMPORAL_TYPE_KEYWORDS):
        return True
    lower_name = col_name.lower()
    return any(
        token in lower_name
        for token in ("date", "month", "year", "week", "quarter", "day", "period", "term", "time")
    )


def _is_numeric_column(col_type: str) -> bool:
    upper_type = col_type.upper()
    return any(k in upper_type for k in NUMERIC_TYPE_KEYWORDS)


def validate_hop1_call(payload: dict[str, Any] | str) -> tuple[bool, list[str]]:
    """Validate a Hop 1 `execute_duckdb_query` tool call dict or JSON string."""
    errors: list[str] = []
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception as exc:
            return False, [f"Invalid JSON string: {exc}"]
    if not isinstance(payload, dict):
        return False, ["Payload must be a JSON object."]
    if payload.get("tool") != "execute_duckdb_query":
        errors.append(f"Expected tool 'execute_duckdb_query', got {payload.get('tool')!r}.")
    args = payload.get("arguments")
    if not isinstance(args, dict):
        errors.append("'arguments' must be an object.")
        return False, errors

    explanation = args.get("explanation")
    sql = args.get("sql")
    if not isinstance(explanation, str) or not explanation.strip():
        errors.append("'arguments.explanation' must be a non-empty string.")
    if not isinstance(sql, str) or not sql.strip():
        errors.append("'arguments.sql' must be a non-empty string.")
    else:
        stripped = sql.lstrip()
        if not (stripped.upper().startswith("SELECT") or stripped.upper().startswith("WITH")):
            errors.append("SQL must start with SELECT or WITH.")

    return len(errors) == 0, errors


def validate_hop2_call(
    payload: dict[str, Any] | str,
    result_summary: dict[str, Any] | None = None,
    valid_columns: list[str] | None = None,
) -> tuple[bool, list[str]]:
    """Validate a Hop 2 `render_workspace_ui` tool call against schema and data-shape rules.

    Checks:
      1. Structural schema validity for all 6 canonical components.
      2. Column binding integrity: every referenced column exists in `result_summary["columns"]`
         (or `valid_columns` when provided directly).
      3. Semantic chart-suitability heuristics (used in dataset curation and GRPO rewards):
         - `KPIGrid` requires `row_count == 1` (or summary scalar row) and numeric value columns.
         - `TimeSeriesChart` requires `row_count >= 2`, temporal/period `x_column`, and numeric `y_columns`.
         - `CategoryBarChart` requires `row_count >= 2` and numeric `value_columns`.
         - `BudgetVarianceChart` requires numeric `actual_column` and `budget_column`.
    """
    errors: list[str] = []
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception as exc:
            return False, [f"Invalid JSON string: {exc}"]
    if not isinstance(payload, dict):
        return False, ["Payload must be a JSON object."]
    if payload.get("tool") != "render_workspace_ui":
        errors.append(f"Expected tool 'render_workspace_ui', got {payload.get('tool')!r}.")

    args = payload.get("arguments")
    if not isinstance(args, dict):
        return False, ["'arguments' must be an object."]

    for field in ("title", "narrative_summary"):
        if not isinstance(args.get(field), str) or not args[field].strip():
            errors.append(f"'arguments.{field}' must be a non-empty string.")

    components = args.get("components")
    if not isinstance(components, list) or not (1 <= len(components) <= 4):
        errors.append("'arguments.components' must be a list of 1 to 4 components.")
        return False, errors

    col_map: dict[str, dict[str, Any]] = {}
    row_count: int | None = None
    if result_summary and isinstance(result_summary.get("columns"), list):
        col_map = {
            c["name"]: c for c in result_summary["columns"] if isinstance(c, dict) and "name" in c
        }
        row_count = result_summary.get("row_count")
    elif valid_columns:
        col_map = {c: {"name": c, "type": ""} for c in valid_columns if isinstance(c, str) and c}

    def check_col_exists(col: Any, ctx: str) -> bool:
        if not isinstance(col, str) or not col:
            errors.append(f"{ctx}: column name must be a non-empty string.")
            return False
        if col_map and col not in col_map:
            errors.append(
                f"{ctx}: referenced column '{col}' does not exist in query output columns {list(col_map.keys())}."
            )
            return False
        return True

    def check_numeric_col(col: str, ctx: str) -> None:
        if col_map and col in col_map:
            col_type = str(col_map[col].get("type", ""))
            if col_type and not _is_numeric_column(col_type):
                errors.append(f"{ctx}: column '{col}' has non-numeric type '{col_type}'.")

    seen_chart_types: list[str] = []

    for idx, comp in enumerate(components):
        ctx = f"components[{idx}]"
        if not isinstance(comp, dict):
            errors.append(f"{ctx} must be an object.")
            continue
        comp_type = comp.get("component")
        if comp_type not in CANONICAL_COMPONENTS:
            errors.append(
                f"{ctx}.component must be one of {CANONICAL_COMPONENTS}, got {comp_type!r}."
            )
            continue

        if comp_type in ("TimeSeriesChart", "CategoryBarChart", "BudgetVarianceChart"):
            if comp_type in seen_chart_types:
                errors.append(f"{ctx}: duplicate chart component type '{comp_type}'.")
            seen_chart_types.append(comp_type)

        if comp_type == "KPIGrid":
            metrics = comp.get("metrics")
            if not isinstance(metrics, list) or not (1 <= len(metrics) <= 4):
                errors.append(f"{ctx}.metrics must be a list of 1 to 4 metrics.")
                continue
            if row_count is not None and row_count != 1:
                errors.append(
                    f"{ctx} (KPIGrid): requires single-row scalar query result (row_count == 1), got row_count={row_count}."
                )
            for m_idx, m in enumerate(metrics):
                m_ctx = f"{ctx}.metrics[{m_idx}]"
                if not isinstance(m, dict):
                    errors.append(f"{m_ctx} must be an object.")
                    continue
                if not isinstance(m.get("label"), str) or not m["label"].strip():
                    errors.append(f"{m_ctx}.label must be a non-empty string.")
                val_col = m.get("value_column")
                if check_col_exists(val_col, f"{m_ctx}.value_column"):
                    check_numeric_col(val_col, f"{m_ctx}.value_column")
                if m.get("value_format") not in VALUE_FORMATS:
                    errors.append(f"{m_ctx}.value_format must be one of {VALUE_FORMATS}.")
                if "delta_column" in m and m["delta_column"] is not None:
                    if check_col_exists(m["delta_column"], f"{m_ctx}.delta_column"):
                        check_numeric_col(m["delta_column"], f"{m_ctx}.delta_column")

        elif comp_type == "TimeSeriesChart":
            if comp.get("chart_variant") not in TIMESERIES_VARIANTS:
                errors.append(f"{ctx}.chart_variant must be one of {TIMESERIES_VARIANTS}.")
            if row_count is not None and row_count < 2:
                errors.append(
                    f"{ctx} (TimeSeriesChart): requires at least 2 rows (row_count >= 2), got row_count={row_count}."
                )
            x_col = comp.get("x_column")
            if check_col_exists(x_col, f"{ctx}.x_column") and col_map and x_col in col_map:
                col_type = str(col_map[x_col].get("type", ""))
                if not _is_temporal_column(x_col, col_type):
                    errors.append(
                        f"{ctx}.x_column: column '{x_col}' (type '{col_type}') is not a temporal/period column."
                    )
            y_cols = comp.get("y_columns")
            if not isinstance(y_cols, list) or not (1 <= len(y_cols) <= 3):
                errors.append(f"{ctx}.y_columns must be a list of 1 to 3 column names.")
            else:
                for y_col in y_cols:
                    if check_col_exists(y_col, f"{ctx}.y_columns"):
                        check_numeric_col(y_col, f"{ctx}.y_columns")
            if "series_column" in comp and comp["series_column"] is not None:
                check_col_exists(comp["series_column"], f"{ctx}.series_column")
            if comp.get("value_format") not in VALUE_FORMATS:
                errors.append(f"{ctx}.value_format must be one of {VALUE_FORMATS}.")

        elif comp_type == "CategoryBarChart":
            if comp.get("chart_variant") not in CATEGORY_BAR_VARIANTS:
                errors.append(f"{ctx}.chart_variant must be one of {CATEGORY_BAR_VARIANTS}.")
            if row_count is not None and row_count < 2:
                errors.append(
                    f"{ctx} (CategoryBarChart): requires at least 2 rows (row_count >= 2), got row_count={row_count}."
                )
            cat_col = comp.get("category_column")
            if (
                check_col_exists(cat_col, f"{ctx}.category_column")
                and col_map
                and cat_col in col_map
            ):
                distinct_cnt = col_map[cat_col].get("distinct_count")
                if isinstance(distinct_cnt, int) and not (2 <= distinct_cnt <= 25):
                    errors.append(
                        f"{ctx}.category_column: '{cat_col}' has distinct_count={distinct_cnt}, expected between 2 and 25."
                    )
            val_cols = comp.get("value_columns")
            if not isinstance(val_cols, list) or not (1 <= len(val_cols) <= 3):
                errors.append(f"{ctx}.value_columns must be a list of 1 to 3 column names.")
            else:
                for v_col in val_cols:
                    if check_col_exists(v_col, f"{ctx}.value_columns"):
                        check_numeric_col(v_col, f"{ctx}.value_columns")
            if "series_column" in comp and comp["series_column"] is not None:
                check_col_exists(comp["series_column"], f"{ctx}.series_column")
            if comp.get("value_format") not in VALUE_FORMATS:
                errors.append(f"{ctx}.value_format must be one of {VALUE_FORMATS}.")

        elif comp_type == "BudgetVarianceChart":
            check_col_exists(comp.get("category_column"), f"{ctx}.category_column")
            for num_field in ("actual_column", "budget_column"):
                c_name = comp.get(num_field)
                if check_col_exists(c_name, f"{ctx}.{num_field}"):
                    check_numeric_col(c_name, f"{ctx}.{num_field}")
            if "variance_column" in comp and comp["variance_column"] is not None:
                if check_col_exists(comp["variance_column"], f"{ctx}.variance_column"):
                    check_numeric_col(comp["variance_column"], f"{ctx}.variance_column")
            if comp.get("value_format") not in VALUE_FORMATS:
                errors.append(f"{ctx}.value_format must be one of {VALUE_FORMATS}.")

        elif comp_type == "DataTable":
            cols = comp.get("columns")
            if not isinstance(cols, list) or len(cols) < 1:
                errors.append(f"{ctx}.columns must be a non-empty list of column names.")
            else:
                for c_name in cols:
                    check_col_exists(c_name, f"{ctx}.columns")
            if "default_sort" in comp and comp["default_sort"] is not None:
                ds = comp["default_sort"]
                if not isinstance(ds, dict):
                    errors.append(f"{ctx}.default_sort must be an object.")
                else:
                    check_col_exists(ds.get("column"), f"{ctx}.default_sort.column")
                    if ds.get("direction") not in SORT_DIRECTIONS:
                        errors.append(f"{ctx}.default_sort.direction must be 'asc' or 'desc'.")

        elif comp_type == "FilterBar":
            controls = comp.get("controls")
            if not isinstance(controls, list) or not (1 <= len(controls) <= 4):
                errors.append(f"{ctx}.controls must be a list of 1 to 4 controls.")
                continue
            for c_idx, ctrl in enumerate(controls):
                c_ctx = f"{ctx}.controls[{c_idx}]"
                if not isinstance(ctrl, dict):
                    errors.append(f"{c_ctx} must be an object.")
                    continue
                check_col_exists(ctrl.get("column"), f"{c_ctx}.column")
                if ctrl.get("control_type") not in FILTER_CONTROL_TYPES_CLEAN:
                    errors.append(
                        f"{c_ctx}.control_type must be one of {FILTER_CONTROL_TYPES_CLEAN}."
                    )
                if not isinstance(ctrl.get("label"), str) or not ctrl["label"].strip():
                    errors.append(f"{c_ctx}.label must be a non-empty string.")

    return len(errors) == 0, errors


def write_default_grammars(
    output_dir: Path, sample_columns: list[str] | None = None
) -> tuple[Path, Path]:
    """Write `hop1_sql.gbnf` and `hop2_ui.gbnf` to disk."""
    output_dir.mkdir(parents=True, exist_ok=True)
    hop1_path = output_dir / "hop1_sql.gbnf"
    hop2_path = output_dir / "hop2_ui.gbnf"
    hop1_path.write_text(compile_hop1_gbnf(), encoding="utf-8")
    hop2_path.write_text(compile_hop2_gbnf(sample_columns), encoding="utf-8")
    return hop1_path, hop2_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Compile Hop 1 and Hop 2 GBNF grammars.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "grammars",
        help="Directory to write hop1_sql.gbnf and hop2_ui.gbnf",
    )
    parser.add_argument(
        "--columns",
        type=str,
        default="",
        help="Comma-separated list of DuckDB result columns to constrain hop2_ui.gbnf",
    )
    args = parser.parse_args()
    cols = [c.strip() for c in args.columns.split(",") if c.strip()] if args.columns else None
    hop1_path, hop2_path = write_default_grammars(args.output_dir, cols)
    print(f"Wrote {hop1_path} and {hop2_path}")


if __name__ == "__main__":
    main()
