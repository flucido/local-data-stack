"""
generate_pairs.py — Generate NL→SQL training pairs against the real warehouse.

Uses a strong LLM (via API) to generate diverse natural language questions and
corresponding DuckDB SQL queries against the curated warehouse schema. Every
generated SQL is validated by executing it against the real DuckDB warehouse.

Usage:
    python training/generate_pairs.py --n 5000 --output training/pairs.jsonl
    python training/generate_pairs.py --n 100 --output training/pairs.jsonl --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

import duckdb

# ── Paths ───────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WAREHOUSE_PATH = PROJECT_ROOT / "oss_framework" / "data" / "analytics.duckdb"
SCHEMA_PATH = Path(__file__).resolve().parent / "training_schema.json"
SEED_EXAMPLES_PATH = PROJECT_ROOT / "nl_query" / "prompts.py"

# ── Load curated schema ─────────────────────────────────────────────────


def load_schema() -> dict:
    with open(SCHEMA_PATH) as f:
        return json.load(f)


def build_schema_prompt(schema: dict) -> str:
    """Format the curated schema as a compact prompt-friendly string."""
    parts = ["AVAILABLE TABLES AND COLUMNS:\n"]
    for idx, (table, cols) in enumerate(schema["tables"].items(), 1):
        col_strs = [f"{c['name']} ({c['type']})" for c in cols]
        parts.append(f"{idx}. {table} :: {', '.join(col_strs)}")
    return "\n".join(parts)


# ── Seed examples (from prompts.py, real warehouse queries) ────────────

SEED_EXAMPLES = [
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
        "question": "What is the chronic absenteeism rate for Hispanic students across all schools in 2023-24?",
        "sql": "SELECT cds_code, school_name, ca_chronic_absent_rate_pct\nFROM main_analytics.mart_cde_school_accountability\nWHERE academic_year = '2023-24'\n  AND reporting_category = 'RH'\n  AND ca_chronic_absent_rate_pct IS NOT NULL\nORDER BY ca_chronic_absent_rate_pct DESC;",
    },
    {
        "question": "Compare suspension rates and chronic absenteeism rates by race group for 2023-24.",
        "sql": "SELECT reporting_category_label,\n  ROUND(AVG(su_suspension_rate_pct), 2) AS avg_suspension_rate,\n  ROUND(AVG(ca_chronic_absent_rate_pct), 2) AS avg_chronic_absent_rate\nFROM main_analytics.mart_cde_school_accountability\nWHERE academic_year = '2023-24'\n  AND reporting_category IN ('RA','RB','RH','TA')\nGROUP BY reporting_category_label\nORDER BY avg_suspension_rate DESC;",
    },
    {
        "question": "Which schools have the highest free meal eligibility in 2023-24?",
        "sql": "SELECT school_name, district_name, frpm_free_pct_k12\nFROM main_analytics.mart_cde_school_accountability\nWHERE academic_year = '2023-24'\n  AND reporting_category = 'TA'\n  AND frpm_free_pct_k12 IS NOT NULL\nORDER BY frpm_free_pct_k12 DESC\nLIMIT 20;",
    },
    {
        "question": "How many homeless students are in each district in 2023-24?",
        "sql": "SELECT district_name, SUM(homeless_student_enrollment) AS total_homeless\nFROM main_staging.stg_cde__homeless_enrollment\nWHERE academic_year = '2023-24'\n  AND aggregate_level = 'D'\n  AND reporting_category = 'TA'\n  AND homeless_student_enrollment IS NOT NULL\nGROUP BY district_name\nORDER BY total_homeless DESC;",
    },
    {
        "question": "What is the average attendance rate for English Learners in 2023-2024?",
        "sql": "SELECT ROUND(AVG(a.attendance_rate), 4) AS avg_attendance_rate\nFROM main_core.fact_attendance a\nJOIN main_core.dim_students s\n  ON a.student_id_hash = s.student_id_hash\n  AND a.academic_year = s.academic_year\nWHERE a.academic_year = '2023-2024'\n  AND s.ell_status = TRUE;",
    },
]


def build_seed_block() -> str:
    lines = ["EXAMPLES OF VALID QUESTION→SQL PAIRS:"]
    for ex in SEED_EXAMPLES:
        lines.append(f"\nQuestion: {ex['question']}")
        lines.append(f"```sql\n{ex['sql']}\n```")
    return "\n".join(lines)


# ── Generation prompt ───────────────────────────────────────────────────

GENERATION_INSTRUCTIONS = """You are an expert education data analyst who writes DuckDB SQL queries.

