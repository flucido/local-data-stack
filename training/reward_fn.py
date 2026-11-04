"""
reward_fn.py — Execution-Guided Verifiable Reward Function for Two-Hop GRPO Alignment.

Scores candidate `LiquidAI/LFM3-1.7B` completions during online GRPO training:
  - Hop 1 (`execute_duckdb_query`):
      * +0.5 for valid Hop 1 JSON tool-call envelope (`validate_hop1_call`)
      * +1.0 for clean DuckDB execution with `row_count > 0`
      * +1.5 for exact result-set execution match (`EX`) against `gold_sql`
      * -1.0 for malformed JSON or DuckDB `BinderError` / `CatalogError` / `ParserError`
  - Hop 2 (`render_workspace_ui`):
      * +1.0 for valid Hop 2 JSON tool-call envelope (`validate_hop2_call`) with 100% valid
        column bindings against the Hop 1 `output_columns`
      * +1.0 for semantic chart fit (`TimeSeriesChart` on temporal series, `BudgetVarianceChart`
        on budget/actual columns, `KPIGrid` on single-row summaries, `CategoryBarChart` on
        categorical breakdowns)
      * -1.0 for hallucinated column names or invalid component props
      * -0.5 for charting a 1-row scalar result as `TimeSeriesChart` or `CategoryBarChart`
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from training.gbnf_compiler import validate_hop1_call, validate_hop2_call  # noqa: E402
from training.seed_warehouses import seed_all_warehouses  # noqa: E402

_REWARD_CONN: duckdb.DuckDBPyConnection | None = None


def get_reward_conn() -> duckdb.DuckDBPyConnection:
    """Lazy-initialize a seeded in-memory DuckDB connection for fast GRPO reward evaluation."""
    global _REWARD_CONN
    if _REWARD_CONN is None:
        _REWARD_CONN = duckdb.connect(":memory:")
        seed_all_warehouses(_REWARD_CONN)
    return _REWARD_CONN


def _clean_completion(text: str) -> str:
    """Strip trailing `<|im_end|>` or whitespace from a model completion."""
    cleaned = text.strip()
    if cleaned.endswith("<|im_end|>"):
        cleaned = cleaned[: -len("<|im_end|>")].strip()
    return cleaned


def score_hop1_completion(
    completion: str,
    gold_sql: str | None = None,
    conn: duckdb.DuckDBPyConnection | None = None,
) -> float:
    """Compute verifiable reward for a Hop 1 `execute_duckdb_query` completion."""
    cleaned = _clean_completion(completion)
    is_valid, err = validate_hop1_call(cleaned)
    if not is_valid:
        return -1.0

    reward = 0.5
    payload = json.loads(cleaned)
    pred_sql = payload["arguments"]["sql"].strip().rstrip(";")

    db = conn or get_reward_conn()
    try:
        pred_rows = db.execute(f"SELECT * FROM (\n{pred_sql}\n) AS _pred LIMIT 500").fetchall()
    except Exception:
        return -1.0

    if len(pred_rows) > 0:
        reward += 1.0
    else:
        reward += 0.1

    if gold_sql:
        try:
            gold_clean = gold_sql.strip().rstrip(";")
            gold_rows = db.execute(
                f"SELECT * FROM (\n{gold_clean}\n) AS _gold LIMIT 500"
            ).fetchall()
            # Multiset, not set: duplicate rows and row counts are part of the
            # result. Collapsing to a set let a lost GROUP BY or a fan-out join
            # collect the full execution-match reward.
            if Counter(tuple(r) for r in pred_rows) == Counter(tuple(r) for r in gold_rows):
                reward += 1.5
        except Exception:
            pass

    return round(reward, 4)


def score_hop2_completion(
    completion: str,
    output_columns: list[str],
    row_count: int = 5,
    column_types: dict[str, str] | None = None,
) -> float:
    """Compute verifiable reward for a Hop 2 `render_workspace_ui` completion."""
    cleaned = _clean_completion(completion)
    is_valid, _ = validate_hop2_call(cleaned, valid_columns=output_columns)
    if not is_valid:
        return -1.0

    reward = 1.0
    payload = json.loads(cleaned)
    components = payload["arguments"].get("components", payload["arguments"].get("panels", []))
    comp_types = [p["component"] for p in components]

    col_set = {c.lower() for c in output_columns}
    col_types_upper = {k.lower(): v.upper() for k, v in (column_types or {}).items()}

    # Semantic chart appropriateness checks
    if row_count == 1:
        if any(
            c in ("TimeSeriesChart", "CategoryBarChart", "BudgetVarianceChart") for c in comp_types
        ):
            reward -= 0.5
        elif "KPIGrid" in comp_types:
            reward += 1.0
        return round(reward, 4)

    has_budget_cols = ("actual_amount" in col_set and "budget_amount" in col_set) or any(
        "variance" in c for c in col_set
    )
    has_temporal = any(
        "DATE" in col_types_upper.get(c, "")
        or "TIME" in col_types_upper.get(c, "")
        or c in ("spend_month", "transaction_date", "academic_year", "school_year", "incident_date")
        for c in col_set
    )

    if has_budget_cols and "BudgetVarianceChart" in comp_types:
        reward += 1.0
    elif has_temporal and "TimeSeriesChart" in comp_types:
        reward += 1.0
    elif row_count > 1 and ("CategoryBarChart" in comp_types or "DataTable" in comp_types):
        reward += 1.0

    return round(reward, 4)


def two_hop_grpo_reward_func(
    prompts: list[str],
    completions: list[str],
    gold_sql: list[str | None] | None = None,
    output_columns: list[list[str] | None] | None = None,
    **kwargs: Any,
) -> list[float]:
    """TRL `GRPOTrainer`-compatible batch reward function."""
    db = get_reward_conn()
    rewards: list[float] = []

    for idx, (prompt, comp) in enumerate(zip(prompts, completions, strict=False)):
        comp_str = comp if isinstance(comp, str) else str(comp)
        g_sql = gold_sql[idx] if (gold_sql and idx < len(gold_sql)) else None
        out_cols = output_columns[idx] if (output_columns and idx < len(output_columns)) else None

        # Detect whether this prompt is asking for Hop 2 (`duckdb_result_summary` in last tool turn)
        if '"status":"ok"' in prompt and '"sample_rows":' in prompt and out_cols:
            r = score_hop2_completion(comp_str, output_columns=out_cols)
        else:
            r = score_hop1_completion(comp_str, gold_sql=g_sql, conn=db)
        rewards.append(r)

    return rewards
