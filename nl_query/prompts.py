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
7. For CDE school accountability metrics (chronic absenteeism, enrollment, suspensions, expulsions, homeless counts, FRPM, SBAC, ELPAC, restraints), use main_analytics.mart_cde_school_accountability.
8. CDE reporting_category codes: TA=All Students, RA=Asian, RB=Black, RH=Hispanic, GM=Male, GF=Female, SED=Socioeconomically Disadvantaged (also SE in legacy CDE extracts), EL=English Learners, SWD=Students with Disabilities, HOM=Homeless, FOS=Foster Youth.
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
        ("academic_year", "VARCHAR", "School year (format 'YYYY-YYYY')"),
        ("school_id", "VARCHAR", "School identifier"),
        ("school_name", "VARCHAR", "School name"),
        ("total_students", "BIGINT", "Number of students"),
        ("student_count", "BIGINT", "Number of students"),
        ("avg_attendance_rate", "DOUBLE", "Average attendance rate"),
        ("avg_gpa", "DOUBLE", "Average GPA"),
        ("pct_high_risk", "DOUBLE", "Percent of students at high risk"),
    ],
    "main_analytics.equity_by_race": [
        ("academic_year", "VARCHAR", "School year (format 'YYYY-YYYY')"),
        ("primary_race", "VARCHAR", "Primary race/ethnicity category"),
        ("is_multi_racial", "BOOLEAN", "TRUE if multi-racial"),
        ("student_count", "BIGINT", "Number of students in group"),
        ("avg_attendance_rate", "DOUBLE", "Average attendance rate"),
        ("avg_gpa", "DOUBLE", "Average GPA"),
        ("incident_count", "BIGINT", "Total discipline incidents"),
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


# ── Gap-filler few-shot examples (20 prompts, Categories A-G) ──────────
#
# These cover query patterns the original 15 few-shots miss:
#   A. Multi-table joins (core ↔ core)
#   B. Trend / year-over-year
#   C. CASE WHEN / risk banding
#   D. OBT advanced patterns (suppression, multi-indicator, county, restraint)
#   E. Window functions / ranking
#   F. Analytics marts (underused)
#   G. Edge cases (ambiguous, negative results)
#
# They focus on exploratory questions a principal would ask that aren't
# covered by the pre-computed Rill dashboard widgets, cross-domain joins
# the CDE flat files can't answer, and student-level queries (the OBT is
# school-level only). Gold SQL validated against the live warehouse.

GAP_FEWSHOT_EXAMPLES = [
    # ── Category A: Multi-Table Joins (Core ↔ Core) ──────────────────
    {
        "question": "What's the average attendance rate for students with at least one suspension in 2023-2024?",
        "sql": "SELECT ROUND(AVG(a.attendance_rate), 4) AS avg_attendance_rate\nFROM main_core.fact_attendance a\nWHERE a.academic_year = '2023-2024'\n  AND a.student_id_hash IN (\n    SELECT DISTINCT student_id_hash\n    FROM main_core.fact_discipline\n    WHERE academic_year = '2023-2024'\n      AND suspension_days > 0\n  );",
    },
    {
        "question": "What is the average GPA by race/ethnicity in 2023-2024?",
        "sql": "SELECT s.primary_race, ROUND(AVG(ar.gpa_points), 2) AS avg_gpa\nFROM main_core.fact_academic_records ar\nJOIN main_core.dim_students s\n  ON ar.student_id_hash = s.student_id_hash\n  AND ar.school_year = s.academic_year\nWHERE ar.school_year = '2023-2024'\nGROUP BY s.primary_race\nORDER BY avg_gpa DESC;",
    },
    {
        "question": "For English Learners, what's the relationship between attendance rate and GPA in 2023-2024?",
        "sql": "SELECT\n  ROUND(AVG(a.attendance_rate), 4) AS avg_attendance_rate,\n  ROUND(AVG(ar.gpa_points), 2) AS avg_gpa\nFROM main_core.fact_attendance a\nJOIN main_core.dim_students s\n  ON a.student_id_hash = s.student_id_hash\n  AND a.academic_year = s.academic_year\nJOIN main_core.fact_academic_records ar\n  ON a.student_id_hash = ar.student_id_hash\n  AND a.academic_year = ar.school_year\nWHERE a.academic_year = '2023-2024'\n  AND s.ell_status = TRUE;",
    },
    {
        "question": "What is the average GPA for students with 3 or more discipline incidents in 2023-2024?",
        "sql": "SELECT ROUND(AVG(ar.gpa_points), 2) AS avg_gpa\nFROM main_core.fact_academic_records ar\nWHERE ar.school_year = '2023-2024'\n  AND ar.student_id_hash IN (\n    SELECT student_id_hash\n    FROM main_core.fact_discipline\n    WHERE academic_year = '2023-2024'\n    GROUP BY student_id_hash\n    HAVING COUNT(*) >= 3\n  );",
    },
    # ── Category B: Trend / Year-over-Year ───────────────────────────
    {
        "question": "How has chronic absenteeism changed from 2021-22 to 2023-24?",
        "sql": "SELECT academic_year,\n       ROUND(AVG(ca_chronic_absent_rate_pct), 2) AS avg_chronic_absent_rate\nFROM main_analytics.mart_cde_school_accountability\nWHERE reporting_category = 'TA'\n  AND academic_year IN ('2021-22', '2022-23', '2023-24')\nGROUP BY academic_year\nORDER BY academic_year;",
    },
    {
        "question": "Show enrollment for each school across the last 3 years",
        "sql": "SELECT school_name, academic_year, SUM(en_cumulative_enrollment) AS total_enrollment\nFROM main_analytics.mart_cde_school_accountability\nWHERE aggregate_level = 'S'\n  AND reporting_category = 'TA'\n  AND academic_year IN ('2022-23', '2023-24', '2024-25')\nGROUP BY school_name, academic_year\nORDER BY school_name, academic_year;",
    },
    {
        "question": "Has average GPA improved from 2022-2023 to 2023-2024?",
        "sql": "SELECT school_year, ROUND(AVG(gpa_points), 2) AS avg_gpa\nFROM main_core.fact_academic_records\nWHERE school_year IN ('2022-2023', '2023-2024')\nGROUP BY school_year\nORDER BY school_year;",
    },
    # ── Category C: CASE WHEN / Risk Banding ──────────────────────────
    {
        "question": "Categorize students by attendance rate: 'Severe' (<80%), 'At Risk' (80-90%), 'Satisfactory' (>90%) for 2023-2024",
        "sql": "SELECT\n  CASE\n    WHEN attendance_rate < 0.80 THEN 'Severe'\n    WHEN attendance_rate <= 0.90 THEN 'At Risk'\n    ELSE 'Satisfactory'\n  END AS attendance_band,\n  COUNT(DISTINCT student_id_hash) AS student_count\nFROM main_core.fact_attendance\nWHERE academic_year = '2023-2024'\nGROUP BY attendance_band\nORDER BY student_count DESC;",
    },
    {
        "question": "Group students by GPA: 'Honor Roll' (3.5+), 'On Track' (2.0-3.4), 'Below' (<2.0) for 2023-2024",
        "sql": "SELECT\n  CASE\n    WHEN gpa_points >= 3.5 THEN 'Honor Roll'\n    WHEN gpa_points >= 2.0 THEN 'On Track'\n    ELSE 'Below'\n  END AS performance_tier,\n  COUNT(DISTINCT student_id_hash) AS student_count\nFROM main_core.fact_academic_records\nWHERE school_year = '2023-2024'\nGROUP BY performance_tier\nORDER BY student_count DESC;",
    },
    {
        "question": "Which students are both chronically absent AND failing (GPA below 2.0) in 2023-2024?",
        "sql": "SELECT COUNT(DISTINCT a.student_id_hash) AS combined_risk_count\nFROM main_core.fact_attendance a\nJOIN main_core.fact_academic_records ar\n  ON a.student_id_hash = ar.student_id_hash\n  AND a.academic_year = ar.school_year\nWHERE a.academic_year = '2023-2024'\n  AND a.absence_rate >= 0.10\n  AND ar.gpa_points < 2.0;",
    },
    # ── Category D: OBT Advanced Patterns ───────────────────────────
    {
        "question": "Show chronic absenteeism rates, excluding suppressed data, for 2023-24",
        "sql": "SELECT school_name, ca_chronic_absent_rate_pct\nFROM main_analytics.mart_cde_school_accountability\nWHERE academic_year = '2023-24'\n  AND reporting_category = 'TA'\n  AND is_suppressed = FALSE\n  AND ca_chronic_absent_rate_pct IS NOT NULL\nORDER BY ca_chronic_absent_rate_pct DESC\nLIMIT 20;",
    },
    {
        "question": "For All Students: chronic absent rate, suspension rate, and SBAC proficiency in one query for 2023-24",
        "sql": "SELECT school_name,\n       ca_chronic_absent_rate_pct,\n       su_suspension_rate_pct,\n       sbac_pct_standard_met_above\nFROM main_analytics.mart_cde_school_accountability\nWHERE academic_year = '2023-24'\n  AND reporting_category = 'TA'\n  AND aggregate_level = 'S'\nORDER BY school_name;",
    },
    {
        "question": "What is the average chronic absenteeism by county for 2023-24?",
        "sql": "SELECT county_name, ROUND(AVG(ca_chronic_absent_rate_pct), 2) AS avg_chronic_absent_rate\nFROM main_analytics.mart_cde_school_accountability\nWHERE academic_year = '2023-24'\n  AND reporting_category = 'TA'\n  AND aggregate_level = 'S'\n  AND ca_chronic_absent_rate_pct IS NOT NULL\nGROUP BY county_name\nORDER BY avg_chronic_absent_rate DESC;",
    },
    {
        "question": "Which schools reported physical restraints in 2023-24?",
        "sql": "SELECT DISTINCT school_name, county_name\nFROM main_analytics.mart_cde_school_accountability\nWHERE academic_year = '2023-24'\n  AND aggregate_level = 'S'\n  AND rs_physical_restraints > 0\nORDER BY school_name;",
    },
    # ── Category E: Window Functions / Ranking ───────────────────────
    {
        "question": "Top 3 schools with highest chronic absenteeism in each county for 2023-24",
        "sql": "WITH ranked AS (\n  SELECT county_name, school_name, ca_chronic_absent_rate_pct,\n    ROW_NUMBER() OVER (PARTITION BY county_name ORDER BY ca_chronic_absent_rate_pct DESC) AS rn\n  FROM main_analytics.mart_cde_school_accountability\n  WHERE academic_year = '2023-24'\n    AND reporting_category = 'TA'\n    AND aggregate_level = 'S'\n    AND ca_chronic_absent_rate_pct IS NOT NULL\n)\nSELECT county_name, school_name, ca_chronic_absent_rate_pct\nFROM ranked\nWHERE rn <= 3\nORDER BY county_name, rn;",
    },
    {
        "question": "What attendance rate puts a student in the bottom quartile in 2023-2024?",
        "sql": "SELECT QUANTILE_CONT(attendance_rate, 0.25) AS bottom_quartile_attendance\nFROM main_core.fact_attendance\nWHERE academic_year = '2023-2024';",
    },
    # ── Category F: Analytics Marts (Underused) ──────────────────────
    {
        "question": "Which schools have the highest percentage of high-risk students?",
        "sql": "SELECT school_id, pct_high_risk\nFROM main_analytics.school_summary\nWHERE pct_high_risk IS NOT NULL\nORDER BY pct_high_risk DESC\nLIMIT 10;",
    },
    {
        "question": "Show the suspension rate gap between Black and White students",
        "sql": "SELECT\n  MAX(CASE WHEN primary_race = 'Black' THEN pct_suspended END) AS black_suspension_rate,\n  MAX(CASE WHEN primary_race = 'White' THEN pct_suspended END) AS white_suspension_rate,\n  MAX(CASE WHEN primary_race = 'Black' THEN pct_suspended END)\n    - MAX(CASE WHEN primary_race = 'White' THEN pct_suspended END) AS suspension_gap\nFROM main_analytics.equity_by_race\nWHERE primary_race IN ('Black', 'White');",
    },
    # ── Category G: Edge Cases ───────────────────────────────────────
    {
        "question": "How are our students doing?",
        "sql": "SELECT COUNT(DISTINCT a.student_id_hash) AS total_students,\n       ROUND(AVG(a.attendance_rate), 4) AS avg_attendance_rate,\n       ROUND(AVG(ar.gpa_points), 2) AS avg_gpa\nFROM main_core.fact_attendance a\nLEFT JOIN main_core.fact_academic_records ar\n  ON a.student_id_hash = ar.student_id_hash\n  AND a.academic_year = ar.school_year\nWHERE a.academic_year = '2023-2024';",
    },
    {
        "question": "Which schools had zero suspensions in 2023-24?",
        "sql": "SELECT school_name\nFROM main_analytics.mart_cde_school_accountability\nWHERE academic_year = '2023-24'\n  AND reporting_category = 'TA'\n  AND aggregate_level = 'S'\n  AND COALESCE(su_total_suspensions, 0) = 0\nORDER BY school_name;",
    },
]


def get_all_few_shot_examples() -> list[dict]:
    """Return the combined base + gap-filler few-shot examples."""
    return FEW_SHOT_EXAMPLES + GAP_FEWSHOT_EXAMPLES


def select_relevant_few_shots(
    user_question: str,
    examples: list[dict] | None = None,
    k: int = 4,
) -> list[dict]:
    """Select the top-k most relevant few-shot examples by token overlap."""
    import re

    pool = examples if examples is not None else get_all_few_shot_examples()
    if len(pool) <= k:
        return list(pool)

    q_tokens = {
        tok for tok in re.findall(r"[a-z0-9_]+", (user_question or "").lower()) if len(tok) > 2
    }
    scored: list[tuple[int, int, dict]] = []
    for idx, ex in enumerate(pool):
        ex_tokens = set(
            re.findall(
                r"[a-z0-9_]+",
                f"{ex.get('question', '')} {ex.get('sql', '')}".lower(),
            )
        )
        overlap = len(q_tokens & ex_tokens)
        scored.append((-overlap, idx, ex))

    scored.sort(key=lambda item: (item[0], item[1]))
    return [item[2] for item in scored[:k]]


def prune_schema_for_prompt(
    user_question: str,
    schema: dict,
    k: int = 6,
) -> dict:
    """Prune schema to top-k relevant tables using select_top_k_tables."""
    import sys
    from pathlib import Path

    if not schema or len(schema) <= k:
        return schema

    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    try:
        from training.schema_pruner import select_top_k_tables

        normalized: dict[str, list[dict[str, str]]] = {}
        for tbl_name, cols in schema.items():
            norm_cols: list[dict[str, str]] = []
            for c in cols:
                if isinstance(c, dict):
                    norm_cols.append(c)
                else:
                    norm_cols.append(
                        {
                            "name": str(c[0]),
                            "type": str(c[1]) if len(c) > 1 else "VARCHAR",
                            "description": str(c[2]) if len(c) > 2 else "",
                        }
                    )
            normalized[tbl_name] = norm_cols

        selected = select_top_k_tables(user_question, normalized, k=k)
        return {tbl: schema[tbl] for tbl in selected if tbl in schema}
    except Exception:
        return dict(list(schema.items())[:k])


def build_few_shot_block(examples: list[dict] = None) -> str:
    """Build the few-shot examples block for prompt injection.

    Defaults to the combined base + gap-filler set (35 examples).
    """
    if examples is None:
        examples = get_all_few_shot_examples()
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
    pruned_schema = prune_schema_for_prompt(user_question, schema, k=6)
    if examples is None:
        examples = select_relevant_few_shots(user_question, k=4)

    system = SYSTEM_PROMPT + "\n\n" + build_schema_context(pruned_schema)
    if examples:
        system += "\n\n" + build_few_shot_block(examples)

    prompt = (
        f"<|im_start|>system\n{system}<|im_end|>\n"
        f"<|im_start|>user\nQuestion: {user_question}<|im_end|>\n"
        f"<|im_start|>assistant\n"
    )
    return prompt


# ── Two-Hop Protocol ChatML Prompt Builders (Milestone 4) ──────────────

TWO_HOP_SYSTEM_PROMPT = """You are a sovereign local-first analytical SQL and Generative UI agent.
Operate in a strict Two-Hop Tool-Calling Protocol:
1. Hop 1: Emit a JSON tool call to `execute_duckdb_query` with `explanation` and a valid read-only DuckDB `sql` query (`SELECT` or `WITH`).
2. Hop 1b (if `duckdb_execution_error` is returned): Read the `Candidate bindings` hint carefully and emit a corrected `execute_duckdb_query` tool call.
3. Hop 2 (after `duckdb_result_summary` is returned): Emit a JSON tool call to `render_workspace_ui` selecting 1 to 4 canonical components (`KPIGrid`, `TimeSeriesChart`, `CategoryBarChart`, `BudgetVarianceChart`, `DataTable`, `FilterBar`) bound strictly to the returned column names."""


def build_two_hop_prompt(user_question: str, pruned_ddl: str) -> str:
    """Assemble the initial ChatML prefix for Hop 1 with Top-K pruned DDL (<800 tokens)."""
    system_block = f"{TWO_HOP_SYSTEM_PROMPT}\n\n{pruned_ddl}"
    return (
        f"<|im_start|>system\n{system_block}<|im_end|>\n"
        f"<|im_start|>user\n{user_question}<|im_end|>\n"
        f"<|im_start|>assistant\n"
    )


def append_tool_turn(active_prompt: str, assistant_output: str, tool_payload: dict) -> str:
    """Append an assistant completion and `<|im_start|>tool` response onto the ChatML buffer."""
    import json

    tool_json = json.dumps(tool_payload, separators=(",", ":"))
    return (
        f"{active_prompt}{assistant_output.strip()}<|im_end|>\n"
        f"<|im_start|>tool\n{tool_json}<|im_end|>\n"
        f"<|im_start|>assistant\n"
    )