Your task: generate {batch_size} diverse, realistic natural-language questions about school
district data, each paired with a correct DuckDB SQL query.

RULES:
1. Questions must sound like real questions from school administrators, board members,
   or data analysts. Vary the phrasing, formality, and specificity.
2. Each SQL query MUST be valid DuckDB SQL that executes against the schema above.
3. Use fully-qualified table names (e.g. main_core.dim_students, not just dim_students).
4. Cover all three query paths:
   - Student-level joins across main_core tables (use student_id_hash for joins)
   - OBT path: single-table queries on main_analytics.mart_cde_school_accountability
   - Staging path: direct queries on main_staging.stg_cde__* tables
5. For CDE data, always filter by reporting_category where relevant. Common codes:
   TA=All Students, RA=Asian, RB=Black, RH=Hispanic, SE=Socioeconomically Disadvantaged,
   EL=English Learners, SWD=Students with Disabilities, HOM=Homeless, FOS=Foster Youth.
6. For CDE data, the academic_year format is 'YYYY-YY' (e.g. '2023-24').
   For Aeries data, the academic_year format is 'YYYY-YYYY' (e.g. '2023-2024').
7. Questions should be diverse: different schools, years, subgroups, metrics, comparison types.
8. Include aggregations (COUNT, AVG, SUM), filtering (WHERE), grouping (GROUP BY),
   ordering (ORDER BY), limiting (LIMIT), and joins where appropriate.
9. Every SQL MUST be a SELECT statement only — no INSERT, UPDATE, DELETE, DROP.
10. Output each pair as a JSON object on its own line:
    {{"question": "...", "sql": "..."}}

