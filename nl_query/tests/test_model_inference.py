"""test_model_inference.py — Model inference and prompt assembly tests.

Covers:
  - Prompt assembly (system prompt, schema context, few-shot examples)
  - Model singleton caching (load_model, get_model)
  - SQL generation with mocked LLM
  - Streaming generator behavior
  - JSON envelope parsing via extract_sql

These tests mock the LLM so no 14B model is loaded.
"""

from unittest.mock import MagicMock, patch

from data_engine import extract_sql
from prompts import (
    DEFAULT_SCHEMA,
    FEW_SHOT_EXAMPLES,
    SYSTEM_PROMPT,
    build_few_shot_block,
    build_prompt,
    build_schema_context,
)

# ── Prompt assembly ────────────────────────────────────────────────────


class TestBuildPrompt:
    """build_prompt() should assemble all prompt components correctly."""

    def test_includes_system_prompt(self):
        prompt = build_prompt("test question")
        assert "expert DuckDB SQL developer" in prompt

    def test_includes_user_question(self):
        prompt = build_prompt("How many students?")
        assert "How many students?" in prompt

    def test_includes_schema_tables(self):
        prompt = build_prompt("test")
        assert "main_core.dim_students" in prompt
        assert "main_core.fact_attendance" in prompt

    def test_includes_column_names(self):
        prompt = build_prompt("test")
        assert "student_id_hash" in prompt
        assert "academic_year" in prompt
        assert "attendance_rate" in prompt

    def test_includes_few_shot_examples(self):
        prompt = build_prompt("test")
        assert "Examples:" in prompt
        assert FEW_SHOT_EXAMPLES[0]["question"] in prompt

    def test_terminates_with_assistant_turn(self):
        prompt = build_prompt("test")
        assert prompt.rstrip().endswith("<|im_start|>assistant")

    def test_question_in_user_turn(self):
        prompt = build_prompt("UNIQUE_QUESTION_123")
        assert "Question: UNIQUE_QUESTION_123" in prompt

    def test_custom_schema(self):
        custom_schema = {"test_table": [("col_a", "INTEGER", "A column")]}
        custom_examples = [{"question": "Q", "sql": "SELECT 1 FROM test_table"}]
        prompt = build_prompt("test", schema=custom_schema, examples=custom_examples)
        assert "test_table" in prompt
        assert "col_a" in prompt
        assert FEW_SHOT_EXAMPLES[0]["question"] not in prompt

    def test_custom_examples(self):
        custom_examples = [{"question": "Q1", "sql": "SELECT 1"}]
        prompt = build_prompt("test", examples=custom_examples)
        assert "Q1" in prompt
        assert "SELECT 1" in prompt


# ── Schema context builder ─────────────────────────────────────────────


class TestBuildSchemaContext:
    """build_schema_context() should format table docs correctly."""

    def test_formats_single_table(self):
        tables = {"t": [("c1", "INT", "desc1")]}
        result = build_schema_context(tables)
        assert "Table: t" in result
        assert "c1 (INT)" in result
        assert "desc1" in result

    def test_formats_multiple_tables(self):
        tables = {"t1": [("a", "INT", "col a")], "t2": [("b", "VARCHAR", "col b")]}
        result = build_schema_context(tables)
        assert "1. Table: t1" in result
        assert "2. Table: t2" in result

    def test_handles_empty_description(self):
        """Live introspection passes empty descriptions; should still render."""
        tables = {"t": [("c1", "VARCHAR", "")]}
        result = build_schema_context(tables)
        assert "c1 (VARCHAR)" in result

    def test_default_schema_is_complete(self):
        result = build_schema_context(DEFAULT_SCHEMA)
        assert "main_core.dim_students" in result
        assert "student_id_hash" in result
        assert "academic_year" in result


# ── Few-shot block builder ─────────────────────────────────────────────


class TestBuildFewShotBlock:
    def test_includes_all_examples(self):
        result = build_few_shot_block()
        for ex in FEW_SHOT_EXAMPLES:
            assert ex["question"] in result
            assert ex["sql"] in result

    def test_sql_in_code_blocks(self):
        result = build_few_shot_block()
        assert "```sql" in result

    def test_custom_examples(self):
        custom = [{"question": "Q", "sql": "S"}]
        result = build_few_shot_block(custom)
        assert "Q" in result
        assert "S" in result
        assert FEW_SHOT_EXAMPLES[0]["question"] not in result


# ── Adapter resolution ─────────────────────────────────────────────────


