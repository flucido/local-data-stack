"""
schema_pruner.py — Deterministic Top-K Schema Pruner (BM25 + Foreign-Key Graph) for K-12 Education Warehouse.

Implements Top-K Schema Pruning for our 20-table K-12 Education Analytics Warehouse
(`main_core`, `main_analytics`, `main_staging`):
  - Sub-3B models lose column-name attention if all 20 warehouse tables (~4,000 tokens of DDL)
    are dumped into every prompt.
  - `select_top_k_tables(question, schema, k=5)` scores every K-12 table using BM25 over table names,
    column names, column descriptions, and K-12 domain keyword synonyms (Aeries + CDE), plus 1-hop
    foreign-key join graph boosts (`student_id_hash`, `cds_code`, `school_id`, `academic_year`,
    `school_year`, `reporting_category`), selecting the top 4-6 relevant tables (<800 tokens).
  - `select_training_tables_with_distractors(question, gold_sql, schema, k=5)` constructs training
    DDL prompts containing the 1-2 gold tables referenced by `gold_sql` plus 3-4 hard-negative
    BM25 distractor tables shuffled in random order to prevent train/inference mismatch.
"""

from __future__ import annotations

import json
import math
import random
import re
from pathlib import Path
from typing import Any

SCHEMA_JSON_PATH = Path(__file__).resolve().parent / "training_schema.json"

# Join keys that link fact, dimension, and CDE staging/mart tables across the K-12 schema
JOIN_KEYS = {
    "student_id_hash",
    "cds_code",
    "school_id",
    "academic_year",
    "school_year",
    "reporting_category",
    "primary_race",
    "course_id",
    "teacher_id_hash",
}

