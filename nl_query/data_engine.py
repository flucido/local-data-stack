"""
data_engine.py — DuckDB lifecycle, schema introspection, and safe query execution.

Adapted for local-data-stack: instead of seeding an in-memory DuckDB from
Parquet/seed.sql, this opens a **read-only** connection to the unified
warehouse produced by the dlt → dbt pipeline (``data/warehouse.duckdb``) and
introspects its live schema.

Handles:
  - Opening per-request read-only DuckDB connections (thread-safe)
  - Multi-schema introspection for prompt context (core + analytics + cde),
    excluding PII-sensitive and dlt bookkeeping objects
  - extract_sql(): JSON envelope → ```sql``` block → raw fallback
  - validate_sql(): forbidden-token check + schema-aware column validation via EXPLAIN
  - execute_safe(): extraction, validation, subquery wrapping, execution
"""

from __future__ import annotations

import json
import os
import re
import threading
from pathlib import Path
from typing import TYPE_CHECKING

import duckdb

if TYPE_CHECKING:
    import pandas as pd

# ── Warehouse location ─────────────────────────────────────────────────

# Repo root = parent of the nl_query/ package directory.
REPO_ROOT = Path(__file__).resolve().parents[1]

# Phase 3 target: a single unified warehouse at data/warehouse.duckdb.
DEFAULT_WAREHOUSE = REPO_ROOT / "data" / "warehouse.duckdb"

# Until the unified warehouse exists, fall back to the warehouse the existing
# dbt pipeline already produces, so introspection/tests work today.
FALLBACK_WAREHOUSE = REPO_ROOT / "oss_framework" / "data" / "analytics.duckdb"


def get_warehouse_path() -> Path:
    """Resolve the warehouse DuckDB file path.

    Priority:
      1. ``LFED_WAREHOUSE_DB`` env var (explicit override)
      2. ``data/warehouse.duckdb`` (Phase 3 unified target)
      3. ``oss_framework/data/analytics.duckdb`` (current dbt output)
    """
    env = os.environ.get("LFED_WAREHOUSE_DB")
    if env:
        return Path(env).expanduser()
    if DEFAULT_WAREHOUSE.exists():
        return DEFAULT_WAREHOUSE
    return FALLBACK_WAREHOUSE


# ── Schema exposure policy ─────────────────────────────────────────────

# Schemas exposed to the NL→SQL layer. dbt-duckdb prefixes custom schemas
# with the default schema name, so the existing warehouse uses ``main_core``
# / ``main_analytics``. The bare ``core`` / ``analytics`` / ``cde`` names are
# included so the same allowlist works once the unified warehouse lands.
DEFAULT_EXPOSED_SCHEMAS = [
    "core",
    "main_core",
    "analytics",
    "main_analytics",
    "cde",
    "main_cde",
]


def get_exposed_schemas() -> list[str]:
    """Schemas the model is allowed to see/query (env-overridable)."""
    env = os.environ.get("LFED_EXPOSED_SCHEMAS")
    if env:
        return [s.strip() for s in env.split(",") if s.strip()]
    return DEFAULT_EXPOSED_SCHEMAS


# Never expose these schemas regardless of the allowlist — they contain
# re-identification keys or are not query targets.
BLOCKED_SCHEMAS = {
    "main_privacy_sensitive",  # priv_pii_lookup_table — de-anonymization keys
    "information_schema",
    "pg_catalog",
}

# Schema-name patterns that are always blocked regardless of the allowlist.
_BLOCKED_SCHEMA_PATTERNS = [
    re.compile(r"\bpriv_", re.IGNORECASE),
]


def _is_blocked_schema(schema_name: str) -> bool:
    if schema_name in BLOCKED_SCHEMAS:
        return True
    return any(p.search(schema_name) for p in _BLOCKED_SCHEMA_PATTERNS)


# Table-name patterns to hide (dlt bookkeeping + any PII lookup leakage).
_BLOCKED_TABLE_PATTERNS = [
    re.compile(r"^_dlt"),
    re.compile(r"pii_lookup", re.IGNORECASE),
]