class TestAdapterResolution:
    """The adapter repo should resolve from env, local path, or HF."""

    def test_env_override_takes_priority(self, monkeypatch):
        import model_inference

        monkeypatch.setenv("LFED_ADAPTER_REPO", "my-org/my-adapter")
        assert model_inference._resolve_adapter() == "my-org/my-adapter"

    def test_local_path_used_when_present(self, monkeypatch, tmp_path):
        import model_inference

        monkeypatch.delenv("LFED_ADAPTER_REPO", raising=False)
        fake = tmp_path / "fake-adapter"
        fake.mkdir()
        monkeypatch.setattr(model_inference, "_LOCAL_ADAPTER", str(fake))
        assert model_inference._resolve_adapter() == str(fake)

    def test_hf_fallback_when_local_absent(self, monkeypatch, tmp_path):
        import model_inference

        monkeypatch.delenv("LFED_ADAPTER_REPO", raising=False)
        monkeypatch.setattr(model_inference, "_LOCAL_ADAPTER", "/nonexistent/path")
        result = model_inference._resolve_adapter()
        assert result == model_inference._HF_ADAPTER
        assert "KDDSTLC" in result


# ── Model singleton ────────────────────────────────────────────────────


class TestModelSingleton:
    def test_get_model_returns_none_before_load(self):
        import model_inference

        model_inference._llm = None
        assert model_inference.get_model() is None

    def test_load_model_caches_instance(self):
        import model_inference

        original = model_inference._llm
        with patch("model_inference.TransformersLLM") as mock_class:
            mock_llama = MagicMock()
            mock_class.return_value = mock_llama
            model_inference._llm = None
            result = model_inference.load_model()
            assert result is mock_llama
            assert model_inference.get_model() is mock_llama
            assert model_inference.load_model() is mock_llama
            mock_class.assert_called_once()
        model_inference._llm = original


# ── SQL generation (mocked) ────────────────────────────────────────────


class TestGenerateSql:
    def test_generates_sql_with_mock_llm(self):
        import model_inference

        mock_llm = MagicMock()
        mock_llm.return_value = {"choices": [{"text": "```sql\nSELECT 1\n```"}]}
        raw, prompt = model_inference.generate_sql("How many students?", llm=mock_llm)
        assert "SELECT 1" in raw
        assert "How many students?" in prompt
        mock_llm.assert_called_once()

    def test_generates_sql_with_custom_params(self):
        import model_inference

        mock_llm = MagicMock()
        mock_llm.return_value = {"choices": [{"text": "SELECT 2"}]}
        raw, _ = model_inference.generate_sql("test", llm=mock_llm, max_tokens=100, temperature=0.5)
        call_kwargs = mock_llm.call_args.kwargs
        assert call_kwargs["max_tokens"] == 100
        assert call_kwargs["temperature"] == 0.5


# ── Streaming generation (mocked) ──────────────────────────────────────


class TestGenerateSqlStreaming:
    def test_yields_accumulated_text(self):
        import model_inference

        mock_llm = MagicMock()
        mock_llm.return_value = iter(
            [
                {"choices": [{"text": "SE"}]},
                {"choices": [{"text": "LECT"}]},
                {"choices": [{"text": " 1"}]},
            ]
        )
        chunks = list(model_inference.generate_sql_streaming("test question", llm=mock_llm))
        assert len(chunks) >= 1
        assert chunks[-1] == "SELECT 1"

    def test_stops_on_double_newline(self):
        import model_inference

        mock_llm = MagicMock()
        mock_llm.return_value = iter(
            [
                {"choices": [{"text": "SELECT 1\n"}]},
                {"choices": [{"text": "\n"}]},
                {"choices": [{"text": "SHOULD NOT APPEAR"}]},
            ]
        )
        chunks = list(model_inference.generate_sql_streaming("test", llm=mock_llm))
        full = "".join(chunks)
        assert "SHOULD NOT APPEAR" not in full
        assert "SELECT 1" in full


# ── JSON envelope → SQL extraction ─────────────────────────────────────


class TestJsonEnvelopeExtraction:
    def test_extracts_sql_from_json(self):
        raw = '{"sql": "SELECT COUNT(*) FROM main_core.fact_attendance", "explanation": "counts"}'
        assert extract_sql(raw) == "SELECT COUNT(*) FROM main_core.fact_attendance"

    def test_json_with_newlines_in_sql(self):
        raw = '{"sql": "SELECT a,\\nb\\nFROM t", "explanation": "multi-line"}'
        assert "SELECT a," in extract_sql(raw)

    def test_json_fallback_to_sql_block(self):
        raw = '{"not_sql": "value"}\n```sql\nSELECT 42\n```'
        assert extract_sql(raw) == "SELECT 42"


# ── System prompt quality ──────────────────────────────────────────────


class TestSystemPrompt:
    def test_mentions_duckdb(self):
        assert "DuckDB" in SYSTEM_PROMPT

    def test_forbids_destructive_ops(self):
        assert "INSERT" in SYSTEM_PROMPT or "SELECT statements" in SYSTEM_PROMPT

    def test_requires_sql_blocks(self):
        assert "```sql" in SYSTEM_PROMPT

    def test_mentions_boolean_syntax(self):
        assert "TRUE" in SYSTEM_PROMPT or "BOOLEAN" in SYSTEM_PROMPT
