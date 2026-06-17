"""
ui_strings.py — All user-facing copy for the Query tab.

Kept in one place so wording can be iterated on without touching app.py.

Adapted for local-data-stack: starter questions target the unified warehouse
(core student-grain + analytics rollups) rather than the original flat seed
schema, and avoid fabricated school names.
"""

from __future__ import annotations

# ── Header ─────────────────────────────────────────────────────────────

APP_TITLE = "Ask your district a question."

APP_TAGLINE = (
    "Ask a question in plain English about attendance, discipline, equity, or "
    "academic outcomes. We'll write the query and bring you the answer."
)

# ── Domain sections (starter questions) ────────────────────────────────
# Each section is a label and 2-3 natural-language questions phrased the way
# a non-technical administrator would actually ask. Questions target the
# warehouse schema (core + analytics layers).

DOMAIN_SECTIONS: list[dict] = [
    {
        "title": "Attendance & chronic absence",
        "questions": [
            "What is the average attendance rate by school?",
            "How many students had an absence rate above 10 percent?",
            "Which school has the lowest average attendance rate?",
        ],
    },
    {
        "title": "Discipline incidents",
        "questions": [
            "How many discipline incidents happened by incident type?",
            "What are the total suspension days by school?",
            "Which incident types lead to the most suspensions?",
        ],
    },
    {
        "title": "Equity & academic outcomes",
        "questions": [
            "Compare average GPA and attendance across race groups.",
            "What is the average attendance rate for English Learners?",
            "Show the percent suspended by race group.",
        ],
    },
]


# ── Input helpers ──────────────────────────────────────────────────────

INPUT_HELPER = (
    "You can ask about: schools, school years (like 2023-2024), grade levels, "
    "students, attendance, discipline incidents, equity, and academic outcomes."
)

INPUT_PROMPT_EMPTY = "Type a question above, or pick one from the suggestions to get started."

FIRST_VISIT_NUDGE = (
    '<a href="javascript:openAboutModal()" class="first-visit-link">'
    "First time here?"
    "</a>"
    " Type a question in plain English, or click any of the "
    "suggestions above to see how it works."
)

# ── About / FAQ modal content (HTML) ─────────────────────────────────
ABOUT_MODAL_TITLE = "About Local First Education Data Framework"

ABOUT_MODAL_INTRO = (
    "Local First Education Data Framework (LFED) is a local-first education data "
    "assistant. It lets school admins ask plain-English questions about district "
    "data and get answers instantly — without sending anything to the cloud."
)

ABOUT_MODAL_HOW_IT_WORKS = (
    "You type a question like <em>“What’s the average attendance rate by school "
    "in 2023-2024?”</em> A language model running on this machine turns it into a "
    "read-only SQL query, runs it against the local DuckDB warehouse, and returns "
    "the result as a sentence and a table."
)

ABOUT_MODAL_PRIVACY = (
    "Everything stays on this machine. Your questions, the generated query, and "
    "the results are not sent anywhere, stored, or logged. Student identity is "
    "pseudonymized in the warehouse — there are no names, only hashed IDs."
)

ABOUT_MODAL_WHAT_IT_IS_BULLETS = [
    "Ask attendance, discipline, equity, enrollment, and academic questions in plain English.",
    "Get a plain-English summary plus a sortable table of results.",
    "Inspect the generated SQL with <strong>Show me how this was computed</strong>.",
    "Download any result table to CSV.",
    "Run entirely on your own hardware — no API keys or internet required (local build).",
]

ABOUT_MODAL_WHAT_IT_ISNT_BULLETS = [
    "It does not change any data — all queries are read-only.",
    "It is not a replacement for your student information system; it is a question-answering layer on top.",
    "It does not know individual students by name — only by pseudonymized ID.",
    "It does not store questions between sessions.",
]