def _is_blocked_table(table_name: str) -> bool:
    return any(p.search(table_name) for p in _BLOCKED_TABLE_PATTERNS)


# ── Column-level PII filtering ──────────────────────────────────────────

PII_COLUMNS: dict[str, set[str]] = {
    "core.dim_students": {
        "first_name",
        "last_name",
        "date_of_birth",
        "student_id",
        "ssn",
        "email",
        "phone",
        "address",
    },
    "main_core.dim_students": {
        "first_name",
        "last_name",
        "date_of_birth",
        "student_id",
        "ssn",
        "email",
        "phone",
        "address",
    },
}


def _get_pii_columns(key: str) -> set[str]:
    return {c.lower() for c in PII_COLUMNS.get(key, set())}


# Tables containing PII: wildcard SELECT * against these is blocked so the
# model can never bulk-extract protected columns it should not even see.
PROTECTED_TABLES = {key.lower() for key in PII_COLUMNS}

# Bare table names of protected tables (matches unqualified / aliased refs).
PROTECTED_TABLE_NAMES = {key.split(".")[-1] for key in PROTECTED_TABLES}


# ── Forbidden SQL terms (case-insensitive) ─────────────────────────────

FORBIDDEN_TOKENS = [
    "drop",
    "delete",
    "insert",
    "update",
    "alter",
    "truncate",
    "create",
    "attach",
    "detach",
    "pragma",
]

# Table-valued file readers / external-access functions. These bypass the
# warehouse catalog entirely (arbitrary filesystem reads), so they are
# rejected statically AND disabled at the engine level via
# ``SET enable_external_access = false`` (see get_connection()).
FORBIDDEN_FUNCTIONS = [
    "read_parquet",
    "parquet_scan",
    "query_parquet",
    "read_csv",
    "read_csv_auto",
    "csv_scan",
    "query_csv",
    "from_csv",
    "sniff_csv",
    "read_text",
    "read_blob",
    "read_json",
    "read_json_auto",
    "read_json_objects",
    "read_ndjson",
    "read_ndjson_objects",
    "json_scan",
    "query_json",
    "read_xlsx",
    "from_excel",
    "glob",
    "iceberg_scan",
    "iceberg_metadata",
    "delta_scan",
    "delta_metadata",
    "gdal_scan",
    "st_read",
]

_FORBIDDEN_FUNCTION_RE = re.compile(
    r"\b(" + "|".join(re.escape(f) for f in FORBIDDEN_FUNCTIONS) + r")\s*\(",
    re.IGNORECASE,
)

# Wildcard projections: `SELECT *`, `SELECT ALL *`, `SELECT DISTINCT *`, or `alias.*`.
_WILDCARD_SELECT_RE = re.compile(
    r"\bselect\s+(?:all\s+|distinct\s+)?\*|\bselect\b[^;]*?\w+\.\s*\*",
    re.IGNORECASE | re.DOTALL,
)

_SINGLE_QUOTED_LITERAL_RE = re.compile(r"'(?:''|[^'])*'")
_SQL_COMMENT_RE = re.compile(r"--[^\n]*|/\*[\s\S]*?\*/")
_DOUBLE_QUOTED_IDENT_RE = re.compile(r'"((?:""|[^"])+)"')
_FORBIDDEN_PII_TOKEN_RE = re.compile(
    r"\bstg_aeries__|\bstg_cde__schools\b|\braw_\w+\b|\w+_raw\b|\banalytics_for_hex\b"
    r"|\bfirst_name\b|\blast_name\b|\bdate_of_birth\b|\bstudent_id_raw\b"
    r"|\bssn\b|\bemail\b|\bphone\b|\baddress\b|\bcolumns\s*\(",
    re.IGNORECASE,
)
_PARSER_CONN_LOCK = threading.Lock()
_PARSER_CONN: duckdb.DuckDBPyConnection | None = None


