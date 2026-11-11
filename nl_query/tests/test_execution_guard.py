"""test_execution_guard.py — Security and safety tests.

Covers:
  - SQL extraction (```sql```, generic blocks, JSON envelope, raw)
  - Forbidden tokens (DROP, INSERT, DELETE, etc.)
  - Multi-statement / comment injection
  - Schema-aware validation against the live warehouse
  - End-to-end execute_safe pipeline
"""

import pytest
from data_engine import execute_safe, extract_sql, validate_sql

# ── SQL extraction ─────────────────────────────────────────────────────


class TestExtractSql:
    """extract_sql() should handle all valid input formats."""

    def test_extract_sql_block(self):
        assert extract_sql("```sql\nSELECT 1\n```") == "SELECT 1"

    def test_extract_generic_code_block(self):
        assert extract_sql("```\nSELECT * FROM x\n```") == "SELECT * FROM x"

    def test_extract_json_envelope(self):
        result = extract_sql(
            '{"sql": "SELECT COUNT(*) FROM main_core.dim_students", "explanation": "test"}'
        )
        assert result == "SELECT COUNT(*) FROM main_core.dim_students"

    def test_extract_json_embedded_in_text(self):
        result = extract_sql('Here: {"sql": "SELECT 1"} rest')
        assert result == "SELECT 1"

    def test_extract_fallback_raw(self):
        assert extract_sql("SELECT 42") == "SELECT 42"

    def test_extract_strips_semicolons(self):
        assert extract_sql("```sql\nSELECT 1;\n```") == "SELECT 1"

    def test_extract_handles_multiline_sql(self):
        result = extract_sql("```sql\nSELECT a,\nb,\nc\nFROM t\n```")
        assert "SELECT a," in result
        assert "FROM t" in result

    def test_extract_json_without_sql_key(self):
        result = extract_sql('{"wrong": "key"}')
        assert result == '{"wrong": "key"}'

    def test_extract_malformed_json(self):
        result = extract_sql('{"sql": "SELECT 1"')
        assert "SELECT 1" in result

    def test_extract_json_with_escaped_quotes_and_surrounding_prose(self):
        prose = (
            'Here is the tool call: {"tool": "execute_duckdb_query", "arguments": '
            '{"explanation": "quoted {brace}", "sql": "SELECT \\"school_name\\" FROM main_analytics.school_summary WHERE school_name != \'A\\"B\'"}} Done.'
        )
        extracted = extract_sql(prose)
        assert extracted.startswith('SELECT "school_name"')
        assert "Done." not in extracted


# ── Static validation ──────────────────────────────────────────────────


class TestValidateSqlStatic:
    """validate_sql() static checks (no DB connection needed)."""

    def test_rejects_empty(self):
        with pytest.raises(ValueError, match="Empty"):
            validate_sql("")

    def test_rejects_no_select(self):
        with pytest.raises(ValueError, match="No SELECT"):
            validate_sql("42")

    def test_rejects_drop(self):
        with pytest.raises(ValueError, match="drop"):
            validate_sql("DROP TABLE main_core.dim_students")

    def test_rejects_insert(self):
        with pytest.raises(ValueError, match="insert"):
            validate_sql("INSERT INTO main_core.dim_students VALUES (1)")

    def test_rejects_delete(self):
        with pytest.raises(ValueError, match="delete"):
            validate_sql("DELETE FROM main_core.fact_attendance")

    def test_rejects_update(self):
        with pytest.raises(ValueError, match="update"):
            validate_sql("UPDATE main_core.dim_students SET x = 1")

    def test_rejects_alter(self):
        with pytest.raises(ValueError, match="alter"):
            validate_sql("ALTER TABLE main_core.dim_students ADD COLUMN x INT")

    def test_rejects_truncate(self):
        with pytest.raises(ValueError, match="truncate"):
            validate_sql("TRUNCATE TABLE main_core.dim_students")

    def test_rejects_create(self):
        with pytest.raises(ValueError, match="create"):
            validate_sql("CREATE TABLE hack (x INT)")

    def test_rejects_attach(self):
        with pytest.raises(ValueError, match="attach"):
            validate_sql("ATTACH 'other.duckdb' AS other")

    def test_rejects_pragma(self):
        with pytest.raises(ValueError, match="pragma"):
            validate_sql("PRAGMA database_list")

    def test_allows_valid_select(self):
        validate_sql("SELECT * FROM main_core.fact_attendance")

    def test_rejects_wildcard_on_protected_pii_table(self):
        with pytest.raises(ValueError, match="protected table"):
            validate_sql("SELECT * FROM main_core.dim_students")

    def test_rejects_qualified_wildcard_on_protected_pii_table(self):
        with pytest.raises(ValueError, match="protected table"):
            validate_sql(
                "SELECT s.* FROM main_core.fact_attendance a "
                "JOIN main_core.dim_students s ON a.student_id_hash = s.student_id_hash"
            )

    def test_rejects_read_parquet(self):
        with pytest.raises(ValueError, match="file-reading function"):
            validate_sql("SELECT * FROM read_parquet('/tmp/secret/*.parquet')")

    def test_rejects_read_csv(self):
        with pytest.raises(ValueError, match="file-reading function"):
            validate_sql("SELECT * FROM read_csv_auto('/tmp/pii.csv')")

    def test_rejects_read_text(self):
        with pytest.raises(ValueError, match="file-reading function"):
            validate_sql("SELECT * FROM read_text('/etc/passwd')")

    def test_rejects_glob(self):
        with pytest.raises(ValueError, match="file-reading function"):
            validate_sql("SELECT * FROM glob('/tmp/**')")

    def test_rejects_main_staging_schema(self):
        with pytest.raises(ValueError, match="outside the exposed schemas"):
            validate_sql("SELECT * FROM main_staging.stg_aeries__students")

    def test_rejects_aeries_stage1_schema(self):
        with pytest.raises(ValueError, match="outside the exposed schemas"):
            validate_sql("SELECT StudentID FROM aeries_stage1.students")

    def test_rejects_edu_wh_catalog_reference(self):
        with pytest.raises(ValueError, match="outside the exposed schemas"):
            validate_sql("SELECT * FROM edu_wh.main_core.fact_attendance")

    @pytest.mark.parametrize(
        "forbidden_sql",
        [
            "SELECT student_id_raw FROM main_core.dim_students",
            "SELECT first_name FROM main_core.dim_students",
            "SELECT last_name FROM main_core.dim_students",
            "SELECT date_of_birth FROM main_core.dim_students",
            "SELECT email_raw FROM main_core.dim_students",
            "SELECT * FROM stg_aeries__students",
            "SELECT * FROM stg_cde__schools",
            "SELECT COLUMNS(*) FROM main_core.dim_students",
        ],
    )
    def test_rejects_pii_columns_raw_tokens_and_columns_star(self, forbidden_sql):
        with pytest.raises(ValueError):
            validate_sql(forbidden_sql)

    def test_system_prompt_does_not_advertise_main_staging(self):
        from prompts import SYSTEM_PROMPT

        assert "main_staging" not in SYSTEM_PROMPT


