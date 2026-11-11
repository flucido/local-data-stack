"""test_eval_harness.py — Eval harness tests (mocked LLM, no GPU needed)."""

import json
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
        p.write_text('{"id": "q01", "question": "Q", "gold_sql": "SELECT 1"}\nnot json\n')
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

    def test_duplicate_rows_disqualify_a_match(self):
        """A prediction that lost a duplicate row must not score as a match.

        This is the dropped-GROUP-BY case: the aggregated gold returns one row
        per key, the ungrouped prediction returns the key once per source row.
        Set comparison collapsed the repeats and scored it EX.
        """
        from eval import execution_match

        gold_rows = [(1,)]
        pred_rows = [(1,), (1,)]
        assert execution_match(gold_rows, pred_rows) is False
        assert execution_match(pred_rows, gold_rows) is False

    def test_repeated_rows_match_when_counts_agree(self):
        from eval import execution_match

        gold_rows = [(1,), (1,), (2,)]
        pred_rows = [(2,), (1,), (1,)]
        assert execution_match(gold_rows, pred_rows) is True

    def test_duplicate_counts_must_be_exact(self):
        from eval import execution_match

        assert execution_match([(1,), (1,)], [(1,), (1,), (1,)]) is False

    def test_multi_column_duplicates_disqualify_a_match(self):
        from eval import execution_match

        gold_rows = [("A", 10), ("B", 20)]
        pred_rows = [("A", 10), ("B", 20), ("A", 10)]
        assert execution_match(gold_rows, pred_rows) is False


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
        import duckdb
        from eval import run_eval

        # Create a minimal self-contained warehouse so the test works on CI
        warehouse = tmp_path / "test_warehouse.duckdb"
        conn = duckdb.connect(str(warehouse))
        conn.execute("CREATE SCHEMA IF NOT EXISTS main_core")
        conn.execute(
            "CREATE TABLE main_core.dim_students (student_id_hash VARCHAR, academic_year VARCHAR)"
        )
        conn.execute(
            "INSERT INTO main_core.dim_students VALUES ('h1', '2023-2024'), ('h2', '2023-2024')"
        )
        conn.close()

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
            result = run_eval(
                adapter_repo="mock",
                test_set_path=str(test_set),
                warehouse_path=str(warehouse),
            )

        assert result.total == 1
        assert result.execution_hits == 1
        assert result.execution_accuracy == 1.0
