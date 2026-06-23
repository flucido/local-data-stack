"""
prompts.py — System prompt, few-shot examples, and schema documentation.

Used by model_inference.py to assemble the full prompt before inference.

Unlike the original (flat 5-table seed schema), this builds the schema
context from the **live warehouse introspection** returned by
data_engine.get_schema_info(): fully-qualified ``schema.table`` names across
the exposed core / analytics / cde layers.
"""

from __future__ import annotations

# ── System prompt (schema-agnostic rules) ──────────────────────────────

SYSTEM_PROMPT = """You are an expert DuckDB SQL developer for school district administration.
Generate ONLY valid DuckDB SQL queries wrapped in ```sql ``` markdown blocks.
Follow these rules strictly:

1. Only SELECT statements — never INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE.
2. Use the exact, fully-qualified table names from the schema below (e.g. main_core.dim_students).
3. Use proper DuckDB syntax: VARCHAR comparisons use single quotes, BOOLEAN checks use TRUE/FALSE.
4. When aggregating, use clear column aliases (e.g., AS total_students).
5. Join on the columns that logically connect the tables — student-grain tables join on student_id_hash; school-grain tables join on cds_code or school_id.
6. Student identity is pseudonymized: student identities are represented by student_id_hash only. Direct PII columns (names, dates of birth, raw student IDs) are not available.
7. There are two query paths for CDE aggregate data:
   - For multi-metric school comparisons, use main_analytics.mart_cde_school_accountability (pre-joined OBT).
   - For detailed single-domain queries, use the staging tables directly (e.g. main_staging.stg_cde__suspension).
8. CDE reporting_category codes: TA=All Students, RA=Asian, RB=Black, RH=Hispanic, GM=Male, GF=Female, SE=Socioeconomically Disadvantaged, EL=English Learners, SWD=Students with Disabilities, HOM=Homeless, FOS=Foster Youth.
9. If the question is ambiguous, make a reasonable assumption and generate the query.
10. Do NOT include any explanation outside the ```sql ``` block."""


# ── Schema documentation builder ───────────────────────────────────────


def build_schema_context(tables: dict[str, list[tuple[str, str, str]]]) -> str:
    """
    Build a formatted schema context string for prompt injection.

    Args:
        tables: dict of table_name -> list of (column_name, type, description)
                (description may be empty when sourced from live introspection)

    Returns:
        Formatted string like:
            1. Table: main_core.dim_students
                 student_id_hash (VARCHAR)
                 ...
    """
    lines = ["Available Tables & Schemas:"]
    for idx, (table_name, columns) in enumerate(tables.items(), 1):
        lines.append(f"\n{idx}. Table: {table_name}")
        for col_name, col_type, col_desc in columns:
            if col_desc:
                lines.append(f"   {col_name} ({col_type}) — {col_desc}")
            else:
                lines.append(f"   {col_name} ({col_type})")
    return "\n".join(lines)


# ── Fallback schema (used only if live introspection is unavailable) ───
# Minimal hint covering the highest-signal core + analytics tables. The
# real schema is normally injected from data_engine.get_schema_info().