# K-12 Education (Aeries SIS + California Dept. of Education) domain synonym expansion
DOMAIN_SYNONYMS: dict[str, list[str]] = {
    "absent": [
        "absenteeism",
        "chronic",
        "attendance",
        "days_absent",
        "ca_chronic_absent_rate_pct",
        "absence_rate",
    ],
    "absenteeism": [
        "chronic",
        "attendance",
        "mart_cde_school_accountability",
        "stg_cde__chronic_absenteeism",
        "v_chronic_absenteeism_risk",
        "ca_chronic_absent_rate_pct",
    ],
    "chronic": [
        "absenteeism",
        "ca_chronic_absent_rate_pct",
        "chronic_absent_rate_pct",
        "v_chronic_absenteeism_risk",
        "chronic_absence_flag",
    ],
    "attendance": [
        "fact_attendance",
        "attendance_rate",
        "days_enrolled",
        "days_absent",
        "days_present",
        "pct_good_attendance",
    ],
    "truancy": ["fact_attendance", "days_truancy", "days_unexcused", "days_tardy"],
    "tardy": ["fact_attendance", "days_tardy"],
    "suspend": [
        "suspension",
        "discipline",
        "incident_type",
        "suspension_days",
        "su_suspension_rate_pct",
        "pct_suspended",
    ],
    "suspension": [
        "discipline",
        "fact_discipline",
        "stg_cde__suspension",
        "mart_cde_school_accountability",
        "su_suspension_rate_pct",
        "su_total_suspensions",
        "pct_suspended",
    ],
    "discipline": [
        "fact_discipline",
        "incident_type",
        "severity",
        "suspension_days",
        "avg_discipline_incidents",
    ],
    "incident": ["fact_discipline", "incident_type", "incident_id", "serious_incident_flag"],
    "incidents": ["fact_discipline", "incident_type", "avg_discipline_incidents"],
    "expel": ["expulsion", "stg_cde__expulsion", "ex_total_expulsions", "total_expulsions"],
    "expulsion": [
        "stg_cde__expulsion",
        "mart_cde_school_accountability",
        "ex_total_expulsions",
        "expulsion_rate_total",
    ],
    "expulsions": [
        "stg_cde__expulsion",
        "mart_cde_school_accountability",
        "ex_total_expulsions",
        "total_expulsions",
    ],
    "meal": [
        "frpm",
        "free_reduced_lunch_flag",
        "frpm_free_pct_k12",
        "stg_cde__frpm",
        "free_meal_count_k12",
    ],
    "lunch": ["frpm", "free_reduced_lunch_flag", "frpm_free_pct_k12", "stg_cde__frpm", "pct_frl"],
    "frpm": [
        "stg_cde__frpm",
        "mart_cde_school_accountability",
        "frpm_free_pct_k12",
        "percent_eligible_frpm_k12",
    ],
    "poverty": [
        "frpm",
        "socioeconomically",
        "free_reduced_lunch_flag",
        "economically_disadvantaged",
    ],
    "disadvantaged": [
        "reporting_category",
        "se",
        "economically_disadvantaged",
        "free_reduced_lunch_flag",
    ],
    "homeless": [
        "homeless_flag",
        "stg_cde__homeless_enrollment",
        "homeless_student_enrollment",
        "hs_homeless_count",
        "homeless_count",
    ],
    "shelter": [
        "stg_cde__homeless_enrollment",
        "temporary_shelters",
        "hs_shelters_pct",
        "temporarily_doubled_up",
    ],
    "foster": ["foster_care_flag", "reporting_category", "fos"],
    "hispanic": [
        "reporting_category",
        "ethnicity",
        "primary_race",
        "equity_by_race",
        "rh",
        "pct_hispanic",
    ],
    "black": ["reporting_category", "primary_race", "equity_by_race", "rb", "pct_black"],
    "asian": ["reporting_category", "primary_race", "equity_by_race", "ra", "pct_asian"],
    "white": ["reporting_category", "primary_race", "equity_by_race", "rw", "pct_white"],
    "race": [
        "ethnicity",
        "primary_race",
        "reporting_category",
        "equity_by_race",
        "race_ethnicity",
        "v_equity_outcomes_by_demographics",
    ],
    "equity": [
        "equity_by_race",
        "v_equity_outcomes_by_demographics",
        "primary_race",
        "race_ethnicity",
    ],
    "gap": ["equity_by_race", "v_equity_outcomes_by_demographics", "pct_suspended", "avg_gpa"],
    "demographic": [
        "dim_student_demographics",
        "dim_students",
        "v_equity_outcomes_by_demographics",
    ],
    "demographics": [
        "dim_student_demographics",
        "dim_students",
        "v_equity_outcomes_by_demographics",
    ],
    "english": [
        "ell_status",
        "home_language",
        "reporting_category",
        "el",
        "english_learner",
        "pct_ell",
        "dim_students",
    ],
    "learner": [
        "ell_status",
        "reporting_category",
        "english_learner",
        "elpac_progressed_pct",
        "dim_students",
    ],
    "learners": ["ell_status", "reporting_category", "english_learner", "pct_ell", "dim_students"],
    "elpac": ["mart_cde_school_accountability", "elpac_progressed_pct", "elpac_maintained_pl4_pct"],
    "special": [
        "special_education_flag",
        "special_education",
        "pct_special_ed",
        "special_ed_count",
        "swd",
    ],
    "disability": ["special_education_flag", "reporting_category", "swd"],
    "disabilities": ["special_education_flag", "reporting_category", "swd"],
    "gpa": ["fact_academic_records", "gpa_points", "grade", "course_id", "is_passing", "avg_gpa"],
    "grade": ["grade_level", "fact_academic_records", "gpa_points", "dim_students"],
    "course": ["fact_academic_records", "course_id", "section_id", "credit_earned", "is_passing"],
    "failing": ["fact_academic_records", "gpa_points", "is_passing", "pct_below_c"],
    "test": [
        "assessment",
        "caspp",
        "stg_cde__assessment_caspp",
        "sbac_mean_scale_score",
        "sbac_pct_standard_met_above",
    ],
    "sbac": [
        "mart_cde_school_accountability",
        "stg_cde__assessment_caspp",
        "sbac_pct_standard_met_above",
        "sbac_mean_scale_score",
    ],
    "caspp": ["stg_cde__assessment_caspp", "mean_scale_score", "pct_standard_met_and_above"],
    "proficiency": [
        "mart_cde_school_accountability",
        "stg_cde__assessment_caspp",
        "sbac_pct_standard_met_above",
    ],
    "restraint": [
        "stg_cde__restraint_seclusion",
        "count_of_physical_restraints",
        "count_of_mechanical_restraints",
        "rs_physical_restraints",
    ],
    "restraints": [
        "stg_cde__restraint_seclusion",
        "count_of_physical_restraints",
        "count_of_mechanical_restraints",
        "rs_physical_restraints",
    ],
    "seclusion": ["stg_cde__restraint_seclusion", "count_of_seclusions", "rs_seclusions"],
    "physical": [
        "stg_cde__restraint_seclusion",
        "count_of_physical_restraints",
        "rs_physical_restraints",
    ],
    "enrollment": [
        "fact_enrollment",
        "stg_cde__enrollment",
        "cumulative_enrollment",
        "en_cumulative_enrollment",
        "dim_students",
    ],
    "enrolled": ["fact_enrollment", "dim_students", "stg_cde__enrollment", "days_enrolled"],
    "risk": [
        "v_chronic_absenteeism_risk",
        "school_summary",
        "equity_by_race",
        "pct_high_risk",
        "risk_level",
    ],
}