# ── Schema-aware validation ────────────────────────────────────────────


class TestValidateSqlSchema:
    """validate_sql() schema-aware checks (with DB connection)."""

    def test_rejects_unknown_column(self, db):
        with pytest.raises(ValueError) as exc:
            validate_sql("SELECT fake_column FROM main_core.dim_students", conn=db)
        assert "fake_column" in str(exc.value).lower()

    def test_rejects_unknown_table(self, db):
        with pytest.raises(ValueError, match="exist"):
            validate_sql("SELECT * FROM main_core.nonexistent_table", conn=db)

    def test_accepts_valid_query(self, db):
        validate_sql("SELECT student_id_hash FROM main_core.dim_students", conn=db)

    def test_accepts_aggregate_query(self, db):
        validate_sql(
            "SELECT school_id, COUNT(*) FROM main_core.dim_students GROUP BY school_id",
            conn=db,
        )

    def test_accepts_join(self, db):
        validate_sql(
            "SELECT a.student_id_hash, a.attendance_rate, s.school_id "
            "FROM main_core.fact_attendance a "
            "JOIN main_core.dim_students s ON a.student_id_hash = s.student_id_hash",
            conn=db,
        )


# ── Read-only enforcement ──────────────────────────────────────────────


class TestReadOnly:
    """The warehouse connection must reject writes at the engine level."""

    def test_connection_is_read_only(self, db):
        import duckdb

        with pytest.raises(duckdb.Error):
            db.execute("CREATE TABLE main_core.should_fail (x INT)")


# ── Multi-statement attack prevention ──────────────────────────────────


class TestMultiStatement:
    """Multi-statement SQL injection should be blocked."""

    def test_semicolon_injection(self):
        with pytest.raises(ValueError, match="drop"):
            validate_sql("SELECT 1; DROP TABLE main_core.dim_students")

    def test_comment_then_drop(self):
        with pytest.raises(ValueError, match="drop"):
            validate_sql("SELECT 1 -- harmless\nDROP TABLE main_core.dim_students")


# ── End-to-end: execute_safe ───────────────────────────────────────────


class TestExecuteSafe:
    """execute_safe() end-to-end pipeline."""

    def test_valid_query_returns_data(self, db):
        sql, df = execute_safe(
            db, "```sql\nSELECT COUNT(*) AS cnt FROM main_core.dim_students\n```"
        )
        assert sql == "SELECT COUNT(*) AS cnt FROM main_core.dim_students"
        assert df.shape[0] == 1

    def test_invalid_sql_raises(self, db):
        with pytest.raises(ValueError):
            execute_safe(db, "```sql\nSELECT fake FROM main_core.nowhere\n```")

    def test_no_sql_blocks_uses_raw(self, db):
        sql, df = execute_safe(db, "SELECT 1 AS one")
        assert sql == "SELECT 1 AS one"
        assert df.shape == (1, 1)

    def test_limit_wrapping(self, db):
        sql, df = execute_safe(db, "```sql\nSELECT * FROM main_core.fact_attendance\n```")
        assert sql == "SELECT * FROM main_core.fact_attendance"
        assert len(df) <= 1000

    def test_execute_safe_blocks_wildcard_on_protected_table(self, db):
        with pytest.raises(ValueError, match="protected table"):
            execute_safe(db, "```sql\nSELECT * FROM main_core.dim_students\n```")

    def test_execute_safe_blocks_read_parquet(self, db):
        with pytest.raises(ValueError, match="file-reading function"):
            execute_safe(db, "```sql\nSELECT * FROM read_parquet('data/*.parquet')\n```")