DEFAULT_SCHEMA = {
    # ── Aeries student-level (core) ──────────────────────────────────
    "main_core.dim_students": [
        ("student_id_hash", "VARCHAR", "Pseudonymized student key (joins to fact_* tables)"),
        ("academic_year", "VARCHAR", "School year (format 'YYYY-YYYY')"),
        ("school_id", "VARCHAR", "School identifier (CDS code)"),
        ("grade_level", "INTEGER", "Grade level (K=0, 1-12)"),
        ("gender", "VARCHAR", "Gender code"),
        ("primary_race", "VARCHAR", "Primary race/ethnicity category"),
        ("ell_status", "BOOLEAN", "TRUE if English Learner"),
        ("special_education_flag", "BOOLEAN", "TRUE if receives special education"),
        ("free_reduced_lunch_flag", "BOOLEAN", "TRUE if qualifies for FRL"),
    ],
    "main_core.fact_attendance": [
        ("student_id_hash", "VARCHAR", "Pseudonymized student key"),
        ("school_id", "VARCHAR", "School identifier"),
        ("academic_year", "VARCHAR", "School year"),
        ("days_enrolled", "INTEGER", "Days enrolled"),
        ("days_absent", "INTEGER", "Total days absent"),
        ("attendance_rate", "DOUBLE", "Attendance rate (0-1)"),
        ("absence_rate", "DOUBLE", "Absence rate (0-1)"),
    ],
    "main_core.fact_discipline": [
        ("student_id_hash", "VARCHAR", "Pseudonymized student key"),
        ("school_id", "VARCHAR", "School identifier"),
        ("academic_year", "VARCHAR", "School year"),
        ("incident_type", "VARCHAR", "Type of incident"),
        ("severity", "VARCHAR", "Incident severity"),
        ("suspension_days", "INTEGER", "Days suspended"),
    ],
    "main_core.fact_academic_records": [
        ("student_id_hash", "VARCHAR", "Pseudonymized student key"),
        ("school_id", "VARCHAR", "School identifier"),
        ("school_year", "VARCHAR", "School year"),
        ("course_id", "VARCHAR", "Course identifier"),
        ("term", "VARCHAR", "Term (Fall/Spring)"),
        ("grade", "VARCHAR", "Letter grade"),
        ("gpa_points", "DOUBLE", "GPA points for this grade"),
        ("is_passing", "BOOLEAN", "TRUE if passing grade"),
    ],
    # ── CDE OBT (pre-joined school accountability metrics) ──────────
    "main_analytics.mart_cde_school_accountability": [
        ("cds_code", "VARCHAR", "14-char school identifier"),
        ("academic_year", "VARCHAR", "School year (format 'YYYY-YY', e.g., '2023-24')"),
        (
            "reporting_category",
            "VARCHAR",
            "Subgroup code: TA=all, RA=Asian, RB=Black, RH=Hispanic, SE=Socioeconomically Disadvantaged, EL=English Learners, SWD=Students with Disabilities",
        ),
        ("reporting_category_label", "VARCHAR", "Human-readable subgroup name"),
        ("school_name", "VARCHAR", "School name (from dim_schools)"),
        ("district_name", "VARCHAR", "District name"),
        ("county_name", "VARCHAR", "County name"),
        ("ca_eligible_enrollment", "INTEGER", "Chronic absenteeism: students enrolled >= 31 days"),
        (
            "ca_chronic_absent_count",
            "INTEGER",
            "Chronic absenteeism: students missing >= 10% of days",
        ),
        ("ca_chronic_absent_rate_pct", "DOUBLE", "Chronic absenteeism rate (%)"),
        ("en_cumulative_enrollment", "INTEGER", "Cumulative enrollment for the year"),
        ("su_total_suspensions", "INTEGER", "Total suspension incidents"),
        ("su_suspension_rate_pct", "DOUBLE", "Suspension rate (%)"),
        ("su_violent_injury", "INTEGER", "Suspensions for violent incident (injury)"),
        ("su_weapons", "INTEGER", "Suspensions for weapons possession"),
        ("su_drug_related", "INTEGER", "Suspensions for illicit drug-related"),
        ("ex_total_expulsions", "INTEGER", "Total expulsion incidents"),
        ("ex_expulsion_rate_pct", "DOUBLE", "Expulsion rate (%)"),
        ("hs_homeless_count", "INTEGER", "Homeless student enrollment count"),
        ("frpm_free_pct_k12", "DOUBLE", "Percent eligible for free meals (K-12)"),
        ("frpm_reduced_pct_k12", "DOUBLE", "Percent eligible for reduced price meals (K-12)"),
        ("ela_currstatus", "DOUBLE", "ELA assessment current status metric"),
        ("ela_status", "VARCHAR", "ELA dashboard status level"),
        ("sbac_mean_scale_score", "DOUBLE", "SBAC/CAASPP mean scale score"),
        ("sbac_pct_standard_met_above", "DOUBLE", "SBAC % met or above standard"),
        ("sbac_students_tested", "INTEGER", "Students tested on SBAC"),
        ("elpac_progressed_pct", "DOUBLE", "ELPAC % progressed"),
        ("rs_mechanical_restraints", "INTEGER", "Count of mechanical restraints"),
        ("rs_physical_restraints", "INTEGER", "Count of physical restraints"),
        ("rs_seclusions", "INTEGER", "Count of seclusions"),
        ("is_suppressed", "BOOLEAN", "TRUE if CDE suppressed data (n < 11)"),
        ("has_cde_data", "BOOLEAN", "TRUE if any CDE domain has data"),
        ("data_domains_present", "INTEGER", "Count of CDE domains with data (0-11)"),
    ],
    # ── CDE staging tables (for detailed single-domain queries) ─────
    "main_staging.stg_cde__chronic_absenteeism": [
        ("cds_code", "VARCHAR", "14-char school identifier"),
        ("academic_year", "VARCHAR", "School year"),
        ("aggregate_level", "VARCHAR", "T=State, C=County, D=District, S=School"),
        ("reporting_category", "VARCHAR", "Subgroup code"),
        ("eligible_enrollment", "INTEGER", "Students enrolled >= 31 days"),
        ("chronic_absent_count", "INTEGER", "Students missing >= 10% of days"),
        ("chronic_absent_rate_pct", "DOUBLE", "Chronic absenteeism rate (%)"),
    ],
    "main_staging.stg_cde__suspension": [
        ("cds_code", "VARCHAR", "14-char school identifier"),
        ("academic_year", "VARCHAR", "School year"),
        ("aggregate_level", "VARCHAR", "T/C/D/S"),
        ("reporting_category", "VARCHAR", "Subgroup code"),
        ("total_suspensions", "INTEGER", "Total suspension incidents"),
        ("suspension_rate_total", "DOUBLE", "Suspension rate (%)"),
        ("suspension_count_violent_incident_injury", "INTEGER", "Violent incident (injury)"),
        ("suspension_count_weapons_possession", "INTEGER", "Weapons possession"),
        ("suspension_count_illicit_drug_related", "INTEGER", "Illicit drug-related"),
        ("suspension_count_defiance_only", "INTEGER", "Defiance-only"),
    ],
    "main_staging.stg_cde__enrollment": [
        ("cds_code", "VARCHAR", "14-char school identifier"),
        ("academic_year", "VARCHAR", "School year"),
        ("aggregate_level", "VARCHAR", "T/C/D/S"),
        ("reporting_category", "VARCHAR", "Subgroup code"),
        ("cumulative_enrollment", "INTEGER", "Cumulative enrollment"),
    ],
    "main_staging.stg_cde__homeless_enrollment": [
        ("cds_code", "VARCHAR", "14-char school identifier"),
        ("academic_year", "VARCHAR", "School year"),
        ("reporting_category", "VARCHAR", "Subgroup code"),
        ("cumulative_enrollment", "INTEGER", "Total enrollment"),
        ("homeless_student_enrollment", "INTEGER", "Homeless student count"),
        ("temporarily_doubled_up_percent", "DOUBLE", "% temporarily doubled up"),
    ],
    "main_staging.stg_cde__frpm": [
        ("cds_code", "VARCHAR", "14-char school identifier"),
        ("academic_year", "VARCHAR", "School year"),
        ("enrollment_k12", "INTEGER", "K-12 enrollment"),
        ("free_meal_count_k12", "INTEGER", "Free meal count (K-12)"),
        ("percent_eligible_free_k12", "DOUBLE", "% eligible free (K-12)"),
        ("frpm_count_k12", "INTEGER", "FRPM count (K-12)"),
        ("percent_eligible_frpm_k12", "DOUBLE", "% eligible FRPM (K-12)"),
    ],
    "main_staging.stg_cde__assessment_caspp": [
        ("cds_code", "VARCHAR", "14-char school identifier"),
        ("academic_year", "VARCHAR", "School year"),
        ("reporting_category", "VARCHAR", "Subgroup code (student_group_id)"),
        ("mean_scale_score", "DOUBLE", "Mean scale score"),
        ("percentage_standard_met_and_above", "DOUBLE", "% met or above standard"),
        ("students_tested", "INTEGER", "Students tested"),
    ],
    # ── Existing analytics marts ────────────────────────────────────
    "main_analytics.school_summary": [
        ("school_id", "VARCHAR", "School identifier"),
        ("student_count", "BIGINT", "Number of students"),
        ("avg_attendance_rate", "DOUBLE", "Average attendance rate"),
        ("avg_gpa", "DOUBLE", "Average GPA"),
        ("pct_high_risk", "DOUBLE", "Percent of students at high risk"),
    ],
    "main_analytics.equity_by_race": [
        ("primary_race", "VARCHAR", "Primary race/ethnicity category"),
        ("student_count", "BIGINT", "Number of students in group"),
        ("avg_attendance_rate", "DOUBLE", "Average attendance rate"),
        ("avg_gpa", "DOUBLE", "Average GPA"),
        ("pct_suspended", "DOUBLE", "Percent suspended"),
    ],
}


