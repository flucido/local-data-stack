"""
modal_generate.py — Multi-Turn Two-Hop K-12 Education Trajectory Synthesis & Validation Pipeline.

Synthesizes and validates 3,000 execution-verified multi-turn Two-Hop trajectories
for `LiquidAI/LFM3-1.7B` across our 20-table K-12 Education Analytics Warehouse
(`main_core`, `main_analytics`, `main_staging` — Aeries SIS + California Dept. of Education):

  - Split A (70% / 2,100 trajectories): Golden 2-Hop
      System (with Top-K Pruned K-12 DDL + 3-4 BM25 hard-negative distractors)
      -> User
      -> Assistant Hop 1 (`execute_duckdb_query`)
      -> Tool (`duckdb_result_summary` from populated K-12 DuckDB warehouse)
      -> Assistant Hop 2 (`render_workspace_ui` validated against exact output columns)

  - Split B (15% / 450 trajectories): Self-Healing SQL Recovery
      System (Top-K Pruned K-12 DDL)
      -> User
      -> Assistant Turn 1 (perturbed SQL with realistic K-12 column/table mistake)
      -> Tool (`duckdb_execution_error` with real DuckDB `BinderError` + `Candidate bindings`)
      -> Assistant Turn 1b (corrected `execute_duckdb_query`)
      -> Tool (`duckdb_result_summary`)
      -> Assistant Turn 2 (`render_workspace_ui`)

  - Split C (15% / 450 trajectories): Conversational Multi-Turn Refinement
      Full Golden 2-Hop Turn 1
      -> User Turn 2 (follow-up filter, subgroup breakdown, year comparison, or top-N refinement)
      -> Assistant Turn 2 Hop 1 (`execute_duckdb_query` with refined SQL)
      -> Tool (`duckdb_result_summary`)
      -> Assistant Turn 2 Hop 2 (`render_workspace_ui`)
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path
from typing import Any

import duckdb
import modal

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "nl_query") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "nl_query"))

from training.gbnf_compiler import validate_hop1_call, validate_hop2_call  # noqa: E402
from training.schema_pruner import (  # noqa: E402
    format_pruned_ddl,
    load_unified_schema,
    select_training_tables_with_distractors,
)
from training.seed_warehouses import (  # noqa: E402
    RACES,
    REPORTING_CATEGORIES,
    SCHOOLS,
    seed_all_warehouses,
)

HF_DATASET_REPO = "KDDSTLC/lfed-lfm3-two-hop-trajectories"
MODAL_VOLUME_NAME = "lfed-training-data"
REMOTE_JSONL_NAME = "lfm3_two_hop_3k.jsonl"

app = modal.App("lfed-two-hop-datagen")
volume = modal.Volume.from_name(MODAL_VOLUME_NAME, create_if_missing=True)

datagen_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "duckdb>=1.1.0",
        "pandas>=2.2.0",
        "numpy>=1.26.0",
        "huggingface_hub>=0.28.0",
        "datasets>=3.2.0",
    )
    .add_local_dir(
        str(PROJECT_ROOT / "training"),
        remote_path="/root/project/training",
        ignore=["*.jsonl", "__pycache__", "*.pyc"],
    )
    .add_local_dir(
        str(PROJECT_ROOT / "nl_query"),
        remote_path="/root/project/nl_query",
        ignore=["*.jsonl", "__pycache__", "*.pyc", ".coverage"],
    )
)


# ── Diverse K-12 Education Multi-Table Query Generator ─────────────────


def generate_extra_k12_pairs() -> list[dict[str, str]]:
    """Generate ~600 diverse, realistic K-12 Education NL->SQL pairs across under-represented
    analytics marts (`v_chronic_absenteeism_risk`, `v_equity_outcomes_by_demographics`,
    `equity_by_race`, `school_summary`) and CDE staging tables (`stg_cde__*`).
    """
    pairs: list[dict[str, str]] = []

    aeries_years = ["2021-2022", "2022-2023", "2023-2024", "2024-2025"]
    cde_years = ["2020-21", "2021-22", "2022-23", "2023-24", "2024-25"]

    # 1. v_chronic_absenteeism_risk & v_equity_outcomes_by_demographics
    for yr in aeries_years:
        pairs.extend(
            [
                {
                    "question": f"Show student counts and average chronic absenteeism risk scores by risk level in {yr}.",
                    "sql": f"SELECT risk_level, COUNT(*) AS student_count, ROUND(AVG(chronic_absenteeism_risk_score), 2) AS avg_risk_score FROM main_analytics.v_chronic_absenteeism_risk WHERE academic_year = '{yr}' GROUP BY risk_level ORDER BY avg_risk_score DESC",
                    "domain": "k12",
                },
                {
                    "question": f"How does the 30-day attendance rate compare across 90-day attendance trends in {yr}?",
                    "sql": f"SELECT attendance_trend_90d, COUNT(*) AS student_count, ROUND(AVG(attendance_rate_30d), 4) AS avg_30d_attendance, ROUND(AVG(chronic_absenteeism_risk_score), 2) AS avg_risk_score FROM main_analytics.v_chronic_absenteeism_risk WHERE academic_year = '{yr}' GROUP BY attendance_trend_90d ORDER BY avg_risk_score DESC",
                    "domain": "k12",
                },
                {
                    "question": f"Break down chronic absenteeism risk score and 30-day unexcused absence rate by school in {yr}.",
                    "sql": f"SELECT school_id, COUNT(*) AS student_count, ROUND(AVG(chronic_absenteeism_risk_score), 2) AS avg_risk_score, ROUND(AVG(unexcused_absence_rate_30d), 4) AS avg_unexcused_rate FROM main_analytics.v_chronic_absenteeism_risk WHERE academic_year = '{yr}' GROUP BY school_id ORDER BY avg_risk_score DESC",
                    "domain": "k12",
                },
                {
                    "question": f"For economically disadvantaged students in {yr}, what is the average chronic absenteeism risk score by race/ethnicity?",
                    "sql": f"SELECT race_ethnicity, COUNT(*) AS student_count, ROUND(AVG(chronic_absenteeism_risk_score), 2) AS avg_risk_score FROM main_analytics.v_chronic_absenteeism_risk WHERE academic_year = '{yr}' AND economically_disadvantaged = TRUE GROUP BY race_ethnicity ORDER BY avg_risk_score DESC",
                    "domain": "k12",
                },
            ]
        )

    for race, _, _ in RACES:
        pairs.extend(
            [
                {
                    "question": f"Show equity outcomes (good attendance percentage, no-discipline percentage, and average GPA) for {race} students by English Learner status.",
                    "sql": f"SELECT race_ethnicity, english_learner, cohort_size, pct_good_attendance, pct_no_discipline, avg_gpa FROM main_analytics.v_equity_outcomes_by_demographics WHERE race_ethnicity = '{race}' ORDER BY english_learner DESC",
                    "domain": "k12",
                },
                {
                    "question": f"What are the student count, special education count, FRL count, and average GPA for {race} students in equity_by_race?",
                    "sql": f"SELECT primary_race, student_count, special_ed_count, frl_count, ell_count, avg_attendance_rate, avg_gpa, pct_suspended FROM main_analytics.equity_by_race WHERE primary_race = '{race}'",
                    "domain": "k12",
                },
            ]
        )

    # 2. school_summary + dim_schools joins
    for sid, sname, _, _dname, _, _county, _, _ in SCHOOLS:
        pairs.extend(
            [
                {
                    "question": f"Show key summary metrics (student count, FRL %, ELL %, average GPA, and high-risk %) for {sname} ({sid}).",
                    "sql": f"SELECT d.school_name, d.cde_district_name, s.student_count, s.pct_frl, s.pct_ell, s.avg_attendance_rate, s.avg_gpa, s.pct_high_risk FROM main_analytics.school_summary s JOIN main_core.dim_schools d ON s.school_id = d.school_id WHERE s.school_id = '{sid}'",
                    "domain": "k12",
                },
                {
                    "question": f"Compare average GPA and attendance rate by grade level at {sname} ({sid}) in 2023-2024.",
                    "sql": f"SELECT st.grade_level, COUNT(DISTINCT st.student_id_hash) AS student_count, ROUND(AVG(a.attendance_rate), 4) AS avg_attendance_rate, ROUND(AVG(ar.gpa_points), 2) AS avg_gpa FROM main_core.dim_students st JOIN main_core.fact_attendance a ON st.student_id_hash = a.student_id_hash AND st.academic_year = a.academic_year JOIN main_core.fact_academic_records ar ON st.student_id_hash = ar.student_id_hash AND st.academic_year = ar.school_year WHERE st.school_id = '{sid}' AND st.academic_year = '2023-2024' GROUP BY st.grade_level ORDER BY st.grade_level ASC",
                    "domain": "k12",
                },
            ]
        )

    # 3. CDE Accountability Mart & Staging across subgroups and years
    for cde_yr in cde_years:
        for rc_code, rc_label, _, _, _ in REPORTING_CATEGORIES[:8]:
            pairs.extend(
                [
                    {
                        "question": f"Compare chronic absenteeism rate, suspension rate, and SBAC proficiency for {rc_label} ({rc_code}) across schools in {cde_yr}.",
                        "sql": f"SELECT school_name, district_name, ca_chronic_absent_rate_pct, su_suspension_rate_pct, sbac_pct_standard_met_above FROM main_analytics.mart_cde_school_accountability WHERE academic_year = '{cde_yr}' AND reporting_category = '{rc_code}' AND aggregate_level = 'S' ORDER BY ca_chronic_absent_rate_pct DESC",
                        "domain": "k12",
                    },
                    {
                        "question": f"Show CAASPP mean scale score and percentage meeting or exceeding standard for {rc_label} ({rc_code}) in {cde_yr}.",
                        "sql": f"SELECT cds_code, reporting_category_label, students_tested, mean_scale_score, pct_standard_met_and_above, pct_standard_not_met FROM main_staging.stg_cde__assessment_caspp WHERE academic_year = '{cde_yr}' AND reporting_category = '{rc_code}' ORDER BY mean_scale_score DESC",
                        "domain": "k12",
                    },
                ]
            )

        pairs.extend(
            [
                {
                    "question": f"Show total expulsions and expulsion rate by school in {cde_yr}.",
                    "sql": f"SELECT school_name, district_name, cumulative_enrollment, total_expulsions, expulsion_rate_total FROM main_staging.stg_cde__expulsion WHERE academic_year = '{cde_yr}' AND aggregate_level = 'S' AND reporting_category = 'TA' ORDER BY total_expulsions DESC",
                    "domain": "k12",
                },
                {
                    "question": f"Show physical and mechanical restraint counts by school and county in {cde_yr}.",
                    "sql": f"SELECT school_name, county_name, count_of_physical_restraints, count_of_mechanical_restraints, count_of_seclusions FROM main_staging.stg_cde__restraint_seclusion WHERE academic_year = '{cde_yr}' AND aggregate_level = 'S' AND reporting_category = 'TA' ORDER BY count_of_physical_restraints DESC",
                    "domain": "k12",
                },
                {
                    "question": f"Compare free meal count and FRPM eligibility percentage across schools in {cde_yr}.",
                    "sql": f"SELECT school_name, district_name, enrollment_k12, free_meal_count_k12, percent_eligible_free_k12, percent_eligible_frpm_k12 FROM main_staging.stg_cde__frpm WHERE academic_year = '{cde_yr}' AND reporting_category = 'TA' ORDER BY percent_eligible_frpm_k12 DESC",
                    "domain": "k12",
                },
            ]
        )

    return pairs


# ── Perturbation Engine for Split B (Self-Healing K-12 SQL Recovery) ────

PERTURBATION_RULES: list[tuple[str, str]] = [
    (r"\bstudent_id_hash\b", "student_id"),
    (r"\bca_chronic_absent_rate_pct\b", "chronic_absenteeism_rate"),
    (r"\bsu_suspension_rate_pct\b", "suspension_rate"),
    (r"\battendance_rate\b", "avg_attendance_pct"),
    (r"\bgpa_points\b", "student_gpa"),
    (r"\bschool_year\b", "academic_year"),
    (r"\bprimary_race\b", "student_race"),
    (r"\breporting_category\b", "subgroup_code"),
    (r"\bfrpm_free_pct_k12\b", "free_lunch_pct"),
    (r"\bsuspension_days\b", "days_suspended_count"),
    (r"\bchronic_absent_rate_pct\b", "chronic_absence_pct"),
    (r"\bsbac_pct_standard_met_above\b", "sbac_proficiency_pct"),
    (r"\bhomeless_student_enrollment\b", "homeless_count"),
]


def create_perturbed_sql(gold_sql: str) -> str | None:
    """Introduce a realistic K-12 column identifier mistake that triggers a DuckDB `BinderError` with `Candidate bindings`."""
    for pattern, wrong_col in PERTURBATION_RULES:
        if re.search(pattern, gold_sql):
            return re.sub(pattern, wrong_col, gold_sql, count=1)
    return None


# ── Follow-Up Engine for Split C (2-Turn K-12 Conversational Refinement) ──


def create_followup_turn(question: str, gold_sql: str) -> tuple[str, str] | None:
    """Create a realistic 2nd user turn (`followup_question`, `followup_sql`) that refines `gold_sql`."""
    sql_clean = gold_sql.strip().rstrip(";")

    # Case 1: Query without LIMIT -> add LIMIT 5
    if "ORDER BY" in sql_clean.upper() and "LIMIT" not in sql_clean.upper():
        return (
            "Limit those results to the top 5 entries only.",
            f"{sql_clean}\nLIMIT 5",
        )

    # Case 2: Query with LIMIT 10 or LIMIT 20 -> refine to top 3
    if re.search(r"\bLIMIT\s+(?:10|20)\b", sql_clean, flags=re.IGNORECASE):
        refined = re.sub(r"\bLIMIT\s+(?:10|20)\b", "LIMIT 3", sql_clean, flags=re.IGNORECASE)
        return (
            "Actually, just show me the top 3 results.",
            refined,
        )

    # Case 3: Query filtering on 2023-2024 -> switch comparison to 2022-2023
    if "'2023-2024'" in sql_clean:
        return (
            "How did that look in the prior 2022-2023 academic year?",
            sql_clean.replace("'2023-2024'", "'2022-2023'"),
        )

    # Case 4: Query filtering on 2023-24 -> switch to 2024-25
    if "'2023-24'" in sql_clean:
        return (
            "Now run the exact same breakdown for the 2024-25 academic year.",
            sql_clean.replace("'2023-24'", "'2024-25'"),
        )

    return None


# ── Trajectory Assembler ────────────────────────────────────────────────


def build_verified_trajectories(
    target_total: int = 3000,
    k12_pairs_path: str | Path = "/tmp/pairs_warehouse.jsonl",
    seed: int = 42,
) -> list[dict[str, Any]]:
    """Build and validate `target_total` multi-turn 2-hop K-12 Education trajectories:
    - 70% Split A (Golden 2-Hop)
    - 15% Split B (Self-Healing SQL Recovery with real DuckDB BinderError)
    - 15% Split C (2-Turn Conversational Follow-Up Refinement)
    """
    from data_engine import compute_result_summary, format_duckdb_error
    from model_inference import synthesize_semantic_hop2_ui
    from prompts import TWO_HOP_SYSTEM_PROMPT, append_tool_turn, build_two_hop_prompt

    rng = random.Random(seed)
    conn = duckdb.connect(":memory:")
    seed_all_warehouses(conn)
    schema = load_unified_schema()

    # Exclude holdout questions so there is zero train/test contamination
    holdout_questions: set[str] = set()
    for hp in [
        PROJECT_ROOT / "nl_query" / "eval_test_set.jsonl",
        PROJECT_ROOT / "nl_query" / "eval_two_hop_holdout.jsonl",
    ]:
        if hp.exists():
            for line in hp.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    holdout_questions.add(json.loads(line)["question"].strip().lower())

    # Load candidate pairs (100% K-12 Education: pairs_warehouse.jsonl + generate_extra_k12_pairs)
    candidates: list[dict[str, str]] = []
    seen_questions: set[str] = set()

    k12_file = Path(k12_pairs_path)
    if k12_file.exists():
        for line in k12_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
                q = obj["question"].strip()
                s = obj["sql"].strip().rstrip(";")
                if q.lower() in holdout_questions or q.lower() in seen_questions:
                    continue
                seen_questions.add(q.lower())
                candidates.append({"question": q, "sql": s, "domain": "k12"})
            except Exception:
                continue

    for extra_item in generate_extra_k12_pairs():
        q = extra_item["question"].strip()
        s = extra_item["sql"].strip().rstrip(";")
        if q.lower() in holdout_questions or q.lower() in seen_questions:
            continue
        seen_questions.add(q.lower())
        candidates.append(extra_item)

    rng.shuffle(candidates)

    target_a = int(target_total * 0.70)  # 2,100
    target_b = int(target_total * 0.15)  # 450
    target_c = target_total - target_a - target_b  # 450

    split_a: list[dict[str, Any]] = []
    split_b: list[dict[str, Any]] = []
    split_c: list[dict[str, Any]] = []

    for idx, item in enumerate(candidates):
        if len(split_a) >= target_a and len(split_b) >= target_b and len(split_c) >= target_c:
            break

        question = item["question"]
        gold_sql = item["sql"]

        # Execute gold SQL and compute result summary (must return > 0 rows and non-null first value)
        try:
            cleaned_sql, df, summary = compute_result_summary(
                conn, gold_sql, query_id=f"q_train_{idx:05d}"
            )
            if summary["row_count"] <= 0 or not summary["columns"]:
                continue
            if summary["sample_rows"] and all(v is None for v in summary["sample_rows"][0]):
                continue
        except Exception:
            continue

        output_cols = [c["name"] for c in summary["columns"]]
        pruned_tables = select_training_tables_with_distractors(
            question, cleaned_sql, schema, k=5, seed=idx
        )
        pruned_ddl = format_pruned_ddl(pruned_tables)
        system_content = f"{TWO_HOP_SYSTEM_PROMPT}\n\n{pruned_ddl}"

        hop1_obj = {
            "tool": "execute_duckdb_query",
            "arguments": {
                "explanation": f"Query the K-12 education warehouse to answer: {question}",
                "sql": cleaned_sql,
            },
        }
        hop1_json = json.dumps(hop1_obj, separators=(",", ":"))
        valid_h1, _ = validate_hop1_call(hop1_json)
        if not valid_h1:
            continue

        hop2_obj = synthesize_semantic_hop2_ui(question, summary)
        hop2_json = json.dumps(hop2_obj, separators=(",", ":"))
        valid_h2, _ = validate_hop2_call(hop2_json, valid_columns=output_cols)
        if not valid_h2:
            continue

        summary_json = json.dumps(summary, separators=(",", ":"))

        # Try Split B (Self-Healing) if needed
        if len(split_b) < target_b:
            bad_sql = create_perturbed_sql(cleaned_sql)
            if bad_sql and bad_sql != cleaned_sql:
                try:
                    conn.execute(bad_sql).fetchall()
                except Exception as exc:
                    err_payload = format_duckdb_error(exc)
                    if err_payload.get("error_type") in ("BinderError", "CatalogError"):
                        bad_hop1_obj = {
                            "tool": "execute_duckdb_query",
                            "arguments": {
                                "explanation": f"Initial query attempt for: {question}",
                                "sql": bad_sql,
                            },
                        }
                        bad_hop1_json = json.dumps(bad_hop1_obj, separators=(",", ":"))
                        err_json = json.dumps(err_payload, separators=(",", ":"))

                        p0 = build_two_hop_prompt(question, pruned_ddl)
                        p1 = append_tool_turn(p0, bad_hop1_json, err_payload)
                        p2 = append_tool_turn(p1, hop1_json, summary)
                        full_text = f"{p2}{hop2_json}<|im_end|>\n"

                        split_b.append(
                            {
                                "id": f"split_b_{len(split_b):04d}",
                                "split": "B_self_healing",
                                "domain": "k12",
                                "question": question,
                                "gold_sql": cleaned_sql,
                                "output_columns": output_cols,
                                "messages": [
                                    {"role": "system", "content": system_content},
                                    {"role": "user", "content": question},
                                    {
                                        "role": "assistant",
                                        "content": bad_hop1_json,
                                        "loss_mask": False,
                                    },
                                    {"role": "tool", "content": err_json},
                                    {"role": "assistant", "content": hop1_json, "loss_mask": True},
                                    {"role": "tool", "content": summary_json},
                                    {"role": "assistant", "content": hop2_json, "loss_mask": True},
                                ],
                                "text": full_text,
                            }
                        )
                        continue

        # Try Split C (2-Turn Conversational Refinement) if needed
        if len(split_c) < target_c:
            followup = create_followup_turn(question, cleaned_sql)
            if followup is not None:
                f_q, f_sql = followup
                try:
                    f_cleaned_sql, _, f_summary = compute_result_summary(
                        conn, f_sql, query_id=f"q_train_{idx:05d}_t2"
                    )
                    if f_summary["row_count"] > 0 and f_summary["columns"]:
                        f_cols = [c["name"] for c in f_summary["columns"]]
                        f_hop1_obj = {
                            "tool": "execute_duckdb_query",
                            "arguments": {
                                "explanation": f"Refine previous query to answer follow-up: {f_q}",
                                "sql": f_cleaned_sql,
                            },
                        }
                        f_hop1_json = json.dumps(f_hop1_obj, separators=(",", ":"))
                        f_hop2_obj = synthesize_semantic_hop2_ui(f_q, f_summary)
                        f_hop2_json = json.dumps(f_hop2_obj, separators=(",", ":"))
                        ok1, _ = validate_hop1_call(f_hop1_json)
                        ok2, _ = validate_hop2_call(f_hop2_json, valid_columns=f_cols)
                        if ok1 and ok2:
                            f_summary_json = json.dumps(f_summary, separators=(",", ":"))
                            p0 = build_two_hop_prompt(question, pruned_ddl)
                            p1 = append_tool_turn(p0, hop1_json, summary)
                            turn1_done = f"{p1}{hop2_json}<|im_end|>\n"
                            turn2_start = f"{turn1_done}<|im_start|>user\n{f_q}<|im_end|>\n<|im_start|>assistant\n"
                            turn2_after_tool = append_tool_turn(turn2_start, f_hop1_json, f_summary)
                            full_text = f"{turn2_after_tool}{f_hop2_json}<|im_end|>\n"

                            split_c.append(
                                {
                                    "id": f"split_c_{len(split_c):04d}",
                                    "split": "C_multi_turn",
                                    "domain": "k12",
                                    "question": question,
                                    "gold_sql": cleaned_sql,
                                    "output_columns": f_cols,
                                    "messages": [
                                        {"role": "system", "content": system_content},
                                        {"role": "user", "content": question},
                                        {
                                            "role": "assistant",
                                            "content": hop1_json,
                                            "loss_mask": True,
                                        },
                                        {"role": "tool", "content": summary_json},
                                        {
                                            "role": "assistant",
                                            "content": hop2_json,
                                            "loss_mask": True,
                                        },
                                        {"role": "user", "content": f_q},
                                        {
                                            "role": "assistant",
                                            "content": f_hop1_json,
                                            "loss_mask": True,
                                        },
                                        {"role": "tool", "content": f_summary_json},
                                        {
                                            "role": "assistant",
                                            "content": f_hop2_json,
                                            "loss_mask": True,
                                        },
                                    ],
                                    "text": full_text,
                                }
                            )
                            continue
                except Exception:
                    pass

        # Otherwise add to Split A (Golden 2-Hop)
        if len(split_a) < target_a:
            p0 = build_two_hop_prompt(question, pruned_ddl)
            p1 = append_tool_turn(p0, hop1_json, summary)
            full_text = f"{p1}{hop2_json}<|im_end|>\n"
            split_a.append(
                {
                    "id": f"split_a_{len(split_a):04d}",
                    "split": "A_golden_two_hop",
                    "domain": "k12",
                    "question": question,
                    "gold_sql": cleaned_sql,
                    "output_columns": output_cols,
                    "messages": [
                        {"role": "system", "content": system_content},
                        {"role": "user", "content": question},
                        {"role": "assistant", "content": hop1_json, "loss_mask": True},
                        {"role": "tool", "content": summary_json},
                        {"role": "assistant", "content": hop2_json, "loss_mask": True},
                    ],
                    "text": full_text,
                }
            )

    conn.close()
    combined = split_a + split_b + split_c
    rng.shuffle(combined)
    print(
        f"Built {len(combined)} verified K-12 trajectories: "
        f"Split A={len(split_a)}, Split B={len(split_b)}, Split C={len(split_c)}"
    )
    return combined


@app.function(
    image=datagen_image,
    volumes={"/data": volume},
    secrets=[modal.Secret.from_name("huggingface-secret")],
    timeout=3600,
    cpu=4.0,
    memory=16384,
)
def synthesize_and_publish_remote(target_total: int = 3000) -> dict[str, Any]:
    """Modal function that synthesizes 3,000 verified K-12 Two-Hop trajectories on `/data`,
    commits to `lfed-training-data`, and pushes to Hugging Face Hub (`KDDSTLC/lfed-lfm3-two-hop-trajectories`).
    """
    import os

    from huggingface_hub import HfApi

    k12_source = "/data/pairs_warehouse.jsonl"
    trajectories = build_verified_trajectories(
        target_total=target_total,
        k12_pairs_path=k12_source,
    )

    out_path = Path(f"/data/{REMOTE_JSONL_NAME}")
    with out_path.open("w", encoding="utf-8") as f:
        for row in trajectories:
            f.write(json.dumps(row) + "\n")
    volume.commit()

    hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    api = HfApi(token=hf_token)
    api.create_repo(repo_id=HF_DATASET_REPO, repo_type="dataset", exist_ok=True)
    api.upload_file(
        path_or_fileobj=str(out_path),
        path_in_repo="train.jsonl",
        repo_id=HF_DATASET_REPO,
        repo_type="dataset",
        commit_message=f"Upload {len(trajectories)} verified K-12 Education Two-Hop trajectories for LiquidAI/LFM3-1.7B",
    )
    return {
        "total": len(trajectories),
        "volume_path": str(out_path),
        "hf_dataset_repo": HF_DATASET_REPO,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Build & publish 3,000 verified K-12 Two-Hop trajectories"
    )
    parser.add_argument("--total", type=int, default=3000)
    parser.add_argument(
        "--output",
        type=str,
        default=str(PROJECT_ROOT / "training" / REMOTE_JSONL_NAME),
    )
    parser.add_argument("--push-hf", action="store_true", help="Upload dataset to Hugging Face Hub")
    args = parser.parse_args()

    trajectories = build_verified_trajectories(target_total=args.total)
    out_file = Path(args.output)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with out_file.open("w", encoding="utf-8") as f:
        for item in trajectories:
            f.write(json.dumps(item) + "\n")
    print(f"Saved {len(trajectories)} trajectories -> {out_file}")

    if args.push_hf:
        from huggingface_hub import HfApi

        api = HfApi()
        api.create_repo(repo_id=HF_DATASET_REPO, repo_type="dataset", exist_ok=True)
        api.upload_file(
            path_or_fileobj=str(out_file),
            path_in_repo="train.jsonl",
            repo_id=HF_DATASET_REPO,
            repo_type="dataset",
            commit_message=f"Upload {len(trajectories)} verified K-12 Education Two-Hop trajectories for LiquidAI/LFM3-1.7B",
        )
        print(f"Published dataset to https://huggingface.co/datasets/{HF_DATASET_REPO}")
