"""
eval.py — Evaluation harness for NL→SQL models.

Runs a held-out test set through the model, extracts SQL, executes it
against the real warehouse, and compares results to gold SQL.

Captures full per-question traces (raw model output, extracted SQL, gold
SQL, execution match, latency, device, errors) and optionally writes them
to a JSONL file for offline review.

Usage:
    python eval.py --test-set eval_test_set.jsonl
    python eval.py --test-set eval_test_set.jsonl --adapter KDDSTLC/lfed-qwen2.5-coder-14b-sql-lora-warehouse-r64
    python eval.py --test-set eval_test_set.jsonl --traces traces.jsonl
    python eval.py --test-set eval_test_set.jsonl --adapter KDDSTLC/lfed-qwen2.5-coder-14b-sql-lora  # old model
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as _dt
import json
import os
import platform
import re
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


def _detect_device() -> str:
    """Best-effort device label for trace context."""
    try:
        import torch

        if torch.cuda.is_available():
            return f"cuda:{torch.cuda.device_count()}"
        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            return "mps"
        return "cpu"
    except Exception:
        return "unknown"


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
    traces_path: str | None = None,
) -> EvalResult:
    """Run the eval harness against a test set with a specified adapter.

    Args:
        traces_path: If set, write one JSON line per question with full
            trace data (raw output, extracted SQL, gold, match, latency,
            device, error) for offline review.
    """
    items = load_test_set(test_set_path)
    result = EvalResult(total=len(items))

    os.environ["LFED_ADAPTER_REPO"] = adapter_repo

    # Force model reload with the specified adapter
    import model_inference

    model_inference._llm = None

    conn = duckdb.connect(warehouse_path, read_only=True)
    device = _detect_device()
    run_meta = {
        "adapter": adapter_repo,
        "warehouse": warehouse_path,
        "device": device,
        "platform": platform.platform(),
        "max_tokens": max_tokens,
        "timeout_sec": timeout_sec,
        "started_at": _dt.datetime.now(_dt.UTC).isoformat(),
        "test_set": str(test_set_path),
        "n_items": len(items),
    }
    print(f"📊 Eval run: device={device} items={len(items)} adapter={adapter_repo}")

    traces_file = open(traces_path, "w") if traces_path else None
    if traces_file:
        traces_file.write(json.dumps({"type": "run_meta", **run_meta}) + "\n")

    for item in items:
        qid = item["id"]
        question = item["question"]
        gold_sql = item["gold_sql"]

        entry = {
            "id": qid,
            "question": question,
            "path": item.get("path", ""),
            "difficulty": item.get("difficulty", ""),
            "label": item.get("label", ""),
            "device": device,
            "timestamp": _dt.datetime.now(_dt.UTC).isoformat(),
        }

        t0 = time.time()
        try:
            raw_output, prompt = generate_sql(question, max_tokens=max_tokens)
            pred_sql = extract_sql(raw_output)
            entry["pred_sql"] = pred_sql
            entry["raw_output"] = raw_output
            entry["prompt_len"] = len(prompt)
            entry["generation_sec"] = round(time.time() - t0, 2)

            # Execute gold
            gold_rows = conn.execute(gold_sql).fetchall()
            entry["gold_row_count"] = len(gold_rows)

            # Validate and execute pred
            validate_sql(pred_sql, conn=conn)
            pred_rows = conn.execute(pred_sql).fetchall()
            entry["pred_row_count"] = len(pred_rows)

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
            entry["error"] = str(e)[:300]
            entry["execution_match"] = False
            entry["exact_match"] = False
            entry["generation_sec"] = round(time.time() - t0, 2)

        entry["latency_sec"] = round(time.time() - t0, 2)
        result.per_question.append(entry)

        if traces_file:
            traces_file.write(json.dumps(entry) + "\n")
            traces_file.flush()

        status = "HIT" if entry.get("execution_match") else "MISS"
        print(
            f"  {qid}: {status} ({entry['latency_sec']}s) "
            f"[{item.get('path', '')}] {item.get('label', '')}"
        )

    conn.close()
    if traces_file:
        summary = {
            "type": "run_summary",
            "total": result.total,
            "execution_hits": result.execution_hits,
            "execution_accuracy": round(result.execution_accuracy, 4),
            "exact_hits": result.exact_hits,
            "exact_accuracy": round(result.exact_accuracy, 4),
            "errors": result.errors,
            "finished_at": _dt.datetime.now(_dt.UTC).isoformat(),
        }
        traces_file.write(json.dumps(summary) + "\n")
        traces_file.close()
        print(f"📝 Traces written to {traces_path}")

    print(f"\n{'=' * 60}")
    print(
        f"Results: {result.execution_hits}/{result.total} execution match ({result.execution_accuracy:.1%})"
    )
    print(f"         {result.exact_hits}/{result.total} exact match ({result.exact_accuracy:.1%})")
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
    parser.add_argument("--warehouse", default="../oss_framework/data/analytics.duckdb")
    parser.add_argument("--output", default=None, help="Save detailed results as JSON")
    parser.add_argument(
        "--traces",
        default=None,
        help="Write per-question traces (raw output, SQL, match, latency, device) as JSONL",
    )
    parser.add_argument("--max-tokens", type=int, default=256, help="Max new tokens per generation")
    args = parser.parse_args()

    adapter = args.adapter or str(
        Path(__file__).resolve().parent.parent / "models" / "lora-warehouse-r64"
    )
    if not Path(adapter).exists():
        adapter = "KDDSTLC/lfed-qwen2.5-coder-14b-sql-lora-warehouse-r64"

    traces = args.traces
    if traces is None:
        # Default to a timestamped traces file next to the test set
        stem = Path(args.test_set).stem
        ts = _dt.datetime.now(_dt.UTC).strftime("%Y%m%d_%H%M%S")
        traces = f"traces_{stem}_{ts}.jsonl"

    result = run_eval(
        adapter,
        args.test_set,
        args.warehouse,
        max_tokens=args.max_tokens,
        traces_path=traces,
    )

    if args.output:
        with open(args.output, "w") as f:
            json.dump(dataclasses.asdict(result), f, indent=2)
        print(f"Detailed results saved to {args.output}")


if __name__ == "__main__":
    main()