# ── Few-shot examples (warehouse schema) ───────────────────────────────

FEW_SHOT_EXAMPLES = [
    # ── Student-level core queries ──────────────────────────────────
    {
        "question": "How many students were enrolled in 2023-2024?",
        "sql": "SELECT COUNT(DISTINCT student_id_hash) AS student_count\nFROM main_core.dim_students\nWHERE academic_year = '2023-2024';",
    },
    {
        "question": "What is the average attendance rate by school in 2023-2024?",
        "sql": "SELECT school_id, ROUND(AVG(attendance_rate), 4) AS avg_attendance_rate\nFROM main_core.fact_attendance\nWHERE academic_year = '2023-2024'\nGROUP BY school_id\nORDER BY avg_attendance_rate;",
    },
    {
        "question": "How many discipline incidents occurred by incident type in 2023-2024?",
        "sql": "SELECT incident_type, COUNT(*) AS incident_count, SUM(suspension_days) AS total_suspension_days\nFROM main_core.fact_discipline\nWHERE academic_year = '2023-2024'\nGROUP BY incident_type\nORDER BY incident_count DESC;",
    },
    {
        "question": "What is the average attendance rate for English Learners in 2023-2024?",
        "sql": "SELECT ROUND(AVG(a.attendance_rate), 4) AS avg_attendance_rate\nFROM main_core.fact_attendance a\nJOIN main_core.dim_students s\n  ON a.student_id_hash = s.student_id_hash\n  AND a.academic_year = s.academic_year\nWHERE a.academic_year = '2023-2024'\n  AND s.ell_status = TRUE;",
    },
    {
        "question": "What is the average GPA by grade level in 2023-2024?",
        "sql": "SELECT grade_level, ROUND(AVG(gpa_points), 2) AS avg_gpa\nFROM main_core.fact_academic_records\nWHERE school_year = '2023-2024'\nGROUP BY grade_level\nORDER BY grade_level;",
    },
    # ── OBT path (mart_cde_school_accountability) ──────────────────
    {
        "question": "What is the chronic absenteeism rate for Hispanic students in 2023-24?",
        "sql": "SELECT cds_code, ca_chronic_absent_rate_pct\nFROM main_analytics.mart_cde_school_accountability\nWHERE academic_year = '2023-24'\n  AND reporting_category = 'RH'\n  AND ca_chronic_absent_rate_pct IS NOT NULL\nORDER BY ca_chronic_absent_rate_pct DESC;",
    },
    {
        "question": "Compare suspension rates by race group for 2023-24.",
        "sql": "SELECT reporting_category_label,\n       ROUND(AVG(su_suspension_rate_pct), 2) AS avg_suspension_rate\nFROM main_analytics.mart_cde_school_accountability\nWHERE academic_year = '2023-24'\n  AND is_race_ethnicity_subgroup = TRUE\n  AND su_suspension_rate_pct IS NOT NULL\nGROUP BY reporting_category_label\nORDER BY avg_suspension_rate DESC;",
    },
    {
        "question": "Which schools have the highest free meal eligibility in 2023-24?",
        "sql": "SELECT cds_code, frpm_free_pct_k12\nFROM main_analytics.mart_cde_school_accountability\nWHERE academic_year = '2023-24'\n  AND reporting_category = 'TA'\n  AND frpm_free_pct_k12 IS NOT NULL\nORDER BY frpm_free_pct_k12 DESC\nLIMIT 20;",
    },
    {
        "question": "Compare chronic absenteeism and suspension rates for all race subgroups in 2023-24.",
        "sql": "SELECT reporting_category_label,\n       ROUND(AVG(ca_chronic_absent_rate_pct), 2) AS avg_chronic_absent,\n       ROUND(AVG(su_suspension_rate_pct), 2) AS avg_suspension\nFROM main_analytics.mart_cde_school_accountability\nWHERE academic_year = '2023-24'\n  AND is_race_ethnicity_subgroup = TRUE\nGROUP BY reporting_category_label\nORDER BY avg_chronic_absent DESC;",
    },
    # ── Staging path (stg_cde__*) ──────────────────────────────────
    {
        "question": "How many homeless students are in each district in 2023-24?",
        "sql": "SELECT district_name, SUM(homeless_student_enrollment) AS total_homeless\nFROM main_staging.stg_cde__homeless_enrollment\nWHERE academic_year = '2023-24'\n  AND aggregate_level = 'D'\n  AND reporting_category = 'TA'\n  AND homeless_student_enrollment IS NOT NULL\nGROUP BY district_name\nORDER BY total_homeless DESC;",
    },
    {
        "question": "What is the total number of suspensions across all schools in 2023-24?",
        "sql": "SELECT SUM(total_suspensions) AS total_suspensions\nFROM main_staging.stg_cde__suspension\nWHERE academic_year = '2023-24'\n  AND aggregate_level = 'S'\n  AND reporting_category = 'TA';",
    },
    {
        "question": "What percentage of students are eligible for free meals district-wide in 2023-24?",
        "sql": "SELECT cds_code, percent_eligible_free_k12\nFROM main_staging.stg_cde__frpm\nWHERE academic_year = '2023-24'\n  AND percent_eligible_free_k12 IS NOT NULL\nORDER BY percent_eligible_free_k12 DESC\nLIMIT 10;",
    },
    {
        "question": "How many total students were enrolled across all schools in 2023-24?",
        "sql": "SELECT SUM(cumulative_enrollment) AS total_enrollment\nFROM main_staging.stg_cde__enrollment\nWHERE academic_year = '2023-24'\n  AND aggregate_level = 'S'\n  AND reporting_category = 'TA';",
    },
    {
        "question": "What are the SBAC mean scale scores by reporting category for a school in 2023-24?",
        "sql": "SELECT reporting_category, ROUND(AVG(mean_scale_score), 1) AS avg_score\nFROM main_staging.stg_cde__assessment_caspp\nWHERE cds_code = '01611190000000'\n  AND academic_year = '2023-24'\nGROUP BY reporting_category\nORDER BY avg_score DESC;",
    },
    # ── Mixed / cross-grain ────────────────────────────────────────
    {
        "question": "How many economically disadvantaged students had at least one discipline incident in 2023-2024?",
        "sql": "SELECT COUNT(DISTINCT s.student_id_hash) AS student_count\nFROM main_core.dim_students s\nJOIN main_core.fact_discipline d\n  ON s.student_id_hash = d.student_id_hash\n  AND s.academic_year = d.academic_year\nWHERE s.academic_year = '2023-2024'\n  AND s.free_reduced_lunch_flag = TRUE;",
    },
]