def load_unified_schema(include_finance: bool = False) -> dict[str, list[dict[str, Any]]]:
    """Load the 20 K-12 Education warehouse tables from `training_schema.json`."""
    _ = include_finance  # Kept for signature backward compatibility; always returns pure K-12 schema
    tables: dict[str, list[dict[str, Any]]] = {}
    if SCHEMA_JSON_PATH.exists():
        raw = json.loads(SCHEMA_JSON_PATH.read_text(encoding="utf-8"))
        for t_name, cols in raw.get("tables", {}).items():
            tables[t_name] = list(cols)
    return tables


def normalize_schema_dict(
    schema: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    """Normalize either `training_schema.json` (`{"tables": ...}`) or `data_engine.get_schema_info()`
    (`table -> [(col, type, desc)]`) into `table_name -> [{"name": ..., "type": ..., "description": ...}]`.
    """
    raw_tables = schema.get("tables", schema) if isinstance(schema, dict) else {}
    normalized: dict[str, list[dict[str, Any]]] = {}
    for table_name, cols in raw_tables.items():
        if not isinstance(cols, list):
            continue
        norm_cols: list[dict[str, Any]] = []
        for c in cols:
            if isinstance(c, dict):
                norm_cols.append(
                    {
                        "name": str(c.get("name", "")),
                        "type": str(c.get("type", "VARCHAR")),
                        "description": str(c.get("description", "")),
                        "sample_values": c.get("sample_values", []),
                    }
                )
            elif isinstance(c, tuple | list) and len(c) >= 2:
                norm_cols.append(
                    {
                        "name": str(c[0]),
                        "type": str(c[1]),
                        "description": str(c[2]) if len(c) > 2 else "",
                        "sample_values": [],
                    }
                )
        normalized[table_name] = norm_cols
    return normalized


# ── Tokenization & BM25 Scoring ────────────────────────────────────────


def _tokenize(text: str) -> list[str]:
    """Split snake_case, schema dots, and natural language into lowercase tokens."""
    cleaned = re.sub(r"[^a-zA-Z0-9_]", " ", text.lower())
    raw_tokens = cleaned.split()
    tokens: list[str] = []
    for tok in raw_tokens:
        tokens.append(tok)
        if "_" in tok:
            tokens.extend(part for part in tok.split("_") if len(part) > 1)
    return [t for t in tokens if len(t) > 1]


def _expand_query_tokens(question: str) -> list[str]:
    base_tokens = _tokenize(question)
    expanded = list(base_tokens)
    for tok in base_tokens:
        if tok in DOMAIN_SYNONYMS:
            for syn in DOMAIN_SYNONYMS[tok]:
                expanded.extend(_tokenize(syn))
    return expanded


def _build_table_document(
    table_name: str, columns: list[dict[str, Any]]
) -> tuple[list[str], set[str]]:
    """Return `(bag_of_tokens, join_keys_present)` for a table."""
    doc_tokens: list[str] = []
    doc_tokens.extend(_tokenize(table_name) * 3)
    join_keys: set[str] = set()
    for col in columns:
        c_name = col.get("name", "")
        if c_name in JOIN_KEYS:
            join_keys.add(c_name)
        doc_tokens.extend(_tokenize(c_name) * 2)
        if col.get("description"):
            doc_tokens.extend(_tokenize(str(col["description"])))
        for sv in col.get("sample_values", []) or []:
            doc_tokens.extend(_tokenize(str(sv)))
    return doc_tokens, join_keys


def score_tables_bm25(
    question: str,
    schema: dict[str, Any],
    k1: float = 1.5,
    b: float = 0.75,
) -> list[tuple[str, float]]:
    """Rank all K-12 tables in `schema` against `question` using BM25 + 1-hop FK join boosts."""
    norm_schema = normalize_schema_dict(schema)
    if not norm_schema:
        return []

    query_tokens = _expand_query_tokens(question)
    table_docs: dict[str, list[str]] = {}
    table_join_keys: dict[str, set[str]] = {}
    doc_freq: dict[str, int] = {}

    for t_name, cols in norm_schema.items():
        tokens, j_keys = _build_table_document(t_name, cols)
        table_docs[t_name] = tokens
        table_join_keys[t_name] = j_keys
        for unique_tok in set(tokens):
            doc_freq[unique_tok] = doc_freq.get(unique_tok, 0) + 1

    num_docs = len(norm_schema)
    avg_dl = sum(len(d) for d in table_docs.values()) / max(num_docs, 1)

    raw_scores: dict[str, float] = {}
    for t_name, doc in table_docs.items():
        dl = len(doc)
        tf_map: dict[str, int] = {}
        for tok in doc:
            tf_map[tok] = tf_map.get(tok, 0) + 1

        score = 0.0
        for q_tok in query_tokens:
            tf = tf_map.get(q_tok, 0)
            if tf == 0:
                continue
            df = doc_freq.get(q_tok, 0)
            idf = math.log(1.0 + (num_docs - df + 0.5) / (df + 0.5))
            denom = tf + k1 * (1.0 - b + b * (dl / max(avg_dl, 1.0)))
            score += idf * ((tf * (k1 + 1.0)) / denom)

        if "mart_" in t_name or "main_analytics." in t_name:
            score += 0.35
        elif "main_core." in t_name:
            score += 0.20

        raw_scores[t_name] = score

    # 1-hop foreign-key join expansion: boost dimension/sibling tables that share join keys
    sorted_initial = sorted(raw_scores.items(), key=lambda x: x[1], reverse=True)
    top_anchors = [t for t, s in sorted_initial[:2] if s > 0]
    anchor_keys: set[str] = set()
    for anchor in top_anchors:
        anchor_keys |= table_join_keys.get(anchor, set())

    final_scores: dict[str, float] = {}
    for t_name, base_score in raw_scores.items():
        shared = anchor_keys & table_join_keys.get(t_name, set())
        fk_boost = 0.4 * len(shared) if shared and t_name not in top_anchors else 0.0
        if shared and (".dim_" in t_name or t_name.startswith("dim_")):
            fk_boost += 0.5
        final_scores[t_name] = round(base_score + fk_boost, 4)

    return sorted(final_scores.items(), key=lambda x: (-x[1], x[0]))


def select_top_k_tables(
    question: str,
    schema: dict[str, Any],
    k: int = 5,
) -> dict[str, list[dict[str, Any]]]:
    """Select the top `k` most relevant K-12 warehouse tables for `question`."""
    norm_schema = normalize_schema_dict(schema)
    ranked = score_tables_bm25(question, norm_schema)
    selected_names = [t_name for t_name, _ in ranked[: max(1, k)]]
    return {t_name: norm_schema[t_name] for t_name in selected_names}


def extract_referenced_tables(sql: str, available_tables: set[str]) -> list[str]:
    """Extract tables from `available_tables` referenced in `sql`."""
    sql_lower = sql.lower()
    matched: list[str] = []
    for t_name in sorted(available_tables):
        bare_name = t_name.split(".")[-1].lower()
        if t_name.lower() in sql_lower or re.search(rf"\b{re.escape(bare_name)}\b", sql_lower):
            matched.append(t_name)
    return matched


def select_training_tables_with_distractors(
    question: str,
    gold_sql: str,
    schema: dict[str, Any],
    k: int = 5,
    seed: int | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Construct a pruned K-12 training DDL schema:
    - Always includes the 1-2 gold tables actually referenced by `gold_sql`.
    - Fills the remaining slots up to `k` (4-6 tables) with the highest-scoring BM25
      hard-negative distractor tables for `question`.
    - Shuffles the table ordering so the model does not learn positional bias.
    """
    norm_schema = normalize_schema_dict(schema)
    gold_tables = extract_referenced_tables(gold_sql, set(norm_schema.keys()))
    ranked = [t_name for t_name, _ in score_tables_bm25(question, norm_schema)]

    chosen: list[str] = list(gold_tables)
    for candidate in ranked:
        if len(chosen) >= max(k, len(gold_tables)):
            break
        if candidate not in chosen:
            chosen.append(candidate)

    rng = random.Random(seed)
    rng.shuffle(chosen)
    return {t_name: norm_schema[t_name] for t_name in chosen}


def format_pruned_ddl(pruned_schema: dict[str, Any]) -> str:
    """Format a pruned 4-6 table K-12 schema into a compact DDL block (<800 tokens)."""
    norm = normalize_schema_dict(pruned_schema)
    lines = ["AVAILABLE WAREHOUSE TABLES (TOP-K PRUNED):"]
    for idx, (table_name, cols) in enumerate(norm.items(), 1):
        col_parts: list[str] = []
        for c in cols:
            base = f"{c['name']} ({c['type']})"
            samples = c.get("sample_values")
            if samples:
                sample_str = ", ".join(repr(s) for s in samples[:4])
                base += f" [e.g. {sample_str}]"
            col_parts.append(base)
        lines.append(f"{idx}. {table_name}: {', '.join(col_parts)}")
    return "\n".join(lines)
