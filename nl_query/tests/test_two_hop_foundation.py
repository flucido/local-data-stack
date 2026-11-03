"""
test_two_hop_foundation.py — Unit and integration tests for the K-12 Education Two-Hop Engine:
  - Canonical Two-Hop Tool Schemas & GBNF Compiler (`training/gbnf_compiler.py`)
  - Deterministic Top-K Schema Pruner for K-12 Education (`training/schema_pruner.py`)
  - Seeded K-12 Education Warehouse (`training/seed_warehouses.py`)
  - Two-Hop DuckDB Result Metadata Summary, Self-Healing Error Formatter, and
    Zero-LLM Parameterized FilterBar CTE Execution (`nl_query/data_engine.py`)
  - Execution-Guided Verifiable Reward Function (`training/reward_fn.py`)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
NL_QUERY_DIR = REPO_ROOT / "nl_query"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(NL_QUERY_DIR) not in sys.path:
    sys.path.insert(0, str(NL_QUERY_DIR))

from data_engine import (  # noqa: E402
    apply_query_filters,
    compute_result_summary,
    extract_sql,
    format_duckdb_error,
    validate_sql,
)

from training.gbnf_compiler import (  # noqa: E402
    compile_hop1_gbnf,
    compile_hop2_gbnf,
    validate_hop1_call,
    validate_hop2_call,
)
from training.schema_pruner import (  # noqa: E402
    format_pruned_ddl,
    load_unified_schema,
    select_top_k_tables,
    select_training_tables_with_distractors,
)
from training.seed_warehouses import seed_all_warehouses  # noqa: E402


@pytest.fixture()
def seeded_conn():
    conn = duckdb.connect(":memory:")
    seed_all_warehouses(conn)
    yield conn
    conn.close()


# ── 1. GBNF Compiler & Semantic Validation Tests ───────────────────────


def test_compile_hop1_gbnf_structure():
    gbnf = compile_hop1_gbnf()
    assert "execute_duckdb_query" in gbnf
    assert "sql-prefix ::=" in gbnf
    assert '"SELECT"' in gbnf
    assert '"WITH"' in gbnf


def test_compile_hop2_gbnf_injects_exact_columns():
    cols = ["academic_year", "reporting_category_label", "avg_chronic_absent_rate"]
    gbnf = compile_hop2_gbnf(cols)
    assert "render_workspace_ui" in gbnf
    assert (
        'column-name ::= "\\"academic_year\\"" | "\\"reporting_category_label\\"" | "\\"avg_chronic_absent_rate\\""'
        in gbnf
    )
    for comp in (
        "KPIGrid",
        "TimeSeriesChart",
        "CategoryBarChart",
        "BudgetVarianceChart",
        "DataTable",
        "FilterBar",
    ):
        assert comp in gbnf


def test_validate_hop1_call_valid_and_invalid():
    valid_call = {
        "tool": "execute_duckdb_query",
        "arguments": {
            "explanation": "Aggregate chronic absenteeism rate by academic year.",
            "sql": "SELECT academic_year, ROUND(AVG(ca_chronic_absent_rate_pct), 2) AS avg_chronic_absent_rate FROM main_analytics.mart_cde_school_accountability GROUP BY 1",
        },
    }
    ok, errors = validate_hop1_call(valid_call)
    assert ok is True
    assert errors == []

    bad_call = {
        "tool": "execute_duckdb_query",
        "arguments": {
            "explanation": "Mutate table",
            "sql": "DROP TABLE main_core.dim_students",
        },
    }
    ok_bad, errors_bad = validate_hop1_call(bad_call)
    assert ok_bad is False
    assert any("SELECT or WITH" in e for e in errors_bad)


def test_validate_hop2_call_enforces_column_binding_and_semantics(seeded_conn):
    hop1_json = json.dumps(
        {
            "tool": "execute_duckdb_query",
            "arguments": {
                "explanation": "Chronic absenteeism trend by subgroup across academic years.",
                "sql": (
                    "SELECT academic_year, reporting_category_label, "
                    "ROUND(AVG(ca_chronic_absent_rate_pct), 2) AS avg_chronic_absent_rate "
                    "FROM main_analytics.mart_cde_school_accountability "
                    "WHERE reporting_category IN ('TA', 'EL', 'SE') AND aggregate_level = 'S' "
                    "GROUP BY 1, 2 ORDER BY 1 ASC, 3 DESC"
                ),
            },
        }
    )
    _, _, summary = compute_result_summary(seeded_conn, hop1_json, query_id="q_test_01")

    valid_hop2 = {
        "tool": "render_workspace_ui",
        "arguments": {
            "title": "Multi-Year Chronic Absenteeism Trend by Subgroup",
            "narrative_summary": "Chronic absenteeism declined across subgroups from 2020-21 to 2024-25.",
            "components": [
                {
                    "component": "FilterBar",
                    "controls": [
                        {
                            "column": "academic_year",
                            "control_type": "date_range",
                            "label": "Academic Year",
                        },
                        {
                            "column": "reporting_category_label",
                            "control_type": "multi_select",
                            "label": "Subgroup",
                        },
                    ],
                },
                {
                    "component": "TimeSeriesChart",
                    "chart_variant": "stacked_bar",
                    "x_column": "academic_year",
                    "y_columns": ["avg_chronic_absent_rate"],
                    "series_column": "reporting_category_label",
                    "value_format": "percent",
                },
                {
                    "component": "DataTable",
                    "columns": [
                        "academic_year",
                        "reporting_category_label",
                        "avg_chronic_absent_rate",
                    ],
                    "default_sort": {"column": "academic_year", "direction": "desc"},
                },
            ],
        },
    }
    ok, errors = validate_hop2_call(valid_hop2, result_summary=summary)
    assert ok is True, f"Unexpected errors: {errors}"

    # Hallucinated column name should be rejected
    hallucinated_hop2 = json.loads(json.dumps(valid_hop2))
    hallucinated_hop2["arguments"]["components"][1]["y_columns"] = ["non_existent_col"]
    ok_h, err_h = validate_hop2_call(hallucinated_hop2, result_summary=summary)
    assert ok_h is False
    assert any("non_existent_col" in e for e in err_h)

    # KPIGrid on a multi-row result should be flagged by semantic validator
    kpi_on_multirow = {
        "tool": "render_workspace_ui",
        "arguments": {
            "title": "Invalid KPI on Multi-row",
            "narrative_summary": "Summary",
            "components": [
                {
                    "component": "KPIGrid",
                    "metrics": [
                        {
                            "label": "Avg Absent Rate",
                            "value_column": "avg_chronic_absent_rate",
                            "value_format": "percent",
                        }
                    ],
                }
            ],
        },
    }
    ok_kpi, err_kpi = validate_hop2_call(kpi_on_multirow, result_summary=summary)
    assert ok_kpi is False
    assert any("row_count == 1" in e for e in err_kpi)


# ── 2. Top-K Schema Pruner Tests (100% K-12 Education) ─────────────────


def test_top_k_schema_pruner_k12_domains():
    schema = load_unified_schema()
    assert len(schema) == 20

    # Attendance + English Learner join query
    q_edu = "What is the average attendance rate for English Learners in 2023-2024?"
    pruned_edu = select_top_k_tables(q_edu, schema, k=5)
    assert len(pruned_edu) == 5
    assert "main_core.fact_attendance" in pruned_edu
    assert "main_core.dim_students" in pruned_edu

    # Restraint & seclusion CDE staging query
    q_rs = "Which schools reported physical restraints in 2023-24?"
    pruned_rs = select_top_k_tables(q_rs, schema, k=5)
    assert len(pruned_rs) == 5
    assert "main_staging.stg_cde__restraint_seclusion" in pruned_rs

    # Equity by race gap query
    q_eq = "Show the suspension rate gap between Black and White students"
    pruned_eq = select_top_k_tables(q_eq, schema, k=5)
    assert "main_analytics.equity_by_race" in pruned_eq

    ddl_text = format_pruned_ddl(pruned_eq)
    # Full column lists are required (must match the training-time prompt format exactly).
    # 5 wide K-12 tables ≈ 4-5k chars; the real guarantee is top-k pruning, not column truncation.
    assert len(ddl_text) < 7000


def test_training_tables_with_distractors_preserves_gold_tables():
    schema = load_unified_schema()
    q = "What is the average attendance rate for English Learners in 2023-2024?"
    gold_sql = (
        "SELECT ROUND(AVG(a.attendance_rate), 4) AS avg_attendance_rate "
        "FROM main_core.fact_attendance a "
        "JOIN main_core.dim_students s ON a.student_id_hash = s.student_id_hash "
        "WHERE s.ell_status = TRUE"
    )
    pruned = select_training_tables_with_distractors(q, gold_sql, schema, k=5, seed=42)
    assert len(pruned) == 5
    assert "main_core.fact_attendance" in pruned
    assert "main_core.dim_students" in pruned


# ── 3. DuckDB Result Summary, Self-Healing Error & FilterBar CTE Tests ─


def test_extract_sql_supports_hop1_tool_call():
    raw = json.dumps(
        {
            "tool": "execute_duckdb_query",
            "arguments": {
                "explanation": "Count enrolled students in 2023-2024.",
                "sql": "SELECT COUNT(DISTINCT student_id_hash) AS student_count FROM main_core.dim_students WHERE academic_year = '2023-2024';",
            },
        }
    )
    sql = extract_sql(raw)
    assert (
        sql
        == "SELECT COUNT(DISTINCT student_id_hash) AS student_count FROM main_core.dim_students WHERE academic_year = '2023-2024'"
    )


def test_format_duckdb_error_preserves_candidate_bindings(seeded_conn):
    bad_sql = "SELECT student_id, attendance_rate FROM main_core.fact_attendance"
    with pytest.raises(ValueError) as exc_info:
        validate_sql(bad_sql, conn=seeded_conn)

    err_payload = format_duckdb_error(exc_info.value)
    assert err_payload["status"] == "error"
    assert err_payload["error_type"] == "BinderError"
    assert "student_id" in err_payload["message"]
    assert "Candidate bindings" in err_payload["message"]


def test_apply_query_filters_zero_llm_parameterized_cte(seeded_conn):
    base_sql = (
        "SELECT academic_year, primary_race, COUNT(*) AS student_count "
        "FROM main_core.dim_students "
        "GROUP BY 1, 2 ORDER BY 1 ASC, 2 ASC"
    )
    filters = [
        {
            "column": "academic_year",
            "control_type": "date_range",
            "min": "2022-2023",
            "max": "2023-2024",
        },
        {
            "column": "primary_race",
            "control_type": "multi_select",
            "values": ["Asian", "Hispanic/Latino"],
        },
    ]
    df = apply_query_filters(seeded_conn, base_sql, filters)
    assert len(df) == 4  # 2 years * 2 races
    assert set(df["primary_race"].unique()) == {"Asian", "Hispanic/Latino"}

    # Reject unknown/injected column names
    with pytest.raises(ValueError, match="Invalid filter column"):
        apply_query_filters(
            seeded_conn,
            base_sql,
            [
                {
                    "column": "student_count; DROP TABLE dim_students --",
                    "control_type": "numeric_range",
                    "min": 0,
                }
            ],
        )


def test_python_two_hop_turn_with_self_healing_retry(seeded_conn):
    from model_inference import generate_two_hop_turn

    calls = []

    def mock_llm(prompt: str, **_kwargs):
        calls.append(prompt)
        if len(calls) == 1:
            # First attempt intentionally uses wrong column `student_id`
            return {
                "choices": [
                    {
                        "text": json.dumps(
                            {
                                "tool": "execute_duckdb_query",
                                "arguments": {
                                    "explanation": "Initial attempt with wrong column.",
                                    "sql": "SELECT school_id, COUNT(DISTINCT student_id) AS student_count FROM main_core.fact_attendance WHERE academic_year = '2023-2024' GROUP BY 1",
                                },
                            }
                        )
                    }
                ]
            }
        # Second attempt inspects Candidate bindings injected into the prompt and fixes the column to `student_id_hash`
        assert "Candidate bindings" in prompt
        assert "student_id_hash" in prompt
        return {
            "choices": [
                {
                    "text": json.dumps(
                        {
                            "tool": "execute_duckdb_query",
                            "arguments": {
                                "explanation": "Corrected query using student_id_hash.",
                                "sql": "SELECT school_id, COUNT(DISTINCT student_id_hash) AS student_count, ROUND(AVG(attendance_rate), 4) AS avg_attendance_rate FROM main_core.fact_attendance WHERE academic_year = '2023-2024' GROUP BY 1 ORDER BY 1 ASC",
                            },
                        }
                    )
                }
            ]
        }

    turn = generate_two_hop_turn(
        "Show student count and average attendance rate by school in 2023-2024.",
        conn=seeded_conn,
        llm=mock_llm,
        k_tables=5,
        max_retries=2,
    )
    assert turn["retries_used"] == 1
    assert len(turn["self_healing_errors"]) == 1
    assert turn["self_healing_errors"][0]["error_type"] == "BinderError"
    assert turn["result_summary"]["row_count"] == 6
    assert turn["hop2_valid"] is True
    assert turn["hop2_call"]["tool"] == "render_workspace_ui"


def test_reward_fn_scores_hop1_and_hop2_accurately():
    from training.reward_fn import score_hop1_completion, score_hop2_completion

    gold_sql = "SELECT school_id, student_count, avg_gpa, pct_high_risk FROM main_analytics.school_summary ORDER BY pct_high_risk DESC"
    good_hop1 = json.dumps(
        {
            "tool": "execute_duckdb_query",
            "arguments": {
                "explanation": "Compare high-risk student percentage and GPA across schools.",
                "sql": gold_sql,
            },
        }
    )
    bad_hop1 = json.dumps(
        {
            "tool": "execute_duckdb_query",
            "arguments": {
                "explanation": "Wrong column.",
                "sql": "SELECT bogus_col FROM main_analytics.school_summary",
            },
        }
    )
    assert score_hop1_completion(good_hop1, gold_sql=gold_sql) == 3.0
    assert score_hop1_completion(bad_hop1, gold_sql=gold_sql) == -1.0

    output_cols = ["school_id", "student_count", "avg_gpa", "pct_high_risk"]
    good_hop2 = json.dumps(
        {
            "tool": "render_workspace_ui",
            "arguments": {
                "title": "School Risk & GPA Summary",
                "narrative_summary": "Comparison of high-risk percentage and GPA by school.",
                "components": [
                    {
                        "component": "CategoryBarChart",
                        "chart_variant": "horizontal",
                        "category_column": "school_id",
                        "value_columns": ["pct_high_risk", "avg_gpa"],
                        "value_format": "percent",
                    }
                ],
            },
        }
    )
    hallucinated_hop2 = json.dumps(
        {
            "tool": "render_workspace_ui",
            "arguments": {
                "title": "School Risk & GPA Summary",
                "narrative_summary": "Comparison of high-risk percentage and GPA by school.",
                "components": [
                    {
                        "component": "CategoryBarChart",
                        "chart_variant": "horizontal",
                        "category_column": "school_id",
                        "value_columns": ["hallucinated_col"],
                        "value_format": "percent",
                    }
                ],
            },
        }
    )
    assert score_hop2_completion(good_hop2, output_columns=output_cols, row_count=6) == 2.0
    assert score_hop2_completion(hallucinated_hop2, output_columns=output_cols, row_count=6) == -1.0