def _serialize_sql_ast(sql: str, conn: duckdb.DuckDBPyConnection | None = None) -> dict | None:
    """Parse SQL into DuckDB's canonical JSON AST via json_serialize_sql."""
    global _PARSER_CONN
    try:
        if conn is not None:
            raw = conn.execute("SELECT json_serialize_sql(?)", [sql]).fetchone()[0]
        else:
            with _PARSER_CONN_LOCK:
                if _PARSER_CONN is None:
                    _PARSER_CONN = duckdb.connect(":memory:")
                raw = _PARSER_CONN.execute("SELECT json_serialize_sql(?)", [sql]).fetchone()[0]
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def _validate_ast_node(node: object, allowed_schemas: set[str], cte_scope: set[str]) -> None:
    """Recursively enforce schema allowlists and protected-table projection rules on DuckDB's AST."""
    if isinstance(node, list):
        for item in node:
            _validate_ast_node(item, allowed_schemas, cte_scope)
        return
    if not isinstance(node, dict):
        return

    local_ctes = set(cte_scope)
    cte_map = node.get("cte_map")
    if isinstance(cte_map, dict):
        for entry in cte_map.get("map") or []:
            if isinstance(entry, dict) and isinstance(entry.get("key"), str):
                local_ctes.add(entry["key"].lower())
        for entry in cte_map.get("map") or []:
            if isinstance(entry, dict):
                _validate_ast_node(entry.get("value"), allowed_schemas, local_ctes)

    node_type = node.get("type")
    if node_type == "BASE_TABLE":
        catalog = str(node.get("catalog_name") or "").strip().lower()
        schema = str(node.get("schema_name") or "").strip().lower()
        table = str(node.get("table_name") or "").strip().lower()
        if catalog and catalog not in ("memory", "temp"):
            raise ValueError(
                f"Query references catalog '{catalog}', which is outside the exposed schemas "
                f"({', '.join(sorted(allowed_schemas))})."
            )
        if not schema:
            if table not in local_ctes:
                raise ValueError(
                    f"Unqualified table '{table}' is outside the exposed schemas "
                    f"({', '.join(sorted(allowed_schemas))}). Specify an allowed schema."
                )
        elif schema not in allowed_schemas:
            raise ValueError(
                f"Query references '{schema}', which is outside the exposed schemas "
                f"({', '.join(sorted(allowed_schemas))})."
            )
        if _is_blocked_table(table) or table.startswith("raw_") or table == "analytics_for_hex":
            raise ValueError(f"Access to restricted table '{table}' is not allowed.")

    if node_type == "SELECT_NODE":
        protected_bindings: set[str] = set()

        def _collect_protected(ref_obj: object) -> None:
            if isinstance(ref_obj, dict):
                if ref_obj.get("type") == "BASE_TABLE":
                    tname = str(ref_obj.get("table_name") or "").strip().lower()
                    alias = str(ref_obj.get("alias") or "").strip().lower()
                    if tname in PROTECTED_TABLE_NAMES:
                        protected_bindings.add(tname)
                        if alias:
                            protected_bindings.add(alias)
                elif ref_obj.get("type") != "SELECT_NODE":
                    for v in ref_obj.values():
                        _collect_protected(v)
            elif isinstance(ref_obj, list):
                for it in ref_obj:
                    _collect_protected(it)

        _collect_protected(node.get("from_table"))
        if protected_bindings:
            for sel_item in node.get("select_list") or []:
                if not isinstance(sel_item, dict):
                    continue
                if sel_item.get("type") == "STAR" or sel_item.get("class") == "STAR":
                    rel = str(sel_item.get("relation_name") or "").strip().lower()
                    if not rel or rel in protected_bindings:
                        raise ValueError(
                            "Wildcard SELECT * against protected table 'dim_students' is not allowed. "
                            "Select only the specific non-PII columns you need."
                        )
                if sel_item.get("type") == "COLUMN_REF":
                    col_names = [str(c).lower() for c in (sel_item.get("column_names") or [])]
                    if len(col_names) == 1 and col_names[0] in protected_bindings:
                        raise ValueError(
                            "Whole-row struct selection against protected table 'dim_students' is not allowed."
                        )

    for key, val in node.items():
        if key != "cte_map":
            _validate_ast_node(val, allowed_schemas, local_ctes)


# ── Execution limits ───────────────────────────────────────────────────

MAX_RESULT_ROWS = 1000
QUERY_TIMEOUT_SEC = 10


