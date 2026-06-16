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
5. Join on the columns that logically connect the tables — student-grain tables join on student_id_hash; school-grain tables join on school_id.
6. Student identity is pseudonymized: there is no name column, only student_id_hash.
7. If the question is ambiguous, make a reasonable assumption and generate the query.
8. Do NOT include any explanation outside the ```sql ``` block."""


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
    {
        "question": "How many students were enrolled in 2023-2024?",
        "sql": "SELECT COUNT(DISTINCT student_id_hash) AS student_count\nFROM main_core.dim_students\nWHERE academic_year = '2023-2024';",
    },
    {
        "question": "What is the average attendance rate by school in 2023-2024?",
        "sql": "SELECT school_id, ROUND(AVG(attendance_rate), 4) AS avg_attendance_rate\nFROM main_core.fact_attendance\nWHERE academic_year = '2023-2024'\nGROUP BY school_id\nORDER BY avg_attendance_rate;",
    },
    {
        "question": "How many suspensions happened by incident type in 2023-2024?",
        "sql": "SELECT incident_type, COUNT(*) AS incident_count, SUM(suspension_days) AS total_suspension_days\nFROM main_core.fact_discipline\nWHERE academic_year = '2023-2024'\nGROUP BY incident_type\nORDER BY incident_count DESC;",
    },
    {
        "question": "Compare average GPA and attendance across race groups.",
        "sql": "SELECT primary_race, student_count, ROUND(avg_gpa, 2) AS avg_gpa, ROUND(avg_attendance_rate, 4) AS avg_attendance_rate\nFROM main_analytics.equity_by_race\nORDER BY student_count DESC;",
    },
    {
        "question": "What is the average attendance rate for English Learners in 2023-2024?",
        "sql": "SELECT ROUND(AVG(a.attendance_rate), 4) AS avg_attendance_rate\nFROM main_core.fact_attendance a\nJOIN main_core.dim_students s\n  ON a.student_id_hash = s.student_id_hash\n  AND a.academic_year = s.academic_year\nWHERE a.academic_year = '2023-2024'\n  AND s.ell_status = TRUE;",
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
