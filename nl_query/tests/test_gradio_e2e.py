"""test_gradio_e2e.py — Gradio app end-to-end tests (mocked LLM).

Tests the full handle_query flow: question -> SQL generation -> extraction ->
validation -> execution -> result formatting. The LLM is mocked so no GPU
is needed. Requires the warehouse at oss_framework/data/analytics.duckdb.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# conftest.py adds the package root to sys.path
from conftest import warehouse_available

try:
    import gradio  # noqa: F401
    GRADIO_AVAILABLE = True
except ImportError:
    GRADIO_AVAILABLE = False


@pytest.fixture
def mock_streaming_llm():
    """Mock LLM that yields SQL in chunks (simulates streaming)."""
    sql = (
        "```sql\n"
        "SELECT COUNT(DISTINCT student_id_hash) AS student_count "
        "FROM main_core.dim_students WHERE academic_year = '2023-2024'\n"
        "```"
    )
    chunks = [sql[i : i + 10] for i in range(0, len(sql), 10)]
    llm = MagicMock()
    llm.return_value = iter([{"choices": [{"text": c}]} for c in chunks])
    return llm


@pytest.mark.skipif(
    not GRADIO_AVAILABLE, reason="gradio not installed"
)
@pytest.mark.skipif(not warehouse_available(), reason="No warehouse available")
class TestHandleQueryE2E:
    """Full end-to-end query flow with mocked LLM."""

    def test_question_to_result(self, mock_streaming_llm):
        import app

        with patch("app.llm", mock_streaming_llm):
            with patch(
                "model_inference.get_model", return_value=mock_streaming_llm
            ):
                results = list(
                    app.handle_query(
                        "How many students were enrolled in 2023-2024?",
                        prior_state=None,
                    )
                )

        # handle_query yields tuples of (prior, sql, df, emoji, status, state)
        # The last yield should be the successful result
        last = results[-1]
        prior, sql, df, emoji, status, state = last
        assert emoji == "\u2705"
        assert sql is not None
        assert "SELECT" in sql.upper()
        assert df is not None
        assert len(df) > 0

    def test_empty_question_returns_error(self):
        import app

        results = list(app.handle_query("", prior_state=None))
        last = results[-1]
        prior, sql, df, emoji, status, state = last
        assert emoji == "\U0001f916"
        assert "ask a question" in status.lower() or "empty" in status.lower()

    def test_invalid_sql_returns_error(self):
        import app

        bad_llm = MagicMock()
        bad_llm.return_value = iter(
            [{"choices": [{"text": "```sql\nDROP TABLE students\n```"}]}]
        )

        with patch("app.llm", bad_llm):
            with patch("model_inference.get_model", return_value=bad_llm):
                results = list(
                    app.handle_query(
                        "Delete all students",
                        prior_state=None,
                    )
                )

        last = results[-1]
        prior, sql, df, emoji, status, state = last
        assert emoji in ("\u26a0\ufe0f", "\u274c")
        assert sql is not None  # SQL was generated (even if invalid)


class TestSchemaIntrospection:
    """Verify the warehouse schema is introspected correctly for prompts."""

    @pytest.mark.skipif(
        not GRADIO_AVAILABLE, reason="gradio not installed"
    )
    @pytest.mark.skipif(
        not warehouse_available(), reason="No warehouse available"
    )
    def test_get_warehouse_schema_returns_dict(self):
        import app

        # Clear cache to force fresh introspection
        app._schema_cache = None
        schema = app.get_warehouse_schema()
        assert isinstance(schema, dict)
        assert len(schema) > 0
        # Should include core tables
        assert any("dim_students" in k for k in schema.keys())
        # Should NOT include PII tables
        assert not any("pii" in k.lower() for k in schema.keys())
        # Should NOT include dlt bookkeeping
        assert not any("_dlt" in k for k in schema.keys())