# ── Connection factory ─────────────────────────────────────────────────


def get_connection(read_only: bool = True) -> duckdb.DuckDBPyConnection:
    """
    Return a fresh connection to the warehouse with safety defaults.

    Defaults to ``read_only=True``: the NL→SQL layer must never mutate the
    warehouse, and a read-only handle is defense-in-depth on top of the
    forbidden-token guard.

    Each request gets its own connection for thread safety. DuckDB allows
    multiple concurrent read-only handles to the same file.
    """
    path = get_warehouse_path()
    if not path.exists():
        raise FileNotFoundError(
            f"Warehouse not found at {path}. Run the dlt → dbt pipeline first, "
            f"or set LFED_WAREHOUSE_DB to an existing DuckDB file."
        )
    conn = duckdb.connect(database=str(path), read_only=read_only)
    _apply_sandbox_settings(conn)
    return conn


def _apply_sandbox_settings(conn: duckdb.DuckDBPyConnection) -> None:
    """Harden a DuckDB handle: no external access, then lock the config.

    ``SET enable_external_access = false`` disables file reads, HTTP, COPY
    to/from files, read_parquet/read_csv, etc. at the engine level.
    ``SET lock_configuration = true`` freezes further configuration changes
    so a query cannot re-enable them.

    DuckDB shares one database instance across connections opened in the
    same process, so once the first handle locks the configuration, later
    handles cannot re-issue the SETs. A failed SET is therefore tolerated
    only when the locked-in value already matches the required setting.
    """
    required = (
        ("enable_external_access", "false"),
        ("lock_configuration", "true"),
    )
    try:
        conn.execute("SET enable_progress_bar = false;")
    except duckdb.Error:
        pass  # cosmetic only; instance may already be locked
    for name, expected in required:
        try:
            conn.execute(f"SET {name} = {expected};")
        except duckdb.Error as exc:
            actual = str(conn.execute(f"SELECT current_setting('{name}')").fetchone()[0])
            if actual.lower() != expected:
                raise RuntimeError(
                    f"DuckDB sandbox setting '{name}' is '{actual}', expected '{expected}', "
                    "and the configuration is locked — refusing to serve queries."
                ) from exc


def create_session() -> duckdb.DuckDBPyConnection:
    """Open a read-only connection to the warehouse, ready for queries."""
    return get_connection(read_only=True)


# ── Schema introspection ───────────────────────────────────────────────


def get_schema_info(
    conn: duckdb.DuckDBPyConnection,
) -> dict[str, list[tuple[str, str, str]]]:
    """
    Introspect the warehouse schema for prompt context.

    Returns:
        dict: "schema.table" -> [(column_name, data_type, "")]

    Only exposed schemas are included; blocked schemas, dlt bookkeeping
    tables, PII lookup tables, and PII columns (name, DOB, raw IDs) are
    excluded. Fully-qualified table names
    are used as keys so generated SQL references e.g. ``main_core.dim_students``.
    """
    exposed = set(get_exposed_schemas())

    rows = conn.execute(
        """
        SELECT table_schema, table_name, column_name, data_type, ordinal_position
        FROM information_schema.columns
        ORDER BY table_schema, table_name, ordinal_position
        """
    ).fetchall()

    schema: dict[str, list[tuple[str, str, str]]] = {}
    for table_schema, table_name, col_name, data_type, _pos in rows:
        if _is_blocked_schema(table_schema):
            continue
        if table_schema not in exposed:
            continue
        if _is_blocked_table(table_name):
            continue
        key = f"{table_schema}.{table_name}"
        if col_name.lower() in _get_pii_columns(key):
            continue
        schema.setdefault(key, []).append((col_name, data_type, ""))
    return schema


# ── JSON envelope parsing ──────────────────────────────────────────────