ABOUT_MODAL_FAQ = [
    {
        "q": "What data can I ask about?",
        "a": "The local DuckDB warehouse built by the dlt → dbt pipeline: a student-grain core layer (students, attendance, discipline, enrollment, academic records) and analytics rollups (school summaries, equity by race, risk scores). You can ask about schools, school years, grade levels, demographics, absences, incidents, equity, and academic performance.",
    },
    {
        "q": "Why do I sometimes need to name a school or year?",
        "a": "The model is fine-tuned on school-data questions, but it still needs enough context to write a safe, correct query. Naming a school and school year usually produces the most reliable results.",
    },
    {
        "q": "What model is running?",
        "a": "A fine-tuned Qwen2.5-Coder-14B (QLoRA adapter on a bnb-4-bit base) via Transformers on GPU, or the same fine-tune as a GGUF in llama.cpp for fully local use.",
    },
    {
        "q": "Can I trust the SQL it writes?",
        "a": "Every generated query is validated: it must be SELECT-only, reference known tables and columns, and avoid forbidden tokens. The warehouse is opened read-only, so queries cannot change data. If validation fails, you get a clear message instead of a result.",
    },
    {
        "q": "Can I use my own real school data?",
        "a": "Yes — point the pipeline at your own SIS (e.g. Aeries) data and the warehouse is rebuilt with the same read-only guardrails. Student identity is pseudonymized during transformation.",
    },
]

ABOUT_MODAL_CLOSE = "Close"

ABOUT_MODAL_HINT = (
    "Tip: If the model misinterprets a question, rephrase it and include a "
    "specific school and school year."
)


# ── Summary templates ──────────────────────────────────────────────────
# Plain-English one-liners used as the headline above the result table.

SUMMARY_TEMPLATES = {
    "single_value": "The answer is **{value}**.",
    "single_pair": "**{label}**: {value}.",
    "by_school": "Here's the breakdown across {n} schools.",
    "generic": "Here are the {n} rows that match.",
}


# ── Error rephrasings ──────────────────────────────────────────────────
# Map substrings of raw error messages → user-friendly message.
# Order matters: more specific markers first.

ERROR_REPHRASINGS: dict[str, str] = {
    "validation": (
        "I couldn't turn that question into a query I trust. "
        "Try rephrasing it more simply — for example, name a school and a school year."
    ),
    "forbidden": (
        "That question would ask for something I don't allow (like changing data). "
        "This tool is read-only, so try asking a question instead."
    ),
    "timeout": (
        "That took too long to look up. "
        "Try narrowing your question to a specific school or school year."
    ),
    "model": (
        "I'm having trouble understanding that question. "
        "Try rephrasing it the way you'd say it out loud."
    ),
    "missing from clause": (
        "I couldn't figure out where to look. "
        "Try naming what you want to see and which school or year."
    ),
}


# ── Result UI copy ─────────────────────────────────────────────────────

SQL_DISCLOSURE_LABEL = "Show me how this was computed"

PREVIOUS_RIBBON_TEMPLATE = "Your previous answer: {summary}"


# ── Footer + explainer ─────────────────────────────────────────────────

WHAT_THIS_IS_ONE_LINER = (
    "A way to ask questions about your district's data in plain English, "
    "that runs on your own machine."
)

WHAT_THIS_IS_NOT_ONE_LINER = (
    "It's not connected to the internet, it doesn't store your questions "
    "between sessions, and it isn't a replacement for your student information system."
)

# Bulleted lists revealed by the 'Read the full explainer' footer button
WHAT_THIS_IS = [
    "A way to ask questions about your district's data in plain English.",
    "A read-only tool — it answers questions, it doesn't change anything.",
    "Something you can run on a single school computer, no internet required.",
    "A model that's been fine-tuned on common school-data questions.",
]

WHAT_THIS_IS_NOT = [
    "It does not connect to the internet or send data anywhere.",
    "It does not store your questions between sessions.",
    "It does not replace your student information system — it's a layer on top.",
    "It does not know about individual students by name, only by pseudonymized ID.",
]

HOW_IT_WORKS = (
    "You ask a question in plain English. A language model (running on this "
    "machine) translates your question into a database query, and the local "
    "DuckDB warehouse runs it. You see the answer as a sentence and a table. "
    "If you want to see exactly what was looked up, click "
    "\u201cShow me how this was computed\u201d under any result."
)

PRIVACY_EXPLAINER = (
    "Everything happens on the machine you're using right now. Your questions, "
    "the generated query, and the results never leave this network. No accounts, "
    "no analytics, no telemetry. When you close this page, the conversation is "
    "gone."
)
