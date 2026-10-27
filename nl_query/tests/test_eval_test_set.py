"""test_eval_test_set.py — Validate the 20-prompt eval test set.

Every gold SQL in nl_query/eval_test_set.jsonl must:
  1. Parse (EXPLAIN) against the live warehouse
  2. Execute without error (returns rows, possibly empty)
  3. Pass the forbidden-token / read-only guard

This is the end-to-end gate: if any gold SQL fails, the eval harness
would score the model unfairly. Run before driving the prompts through
the PromptUp UI (Gradio app).
"""

import json
from pathlib import Path

import pytest
from conftest import warehouse_available

EVAL_SET = Path(__file__).resolve().parent.parent / "eval_test_set.jsonl"


def _load_items():
    if not EVAL_SET.exists():
        return []
    items = []
    with EVAL_SET.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return items


ITEMS = _load_items()


@pytest.mark.skipif(not warehouse_available(), reason="No warehouse available")
class TestEvalTestSet:
    """All 20 gold SQL queries must execute against the live warehouse."""

    def test_set_has_20_items(self):
        assert len(ITEMS) == 20, f"Expected 20 prompts, got {len(ITEMS)}"

    def test_every_item_has_required_fields(self):
        for item in ITEMS:
            assert "id" in item, item
            assert "question" in item, item
            assert "gold_sql" in item, item
            assert "path" in item, item
            assert "difficulty" in item, item

    @pytest.mark.parametrize("item", ITEMS, ids=[i["id"] for i in ITEMS])
    def test_gold_sql_validates_and_executes(self, item, db):
        from data_engine import validate_sql

        sql = item["gold_sql"]
        # Must pass the forbidden-token / SELECT-only guard
        validate_sql(sql, conn=db)
        # Must EXPLAIN (schema-aware)
        db.execute(f"EXPLAIN {sql}")
        # Must execute (returns a row set, possibly empty)
        rows = db.execute(sql).fetchall()
        assert isinstance(rows, list)

    @pytest.mark.parametrize("item", ITEMS, ids=[i["id"] for i in ITEMS])
    def test_gold_sql_is_select_only(self, item):
        from data_engine import FORBIDDEN_TOKENS

        sql_lower = item["gold_sql"].lower()
        for token in FORBIDDEN_TOKENS:
            assert token not in sql_lower, f"{item['id']}: forbidden token '{token}'"

    def test_prompt_in_few_shot_set(self):
        """Each question in the eval set should also be a few-shot
        example in prompts.py so the model has seen the pattern."""
        from prompts import GAP_FEWSHOT_EXAMPLES

        few_shot_questions = {ex["question"] for ex in GAP_FEWSHOT_EXAMPLES}
        for item in ITEMS:
            assert (
                item["question"] in few_shot_questions
            ), f"{item['id']}: question not in GAP_FEWSHOT_EXAMPLES"