def _try_parse_json_envelope(text: str) -> str | None:
    """
    Try to parse the LLM output as either:
      1. Canonical Hop 1 tool call:
         {"tool": "execute_duckdb_query", "arguments": {"explanation": "...", "sql": "SELECT ..."}}
      2. Legacy JSON envelope:
         {"sql": "SELECT ...", "explanation": "..."}
    Uses ``json.JSONDecoder().raw_decode`` scanning from each ``{`` so escaped
    quotes and nested JSON objects inside prose are handled accurately.
    """
    decoder = json.JSONDecoder()
    idx = text.find("{")
    while idx != -1:
        try:
            obj, _end = decoder.raw_decode(text, idx)
            if isinstance(obj, dict):
                if isinstance(obj.get("arguments"), dict) and "sql" in obj["arguments"]:
                    return str(obj["arguments"]["sql"])
                if "sql" in obj:
                    return str(obj["sql"])
        except (json.JSONDecodeError, KeyError, TypeError):
            pass
        idx = text.find("{", idx + 1)
    return None


# ── SQL extraction ─────────────────────────────────────────────────────


def extract_sql(raw_llm_output: str) -> str:
    """
    Extract SQL from LLM output. Tries, in order:
      1. JSON envelope: {"sql": "...", "explanation": "..."}
      2. ```sql ... ``` markdown block
      3. Generic ``` ... ``` code block
      4. Raw text fallback
    Always strips trailing semicolons (they break subquery wrapping).
    """
    json_sql = _try_parse_json_envelope(raw_llm_output)
    if json_sql:
        return json_sql.strip().rstrip(";")

    sql_match = re.search(r"```sql\s*\n?(.*?)```", raw_llm_output, re.DOTALL | re.IGNORECASE)
    if sql_match:
        return sql_match.group(1).strip().rstrip(";")

    code_match = re.search(r"```\s*\n?(.*?)```", raw_llm_output, re.DOTALL)
    if code_match:
        return code_match.group(1).strip().rstrip(";")

    return raw_llm_output.strip().rstrip(";")


# ── SQL validation ─────────────────────────────────────────────────────


