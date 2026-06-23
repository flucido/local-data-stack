"""test_eval_harness.py — Eval harness tests (mocked LLM, no GPU needed)."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestLoadTestSet:
    def test_loads_jsonl(self, tmp_path):
        from eval import load_test_set

        p = tmp_path / "test.jsonl"
        p.write_text(
            json.dumps(
                {
                    "id": "q01",
                    "question": "Q",
                    "gold_sql": "SELECT 1",
                    "path": "core",
                    "difficulty": "easy",
                }
            )
            + "\n"
        )
        items = load_test_set(str(p))
        assert len(items) == 1
        assert items[0]["id"] == "q01"

    def test_skips_malformed_lines(self, tmp_path):
        from eval import load_test_set

        p = tmp_path / "test.jsonl"
        p.write_text(
            '{"id": "q01", "question": "Q", "gold_sql": "SELECT 1"}\nnot json\n'
        )
        items = load_test_set(str(p))
        assert len(items) == 1

    def test_skips_empty_lines(self, tmp_path):
        from eval import load_test_set

        p = tmp_path / "test.jsonl"
        p.write_text(
            '{"id": "q01", "question": "Q", "gold_sql": "SELECT 1"}\n\n{"id": "q02", "question": "Q2", "gold_sql": "SELECT 2"}\n'
        )
        items = load_test_set(str(p))
        assert len(items) == 2


class TestExecutionMatch:
    def test_matching_results_score_hit(self):
        from eval import execution_match

        gold_rows = [(1,), (2,)]
        pred_rows = [(1,), (2,)]
        assert execution_match(gold_rows, pred_rows) is True

    def test_different_order_still_matches(self):
        from eval import execution_match

        gold_rows = [(1,), (2,)]
        pred_rows = [(2,), (1,)]
        assert execution_match(gold_rows, pred_rows) is True

    def test_different_results_score_miss(self):
        from eval import execution_match

        gold_rows = [(1,), (2,)]
        pred_rows = [(1,), (3,)]
        assert execution_match(gold_rows, pred_rows) is False

    def test_empty_vs_nonempty(self):
        from eval import execution_match

        assert execution_match([], [(1,)]) is False
        assert execution_match([], []) is True

    def test_different_length(self):
        from eval import execution_match

        assert execution_match([(1,), (2,)], [(1,)]) is False


class TestExactMatch:
    def test_identical_sql_matches(self):
        from eval import exact_match

        assert exact_match("SELECT 1", "SELECT 1") is True

    def test_whitespace_normalized(self):
        from eval import exact_match

        assert exact_match("SELECT   1", "SELECT 1") is True

    def test_case_normalized(self):
        from eval import exact_match

        assert exact_match("select 1", "SELECT 1") is True

    def test_trailing_semicolon_normalized(self):
        from eval import exact_match

        assert exact_match("SELECT 1;", "SELECT 1") is True

    def test_different_sql_does_not_match(self):
        from eval import exact_match

        assert exact_match("SELECT 1", "SELECT 2") is False


class TestRunEvalMocked:
    def test_full_flow_with_mock_llm(self, tmp_path):
        """Mock LLM returns gold SQL -> should score 100% execution match."""
        from eval import run_eval

        test_set = tmp_path / "test.jsonl"
        test_set.write_text(
            json.dumps(
                {
                    "id": "q01",
                    "question": "How many students?",
                    "gold_sql": "SELECT COUNT(*) AS c FROM main_core.dim_students WHERE academic_year = '2023-2024'",
                    "path": "core",
                    "difficulty": "easy",
                }
            )
            + "\n"
        )

        mock_llm = MagicMock()
        mock_llm.return_value = {
            "choices": [
                {
                    "text": "```sql\nSELECT COUNT(*) AS c FROM main_core.dim_students WHERE academic_year = '2023-2024'\n```"
                }
            ]
        }

        with patch("model_inference.get_model", return_value=mock_llm):
            warehouse = str(
                Path(__file__).resolve().parent.parent.parent
                / "oss_framework"
                / "data"
                / "analytics.duckdb"
            )
            result = run_eval(
                adapter_repo="mock",
                test_set_path=str(test_set),
                warehouse_path=warehouse,
            )

        assert result.total == 1
        assert result.execution_hits == 1
        assert result.execution_accuracy == 1.0