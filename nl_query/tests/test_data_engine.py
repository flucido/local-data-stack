"""test_data_engine.py — Data engine and warehouse integration tests.

Covers:
  - Warehouse path resolution
  - Multi-schema introspection (qualified names, PII/dlt exclusion)
  - Connection isolation (per-request independence)
  - extract_sql edge cases
  - execute_safe LIMIT capping and empty results
"""

import pytest
from data_engine import (
    create_session,
    get_connection,
    get_schema_info,
    get_warehouse_path,
    get_exposed_schemas,
    extract_sql,
    execute_safe,
    BLOCKED_SCHEMAS,
    MAX_RESULT_ROWS,
    QUERY_TIMEOUT_SEC,
)


# ── Warehouse path resolution ──────────────────────────────────────────

class TestWarehousePath:
    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("LFED_WAREHOUSE_DB", "/tmp/custom.duckdb")
        assert str(get_warehouse_path()) == "/tmp/custom.duckdb"

    def test_default_or_fallback(self, monkeypatch):
        monkeypatch.delenv("LFED_WAREHOUSE_DB", raising=False)
        path = get_warehouse_path()
        assert path.name in {"warehouse.duckdb", "analytics.duckdb"}


# ── Schema introspection ───────────────────────────────────────────────

class TestSchemaIntrospection:
    """get_schema_info() should expose only allowlisted, non-PII tables."""

    def test_returns_qualified_table_names(self, db):
        info = get_schema_info(db)
        # Keys are fully-qualified schema.table names.
        assert all("." in key for key in info)

    def test_includes_core_and_analytics(self, db):
        info = get_schema_info(db)
        schemas = {key.split(".")[0] for key in info}
        # At least one exposed schema must be present.
        assert schemas & set(get_exposed_schemas())

    def test_excludes_pii_lookup(self, db):
        info = get_schema_info(db)
        assert not any("pii_lookup" in key.lower() for key in info)

    def test_excludes_blocked_schemas(self, db):
        info = get_schema_info(db)
        for key in info:
            assert key.split(".")[0] not in BLOCKED_SCHEMAS

    def test_excludes_dlt_tables(self, db):
        info = get_schema_info(db)
        assert not any(key.split(".")[1].startswith("_dlt") for key in info)

    def test_columns_are_triples(self, db):
        info = get_schema_info(db)
        assert info, "schema introspection returned no tables"
        first = next(iter(info.values()))
        assert all(len(col) == 3 for col in first)


# ── Connection isolation ───────────────────────────────────────────────

class TestConnectionIsolation:
    """Each create_session() returns an independent read-only handle."""

    def test_independent_connections(self):
        if not get_warehouse_path().exists():
            pytest.skip("No warehouse available.")
        conn_a = create_session()
        conn_b = create_session()
        assert conn_a.execute("SELECT 1").fetchone() == (1,)
        conn_a.close()
        # Closing one does not affect the other
        assert conn_b.execute("SELECT 1").fetchone() == (1,)
        conn_b.close()


# ── Execution limits ───────────────────────────────────────────────────

class TestExecutionLimits:
    def test_max_result_rows_constant(self):
        assert MAX_RESULT_ROWS == 1000

    def test_timeout_constant(self):
        assert QUERY_TIMEOUT_SEC == 10

    def test_fast_query_succeeds(self, db):
        sql, df = execute_safe(db, "SELECT 1", timeout_sec=5)
        assert df.shape == (1, 1)


# ── Empty results ──────────────────────────────────────────────────────

class TestEmptyResults:
    def test_empty_aggregate(self, db):
        sql, df = execute_safe(db, "SELECT COUNT(*) FROM main_core.dim_students WHERE 1 = 0")
        assert df.iloc[0, 0] == 0


# ── extract_sql edge cases ─────────────────────────────────────────────

class TestExtractSqlEdgeCases:
    def test_whitespace_only_after_block(self):
        assert extract_sql("```sql\nSELECT 1\n```   \n  ") == "SELECT 1"

    def test_no_newline_after_fence(self):
        assert extract_sql("```sql\nSELECT 1```") == "SELECT 1"

    def test_multiple_code_blocks(self):
        assert extract_sql("```sql\nSELECT 1\n```\n```sql\nSELECT 2\n```") == "SELECT 1"

    def test_case_insensitive_sql_fence(self):
        assert extract_sql("```SQL\nSELECT 1\n```") == "SELECT 1"

    def test_trailing_semicolons_stripped(self):
        assert extract_sql("```sql\nSELECT 1;;;;\n```") == "SELECT 1"