def validate_sql(sql: str, conn: duckdb.DuckDBPyConnection | None = None) -> None:
    """
    Validate that the SQL is safe and refers to real columns.

    Layer 1 — static checks (always run):
      - Not empty
      - No forbidden tokens (DROP, DELETE, INSERT, etc.)
      - Contains SELECT
      - No table-valued file readers (read_parquet, read_csv, read_text, ...)
      - No wildcard SELECT * against PII-bearing protected tables

    Layer 2 — schema-aware validation (if conn provided):
      - Runs EXPLAIN against the live warehouse to catch missing columns,
        unknown tables, and syntax errors before execution.

    Raises ValueError with a user-facing message on any failure.
    """
    if not sql:
        raise ValueError("Empty SQL query — nothing to execute.")

    # Forbidden tokens FIRST (DROP/INSERT don't contain SELECT but are worse).
    sql_lower = sql.lower()
    for token in FORBIDDEN_TOKENS:
        if re.search(rf"\b{token}\b", sql_lower):
            raise ValueError(
                f"Forbidden operation detected: '{token}'. Only SELECT queries are allowed."
            )

    if "SELECT" not in sql.upper():
        raise ValueError("Only SELECT queries are allowed. No SELECT found.")

    # Block table-valued file readers (read_parquet, read_csv, read_text, ...).
    # These would let a query escape the warehouse catalog and read arbitrary
    # files (including raw PII Parquet) from disk.
    fn_match = _FORBIDDEN_FUNCTION_RE.search(sql)
    if fn_match:
        raise ValueError(
            f"Forbidden file-reading function detected: '{fn_match.group(1).lower()}'. "
            "Only queries against warehouse tables are allowed."
        )

    # Block wildcard SELECT * / alias.* against PII-bearing protected tables.
    if _WILDCARD_SELECT_RE.search(sql):
        for name in PROTECTED_TABLE_NAMES:
            if re.search(rf"\b{re.escape(name)}\b", sql_lower):
                raise ValueError(
                    f"Wildcard SELECT * against protected table '{name}' is not allowed. "
                    "Select only the specific non-PII columns you need."
                )

    for blocked in BLOCKED_SCHEMAS:
        if re.search(rf"\b{re.escape(blocked)}\.", sql_lower):
            raise ValueError(
                f"Reference to blocked schema detected: '{blocked}'. "
                "Only queries against exposed schemas are allowed."
            )
    for pat in _BLOCKED_SCHEMA_PATTERNS:
        if pat.search(sql_lower):
            raise ValueError(
                "Reference to a blocked schema pattern detected. "
                "Only queries against exposed schemas are allowed."
            )

    no_strings = _SINGLE_QUOTED_LITERAL_RE.sub("''", sql)
    no_comments = _SQL_COMMENT_RE.sub(" ", no_strings)
    normalized_lower = _DOUBLE_QUOTED_IDENT_RE.sub(
        lambda m: m.group(1).replace('""', '"'), no_comments
    ).lower()

    if _WILDCARD_SELECT_RE.search(normalized_lower):
        for name in PROTECTED_TABLE_NAMES:
            if re.search(rf"\b{re.escape(name)}\b", normalized_lower):
                raise ValueError(
                    f"Wildcard SELECT * against protected table '{name}' is not allowed. "
                    "Select only the specific non-PII columns you need."
                )

    allowed = {s.lower() for s in get_exposed_schemas()}
    ast = _serialize_sql_ast(sql, conn=conn)
    if ast is not None and not ast.get("error", False):
        stmts = ast.get("statements") or []
        if len(stmts) != 1:
            raise ValueError("Only a single SELECT statement is allowed.")
        _validate_ast_node(stmts[0].get("node"), allowed, {"_safe", "_base", "_desc"})
    else:
        for qualifier in re.findall(
            r"\b(?:from|join)\s+([a-z_][a-z0-9_]*)\s*\.\s*[a-z_][a-z0-9_]*",
            normalized_lower,
        ):
            if qualifier not in allowed:
                raise ValueError(
                    f"Query references '{qualifier}', which is outside the exposed schemas "
                    f"({', '.join(sorted(allowed))})."
                )

    pii_token_match = _FORBIDDEN_PII_TOKEN_RE.search(normalized_lower)
    if pii_token_match:
        raise ValueError(
            f"Forbidden staging or PII identifier detected: '{pii_token_match.group(0).strip()}'. "
            "Use pseudonymized core or analytics columns only."
        )

    if conn is not None:
        try:
            conn.execute(f"EXPLAIN {sql}")
        except duckdb.Error as e:
            msg = str(e).strip()
            for prefix in ["Parser Error: ", "Catalog Error: ", "Binder Error: "]:
                if msg.startswith(prefix):
                    msg = msg[len(prefix) :]
            raise ValueError(f"SQL validation failed: {msg}") from e


# ── Timeout helper ─────────────────────────────────────────────────────


class QueryTimeoutError(TimeoutError):
    """Raised when a query exceeds the time budget."""

    pass


def _execute_with_timeout(
    conn: duckdb.DuckDBPyConnection,
    sql: str,
    timeout_sec: int,
):
    """
    Execute SQL with a Python-level timeout via conn.interrupt().

    DuckDB has no SET query_timeout, so we use a watchdog thread that calls
    conn.interrupt() after the deadline.
    """
    result = {"df": None, "error": None}
    done = threading.Event()

    def run():
        try:
            result["df"] = conn.execute(sql).fetchdf()
        except Exception as e:
            result["error"] = e
        finally:
            done.set()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()

    if not done.wait(timeout=timeout_sec):
        try:
            conn.interrupt()
        except Exception:
            pass
        thread.join(timeout=2)
        try:
            conn.close()
        except Exception:
            pass
        raise QueryTimeoutError(f"Query timed out after {timeout_sec}s.")

    if result["error"]:
        raise result["error"]

    return result["df"]


# ── Safe SQL execution ─────────────────────────────────────────────────


