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

import duckdb

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
    conn.execute("SET enable_progress_bar = false;")
    return conn


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
    Try to parse the LLM output as a JSON envelope like:
      {"sql": "SELECT ...", "explanation": "..."}
    Returns the SQL string if found, or None.
    """
    json_match = re.search(r'\{[^{}]*"sql"\s*:\s*"[^"]+"[^{}]*\}', text, re.DOTALL)
    if not json_match:
        return None
    try:
        obj = json.loads(json_match.group(0))
        if isinstance(obj, dict) and "sql" in obj:
            return obj["sql"]
    except (json.JSONDecodeError, KeyError):
        pass
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
        conn.interrupt()
        thread.join(timeout=2)
        raise QueryTimeoutError(f"Query timed out after {timeout_sec}s.")

    if result["error"]:
        raise result["error"]

    return result["df"]


# ── Safe SQL execution ─────────────────────────────────────────────────


def execute_safe(
    conn: duckdb.DuckDBPyConnection,
    raw_llm_output: str,
    timeout_sec: int = QUERY_TIMEOUT_SEC,
) -> tuple[str, DataFrame]:
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
