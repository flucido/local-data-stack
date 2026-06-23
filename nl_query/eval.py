"""
eval.py — Evaluation harness for NL→SQL models.

Runs a held-out test set through the model, extracts SQL, executes it
against the real warehouse, and compares results to gold SQL.

Usage:
    python eval.py --test-set eval_test_set.jsonl
    python eval.py --test-set eval_test_set.jsonl --adapter KDDSTLC/lfed-qwen2.5-coder-14b-sql-lora-warehouse-r64
    python eval.py --test-set eval_test_set.jsonl --adapter KDDSTLC/lfed-qwen2.5-coder-14b-sql-lora  # old model
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import re
import sys
import time
from pathlib import Path

import duckdb

from data_engine import extract_sql, validate_sql
from model_inference import generate_sql


@dataclasses.dataclass
class EvalResult:
    total: int = 0
    execution_hits: int = 0
    exact_hits: int = 0
    errors: int = 0
    timeouts: int = 0
    per_question: list[dict] = dataclasses.field(default_factory=list)

    @property
    def execution_accuracy(self) -> float:
        return self.execution_hits / self.total if self.total > 0 else 0.0

    @property
    def exact_accuracy(self) -> float:
        return self.exact_hits / self.total if self.total > 0 else 0.0


def load_test_set(path: str) -> list[dict]:
    """Load a JSONL test set, skipping malformed and empty lines."""
    items = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return items


def execution_match(gold_rows: list, pred_rows: list) -> bool:
    """Compare result sets as unordered collections of tuples."""
    gold_set = {tuple(r) for r in gold_rows}
    pred_set = {tuple(r) for r in pred_rows}
    return gold_set == pred_set


def exact_match(gold_sql: str, pred_sql: str) -> bool:
    """Compare SQL strings after normalization (whitespace, case, semicolons)."""

    def normalize(s: str) -> str:
        s = s.strip().rstrip(";").lower()
        s = re.sub(r"\s+", " ", s)
        return s

    return normalize(gold_sql) == normalize(pred_sql)


def run_eval(
    adapter_repo: str,
    test_set_path: str,
    warehouse_path: str = "../oss_framework/data/analytics.duckdb",
    max_tokens: int = 256,
    timeout_sec: int = 30,
) -> EvalResult:
    """Run the eval harness against a test set with a specified adapter."""
    items = load_test_set(test_set_path)
    result = EvalResult(total=len(items))

    os.environ["LFED_ADAPTER_REPO"] = adapter_repo

    # Force model reload with the specified adapter
    import model_inference

    model_inference._llm = None

    conn = duckdb.connect(warehouse_path, read_only=True)

    for item in items:
        qid = item["id"]
        question = item["question"]
        gold_sql = item["gold_sql"]

        entry = {
            "id": qid,
            "question": question,
            "path": item.get("path", ""),
            "difficulty": item.get("difficulty", ""),
        }

        t0 = time.time()
        try:
            raw_output, _ = generate_sql(question, max_tokens=max_tokens)
            pred_sql = extract_sql(raw_output)
            entry["pred_sql"] = pred_sql
            entry["raw_output"] = raw_output[:200]

            # Execute gold
            gold_rows = conn.execute(gold_sql).fetchall()

            # Validate and execute pred
            validate_sql(pred_sql, conn=conn)
            pred_rows = conn.execute(pred_sql).fetchall()

            if execution_match(gold_rows, pred_rows):
                result.execution_hits += 1
                entry["execution_match"] = True
            else:
                entry["execution_match"] = False
                entry["gold_rows_sample"] = str(gold_rows[:3])
                entry["pred_rows_sample"] = str(pred_rows[:3])

            if exact_match(gold_sql, pred_sql):
                result.exact_hits += 1
                entry["exact_match"] = True
            else:
                entry["exact_match"] = False

        except Exception as e:
            result.errors += 1
            entry["error"] = str(e)[:200]
            entry["execution_match"] = False
            entry["exact_match"] = False

        entry["latency_sec"] = round(time.time() - t0, 2)
        result.per_question.append(entry)

        status = "HIT" if entry.get("execution_match") else "MISS"
        print(f"  {qid}: {status} ({entry['latency_sec']}s) [{item.get('path', '')}]")

    conn.close()

    print(f"\n{'=' * 60}")
    print(
        f"Results: {result.execution_hits}/{result.total} execution match ({result.execution_accuracy:.1%})"
    )
    print(
        f"         {result.exact_hits}/{result.total} exact match ({result.exact_accuracy:.1%})"
    )
    print(f"         {result.errors} errors")
    print(f"{'=' * 60}")

    return result


def main():
    parser = argparse.ArgumentParser(description="Run NL->SQL eval")
    parser.add_argument("--test-set", default="eval_test_set.jsonl")
    parser.add_argument(
        "--adapter",
        default=None,
        help="HF repo id or local path (default: current model_inference config)",
    )
    parser.add_argument(
        "--warehouse", default="../oss_framework/data/analytics.duckdb"
    )
    parser.add_argument(
        "--output", default=None, help="Save detailed results as JSON"
    )
    args = parser.parse_args()

    adapter = args.adapter or str(
        Path(__file__).resolve().parent.parent / "models" / "lora-warehouse-r64"
    )
    if not Path(adapter).exists():
        adapter = "KDDSTLC/lfed-qwen2.5-coder-14b-sql-lora-warehouse-r64"

    result = run_eval(adapter, args.test_set, args.warehouse)

    if args.output:
        with open(args.output, "w") as f:
            json.dump(dataclasses.asdict(result), f, indent=2)
        print(f"Detailed results saved to {args.output}")


if __name__ == "__main__":
    main()