def execute_safe(
    conn: duckdb.DuckDBPyConnection,
    raw_llm_output: str,
    timeout_sec: int = QUERY_TIMEOUT_SEC,
) -> tuple[str, pd.DataFrame]:
    """
    Extract, validate, and execute LLM-generated SQL.

    Pipeline:
      1. extract_sql() — parse JSON / ```sql``` / raw
      2. validate_sql() — static checks + schema-aware EXPLAIN
      3. Wrap in SELECT * FROM (<query>) AS _safe LIMIT {MAX_RESULT_ROWS}
      4. Execute with a watchdog timeout
      5. Return (cleaned_sql, dataframe)

    Returns:
        (cleaned_sql, pandas.DataFrame)

    Raises:
        ValueError: if SQL is invalid or references unknown columns/tables.
        QueryTimeoutError: if execution exceeds timeout_sec.
        duckdb.Error: on database-level failures.
    """
    sql = extract_sql(raw_llm_output)
    validate_sql(sql, conn=conn)

    safe_sql = f"SELECT * FROM (\n{sql}\n) AS _safe LIMIT {MAX_RESULT_ROWS}"
    df = _execute_with_timeout(conn, safe_sql, timeout_sec)

    return sql, df


# ── Two-Hop Protocol Primitives (Self-Healing Errors, Result Summary, Filter CTEs) ──


def format_duckdb_error(exc: Exception) -> dict:
    """Format a DuckDB or SQL validation exception into the canonical Hop 1b `duckdb_execution_error` payload.

    Preserves DuckDB's `Candidate bindings` hints so a 1.5B-3B model can self-heal column/table mistakes.
    """
    raw_msg = str(exc.__cause__ if exc.__cause__ else exc).strip()
    error_type = "ExecutionError"
    for prefix, label in (
        ("Binder Error:", "BinderError"),
        ("Catalog Error:", "CatalogError"),
        ("Parser Error:", "ParserError"),
        ("Conversion Error:", "ConversionError"),
    ):
        if raw_msg.startswith(prefix):
            error_type = label
            raw_msg = raw_msg[len(prefix) :].strip()
            break
    else:
        if isinstance(exc, ValueError):
            error_type = "ValidationError"
            if raw_msg.startswith("SQL validation failed:"):
                raw_msg = raw_msg[len("SQL validation failed:") :].strip()

    return {
        "status": "error",
        "error_type": error_type,
        "message": raw_msg,
    }


def _json_safe_scalar(val):
    """Convert dates, timestamps, decimals, numpy scalars, and NaNs into JSON-safe primitives."""
    if val is None:
        return None
    if hasattr(val, "item") and callable(val.item):
        try:
            val = val.item()
        except Exception:
            pass
    if hasattr(val, "isoformat"):
        return val.isoformat()
    try:
        import math

        if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
            return None
    except Exception:
        pass
    if isinstance(val, int | float | str | bool):
        return val
    return str(val)


def compute_result_summary(
    conn: duckdb.DuckDBPyConnection,
    raw_llm_output: str,
    query_id: str = "q_default",
    max_sample_rows: int = 3,
    timeout_sec: int = QUERY_TIMEOUT_SEC,
) -> tuple[str, pd.DataFrame, dict]:
    """Execute a Hop 1 SQL query and compute the compact ~150-token `duckdb_result_summary` for Hop 2.

    Returns:
        `(cleaned_sql, df, result_summary_dict)`
    """
    sql, df = execute_safe(conn, raw_llm_output, timeout_sec=timeout_sec)

    # Describe logical DuckDB column types
    desc_rows = conn.execute(f"DESCRIBE SELECT * FROM (\n{sql}\n) AS _desc").fetchall()
    col_types = {row[0]: str(row[1]) for row in desc_rows}

    row_count = int(len(df))
    columns_meta: list[dict] = []

    for col_name in df.columns:
        series = df[col_name]
        logical_type = col_types.get(col_name, str(series.dtype).upper())
        null_count = int(series.isna().sum())
        non_null = series.dropna()
        distinct_count = int(non_null.nunique()) if len(non_null) > 0 else 0

        col_entry: dict = {
            "name": str(col_name),
            "type": logical_type,
            "distinct_count": distinct_count,
            "null_count": null_count,
        }

        upper_t = logical_type.upper()
        is_num_or_date = any(
            k in upper_t
            for k in ("INT", "DOUBLE", "FLOAT", "DECIMAL", "NUMERIC", "REAL", "DATE", "TIME")
        )
        if is_num_or_date and len(non_null) > 0:
            col_entry["min"] = _json_safe_scalar(non_null.min())
            col_entry["max"] = _json_safe_scalar(non_null.max())
        elif len(non_null) > 0:
            unique_vals = [_json_safe_scalar(v) for v in non_null.unique()[:3]]
            col_entry["sample_values"] = unique_vals

        columns_meta.append(col_entry)

    sample_rows: list[list] = []
    for _, row in df.head(max_sample_rows).iterrows():
        sample_rows.append([_json_safe_scalar(v) for v in row.tolist()])

    summary = {
        "status": "ok",
        "query_id": query_id,
        "row_count": row_count,
        "columns": columns_meta,
        "sample_rows": sample_rows,
    }
    return sql, df, summary