def build_few_shot_block(examples: list[dict] = None) -> str:
    """Build the few-shot examples block for prompt injection."""
    if examples is None:
        examples = FEW_SHOT_EXAMPLES
    lines = ["Examples:"]
    for ex in examples:
        lines.append(f"\nQuestion: {ex['question']}")
        lines.append(f"```sql\n{ex['sql']}\n```")
    return "\n".join(lines)


# ── Full prompt assembler ──────────────────────────────────────────────


def build_prompt(
    user_question: str,
    schema: dict = None,
    examples: list[dict] = None,
) -> str:
    """
    Assemble the full prompt for the fine-tuned Qwen2.5 LLM.

    Uses the Qwen2.5 chat template (matching training format):
    <|im_start|>system ... <|im_end|>
    <|im_start|>user Question: ... <|im_end|>
    <|im_start|>assistant

    Schema and few-shot examples are embedded in the system prompt since the
    fine-tuned model was trained with system + question → SQL. ``schema`` is
    normally the live introspection from data_engine.get_schema_info();
    DEFAULT_SCHEMA is only a fallback.
    """
    if schema is None:
        schema = DEFAULT_SCHEMA
    if examples is None:
        examples = FEW_SHOT_EXAMPLES

    system = SYSTEM_PROMPT + "\n\n" + build_schema_context(schema)
    if examples:
        system += "\n\n" + build_few_shot_block(examples)

    prompt = (
        f"<|im_start|>system\n{system}<|im_end|>\n"
        f"<|im_start|>user\nQuestion: {user_question}<|im_end|>\n"
        f"<|im_start|>assistant\n"
    )
    return prompt