Generate exactly {batch_size} pairs. Output ONLY the JSON lines, nothing else."""


def build_generation_prompt(batch_size: int = 20) -> str:
    schema = load_schema()
    schema_text = build_schema_prompt(schema)
    seed_text = build_seed_block()
    instructions = GENERATION_INSTRUCTIONS.format(batch_size=batch_size)
    return schema_text + "\n" + seed_text + "\n\n" + instructions


# ── SQL validation ──────────────────────────────────────────────────────

FORBIDDEN_TOKENS = [
    "drop",
    "delete",
    "insert",
    "update",
    "alter",
    "truncate",
    "create",
    "attach",
    "detach",
    "pragma",
]


def validate_sql(sql: str, conn: duckdb.DuckDBPyConnection) -> tuple[bool, str]:
    """Execute SQL against the warehouse. Returns (is_valid, error_or_rows)."""
    sql_clean = sql.strip().rstrip(";")

    # Forbidden token check
    sql_lower = sql_clean.lower()
    for token in FORBIDDEN_TOKENS:
        if re.search(rf"\b{token}\b", sql_lower):
            return False, f"Forbidden token: {token}"

    if "SELECT" not in sql_clean.upper():
        return False, "Not a SELECT statement"

    # Check it references known tables
    known = set(load_schema()["tables"].keys())
    short_names = {k.split(".")[-1] for k in known}
    if not any(t in sql_lower for t in known) and not any(t in sql_lower for t in short_names):
        return False, "No known tables referenced"

    # Execute
    try:
        safe_sql = f"SELECT * FROM (\n{sql_clean}\n) AS _validate LIMIT 10"
        result = conn.execute(safe_sql).fetchall()
        if result and len(result) > 0:
            return True, f"{len(result)} rows returned"
        else:
            return True, "0 rows (valid SQL, empty result)"
    except Exception as e:
        return False, str(e)[:200]


# ── Pair generation ─────────────────────────────────────────────────────


def parse_pairs(text: str) -> list[dict]:
    """Extract {question, sql} pairs from LLM output (JSON lines or markdown)."""
    pairs = []
    # Try JSON lines
    for line in text.strip().split("\n"):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                obj = json.loads(line)
                if "question" in obj and "sql" in obj:
                    pairs.append(obj)
            except json.JSONDecodeError:
                pass

    if not pairs:
        # Fallback: try to find JSON blocks
        json_match = re.findall(r'\{[^{}]*"question"[^{}]*\}', text, re.DOTALL)
        for m in json_match:
            try:
                obj = json.loads(m)
                if "question" in obj and "sql" in obj:
                    pairs.append(obj)
            except json.JSONDecodeError:
                pass

    return pairs


def generate_batch(
    llm_callable,
    batch_size: int = 20,
    conn: duckdb.DuckDBPyConnection = None,
    max_retries: int = 2,
) -> list[dict]:
    """Generate one batch of NL→SQL pairs and validate them."""
    prompt = build_generation_prompt(batch_size)

    for attempt in range(max_retries + 1):
        try:
            response = llm_callable(prompt)
        except Exception as e:
            print(f"  LLM call failed (attempt {attempt+1}): {e}")
            time.sleep(5)
            continue

        pairs = parse_pairs(response)
        if pairs:
            break
        print(f"  Parse failed (attempt {attempt+1}), retrying...")
        time.sleep(2)
    else:
        return []

    valid_pairs = []
    for pair in pairs:
        is_valid, msg = validate_sql(pair["sql"], conn)
        if is_valid:
            valid_pairs.append(pair)
        else:
            pass  # silently skip invalid

    return valid_pairs


# ── Main ────────────────────────────────────────────────────────────────


def run_generation(
    n_pairs: int = 5000,
    output_path: str = "training/pairs.jsonl",
    batch_size: int = 20,
    dry_run: bool = False,
) -> None:
    """Generate validated NL→SQL training pairs."""
    schema = load_schema()
    print(
        f"📋 Schema: {len(schema['tables'])} tables, {sum(len(v) for v in schema['tables'].values())} columns"
    )
    print(f"🎯 Target: {n_pairs} pairs, batch size: {batch_size}")
    print(f"🗄️  Warehouse: {WAREHOUSE_PATH}")

    if dry_run:
        prompt = build_generation_prompt(batch_size)
        print(f"\n{'='*60}")
        print("DRY RUN — Generation prompt preview:")
        print(f"{'='*60}")
        print(prompt[:3000])
        print(f"\n... ({len(prompt)} chars total)")
        return

    # ── Setup LLM ──────────────────────────────────────────────────
    print("\n🔧 Setting up LLM...")
    try:
        import dspy

        lm = dspy.LM(
            "ollama_chat/SyntacticLuster/DeepSeek-Coder-V2-Lite:latest",
            api_base="http://localhost:11434",
            temperature=0.8,
            max_tokens=2048,
        )
        dspy.settings.configure(lm=lm)

        def llm_call(prompt):
            result = lm(prompt, temperature=0.8, max_tokens=2048)
            if isinstance(result, list):
                return result[0].get("text", "") if result else ""
            return str(result)

        print("   Using local Ollama (DeepSeek-Coder-V2-Lite)")
    except Exception:
        print("   ⚠️  Ollama not available. Using dry-run mode for prompt testing.")
        print("   Set up Ollama or use training/modal_generate.py for Modal.")
        return

    # ── Connect to warehouse ─────────────────────────────────────
    conn = duckdb.connect(str(WAREHOUSE_PATH), read_only=True)

    # ── Generate ─────────────────────────────────────────────────
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    total_valid = 0
    total_attempted = 0
    t_start = time.time()

    with open(output, "w") as f:
        while total_valid < n_pairs:
            batch = generate_batch(llm_call, batch_size=batch_size, conn=conn)
            total_attempted += batch_size

            for pair in batch:
                f.write(json.dumps(pair) + "\n")
                total_valid += 1

            elapsed = time.time() - t_start
            rate = total_valid / elapsed if elapsed > 0 else 0
            print(
                f"  ✅ {total_valid}/{n_pairs} pairs ({total_valid*100/total_attempted:.0f}% valid, {rate:.1f}/s)"
            )

            if total_valid >= n_pairs:
                break

    conn.close()
    elapsed = time.time() - t_start
    print(f"\n⏱️  Done: {total_valid} pairs in {elapsed:.0f}s ({elapsed/60:.1f}m)")
    print(f"📄 Output: {output.resolve()}")


# ── CLI ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate NL→SQL training pairs")
    parser.add_argument("--n", type=int, default=5000, help="Target pairs (default: 5000)")
    parser.add_argument("--output", type=str, default="training/pairs.jsonl", help="Output path")
    parser.add_argument("--batch-size", type=int, default=20, help="Pairs per batch (default: 20)")
    parser.add_argument("--dry-run", action="store_true", help="Print prompt without generating")
    args = parser.parse_args()

    run_generation(
        n_pairs=args.n,
        output_path=args.output,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
    )