def apply_query_filters(
    conn: duckdb.DuckDBPyConnection,
    base_sql: str,
    filters: list[dict],
    timeout_sec: int = QUERY_TIMEOUT_SEC,
) -> pd.DataFrame:
    """Zero-LLM `FilterBar` execution: wrap `base_sql` in a parameterized outer CTE (`WITH _base AS (...)`).

    Supported filter items in `filters`:
      - `{"column": "spend_month", "control_type": "date_range", "min": "2026-06-01", "max": "2026-09-01"}`
      - `{"column": "category", "control_type": "multi_select", "values": ["Groceries", "Utilities"]}`
      - `{"column": "category", "control_type": "single_select", "value": "Groceries"}`
      - `{"column": "total_spend", "control_type": "numeric_range", "min": 100.0, "max": 900.0}`
      - `{"column": "merchant_name", "control_type": "search", "query": "Trader"}`
    """
    cleaned_base = extract_sql(base_sql)
    validate_sql(cleaned_base, conn=conn)

    # Introspect valid output column names from the base query to prevent SQL injection via column names
    desc_rows = conn.execute(f"DESCRIBE SELECT * FROM (\n{cleaned_base}\n) AS _desc").fetchall()
    valid_cols = {str(r[0]) for r in desc_rows}

    where_clauses: list[str] = []
    params: list = []

    for f in filters or []:
        col = f.get("column")
        if not isinstance(col, str) or col not in valid_cols:
            raise ValueError(
                f"Invalid filter column '{col}'. Allowed columns: {sorted(valid_cols)}"
            )

        quoted_col = f'"{col}"'
        ctrl_type = f.get("control_type")

        if ctrl_type in ("date_range", "numeric_range"):
            if f.get("min") is not None:
                where_clauses.append(f"{quoted_col} >= ?")
                params.append(f["min"])
            if f.get("max") is not None:
                where_clauses.append(f"{quoted_col} <= ?")
                params.append(f["max"])
        elif ctrl_type == "multi_select":
            vals = f.get("values") or []
            if vals:
                placeholders = ", ".join("?" for _ in vals)
                where_clauses.append(f"{quoted_col} IN ({placeholders})")
                params.extend(vals)
        elif ctrl_type == "single_select":
            if f.get("value") is not None:
                where_clauses.append(f"{quoted_col} = ?")
                params.append(f["value"])
        elif ctrl_type == "search":
            q = f.get("query")
            if isinstance(q, str) and q.strip():
                where_clauses.append(f"CAST({quoted_col} AS VARCHAR) ILIKE ?")
                params.append(f"%{q.strip()}%")
        else:
            raise ValueError(f"Unsupported filter control_type: {ctrl_type!r}")

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    wrapped_sql = (
        f"WITH _base AS (\n{cleaned_base}\n)\n"
        f"SELECT * FROM _base\n"
        f"{where_sql}\n"
        f"LIMIT {MAX_RESULT_ROWS}"
    )

    result = {"df": None, "error": None}
    done = threading.Event()

    def run():
        try:
            result["df"] = conn.execute(wrapped_sql, params).fetchdf()
        except Exception as e:
            result["error"] = e
        finally:
            done.set()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()

    if not done.wait(timeout=timeout_sec):
        try:
            conn.interrupt()
        except Exception:
            pass
        thread.join(timeout=2)
        try:
            conn.close()
        except Exception:
            pass
        raise QueryTimeoutError(f"Filtered query timed out after {timeout_sec}s.")

    if result["error"]:
        raise result["error"]

    return result["df"]
