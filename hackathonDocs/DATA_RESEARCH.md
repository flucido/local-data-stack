# Deep Research: Text-to-SQL Training Data for Education Domain

> **Date:** 2026-06-08
> **Goal:** Find existing datasets, proven approaches, and the best path for building a high-quality NL→SQL training set for K-12 school district analytics

---

## Part 1: Existing Datasets That Do This Work

### Tier 1: Large-Scale Text-to-SQL Datasets (General Domain)

These are the big ones. None are education-specific, but they contain transferable patterns.

#### 1. gretelai/synthetic_text_to_sql (HuggingFace)
- **Size:** 106K pairs (100K train / 5.8K test)
- **Domains:** 100 domains including healthcare, government, education-related
- **Complexity:** Basic SQL through window functions, CTEs, multi-joins
- **Format:** Each row has: domain, sql_prompt (NL question), sql_context (CREATE TABLE + INSERT), sql (answer), sql_explanation
- **License:** Apache 2.0
- **Why it matters:** This is THE standard dataset people use to fine-tune text-to-SQL models. Rubrik/Predibase used it to fine-tune Llama-3-8B to outperform GPT-4 on SQL tasks.
- **Relevance:** HIGH — contains the SQL patterns (aggregation, joins, GROUP BY, CASE WHEN, HAVING, window functions) you need. But the schemas are generic, not education-specific.
- **How to use:** Filter for domains closest to education, then combine with your own education-specific pairs.

#### 2. NumbersStation/NSText2SQL (HuggingFace)
- **Size:** 289K pairs
- **Sources:** 26 different public datasets merged (Spider, CoSQL, SparC, WikiSQL, etc.)
- **Format:** instruction (schema + question) → output (SQL)
- **License:** Various (curated from permissive sources)
- **Why it matters:** Largest merged text-to-SQL corpus. Contains course/student/enroll schemas from Spider that are closest to education.
- **Relevance:** MEDIUM — has some education-adjacent schemas (courses, enrollment, professors) but not K-12 specific.

#### 3. OmniSQL / SynSQL-2.5M (HuggingFace + GitHub)
- **Size:** 2.5 MILLION pairs across 16,575 schemas
- **Approach:** LLM generates schemas, then synthesizes NL questions + SQL
- **Paper:** VLDB 2025
- **Why it matters:** First million-scale text-to-SQL dataset. Their synthesis pipeline is open-source — you could adapt it for education schemas.
- **Relevance:** MEDIUM — the pipeline (schema → question → SQL → validation) is exactly what you need to replicate for education.

#### 4. SQaLe (trl-lab/SQaLe-text-to-SQL-dataset)
- **Size:** 517K validated triples from 135,875 schemas
- **Approach:** Start with real schemas from SchemaPile, extend with LLM, generate questions from Spider/BIRD examples, validate via execution
- **Why it matters:** Proves that schema-variety matters more than raw volume. 135K schemas beat datasets with 10x more pairs on fewer schemas.
- **Relevance:** MEDIUM — methodology is spot-on, but no education schemas specifically.

#### 5. Spider + BIRD Benchmarks
- **Spider:** 10K questions, 200 databases, 138 domains. Used as the standard benchmark.
- **BIRD:** 12K questions, 95 databases. Focuses on real-world noisy data.
- **Why they matter:** These define what "good" looks like. Every serious text-to-SQL paper benchmarks against them.
- **Relevance:** LOW for direct use (small, no education focus), but HIGH for understanding what evaluation metrics matter.

### Tier 2: Education-Specific Raw Data (No NL→SQL Pairs)

These have the DATA but not the training pairs. You'd need to generate NL→SQL from them.

#### 6. Kaggle: Student Performance Data Set
- **Source:** UCI ML Repository, 2 Portuguese schools
- **Size:** 649 students, 33 columns
- **Columns:** grades (G1, G2, G3), demographics (sex, age, address), parental education, study time, failures, absences, social factors
- **License:** CC0 Public Domain
- **Relevance:** HIGH — closest to your use case. Grades + demographics + attendance. But it's flat (one table), not normalized like a real SIS.

#### 7. Kaggle: Sample Highschool Database
- **Source:** Student project
- **Size:** 1,000 students
- **Format:** SQL database file
- **Relevance:** MEDIUM — has normalized tables but limited scope.

#### 8. California Department of Education (CDE) Downloadable Data
- **URL:** https://www.cde.ca.gov/ds/ad/downloadabledata.asp
- **Data:** Enrollment, demographics, test scores, graduation rates, discipline, absenteeism, staff, financials — all at school/district/county/state level
- **Format:** CSV files, updated annually
- **License:** Public (CA government data)
- **Relevance:** VERY HIGH — this is REAL data from the exact domain you serve. You could build a realistic seed database from CDE data and generate NL→SQL pairs against it.

#### 9. NCES (National Center for Education Statistics) DataLab
- **URL:** https://nces.ed.gov/datalab/
- **Data:** National education data, PowerStats tool
- **Relevance:** HIGH — federal-level education data, complementary to CDE.

#### 10. Ed-Data.org
- **URL:** https://www.ed-data.org/
- **Data:** CA school/district profiles, financial data, test scores
- **Relevance:** HIGH — partnership of CDE + EdSource, already structured for queries.

---

## Part 2: Proven Approaches for Generating NL→SQL Training Data

### Approach A: Template-Based (What You're Doing Now)

**How it works:** Write SQL templates with placeholders, parameterize with real values, generate NL from templates.

**Pros:**
- 100% accurate SQL (you write it)
- Cheap, fast, deterministic
- Full control over coverage

**Cons:**
- Questions feel synthetic/stilted
- Limited by your imagination
- Hard to scale past ~2K pairs without exhaustion
- Doesn't train for ambiguity, typos, or real-world messiness

**Your current state:** 1,289 pairs from 32 templates. Good start, but ceiling is ~2K.

### Approach B: LLM-Augmented Synthesis (Recommended Next Step)

**How it works:** Use a powerful LLM (GPT-4, Claude, Qwen-72B) to generate NL→SQL pairs from your schema.

**Proven by:**
- OmniSQL (2.5M pairs via LLM synthesis)
- SQaLe (517K pairs via LLM + validation)
- SING-SQL (Bilkent University, 2025) — specifically designed for single-database in-domain training

**The SING-SQL pipeline is the most relevant to your case:**
1. Take your database schema
2. Partition schema into sub-schemas (e.g., attendance-only, grades+demographics, cross-table)
3. For each sub-schema, have LLM generate SQL queries at multiple complexity levels (basic SELECT → aggregation → joins → window functions → CTEs)
4. For each SQL, have LLM generate the NL question
5. Validate: run SQL against real data, check it executes
6. LLM-as-judge: have another LLM verify Q↔SQL match
7. Auto-repair broken queries
8. Balance column coverage (ensure all columns get queried)

**SING-SQL results:** Their 3B model (fine-tuned on synthetic data) hit 82.87% Soft F1 on BIRD — beating prior 3B baselines by +16 points.

**Pros:**
- Scales to 10K-100K+ pairs
- Questions sound natural
- Covers SQL patterns you wouldn't think of
- Validated against real data

**Cons:**
- Needs API credits (or local LLM)
- Some generated SQL will be wrong (need validation)
- May generate SQL for impossible queries

### Approach C: Hybrid (Best for Your Timeline)

Combine templates for known patterns + LLM for natural variation + real data for seed realism.

**Recommended pipeline:**
1. **Foundation:** Your existing 1,289 template pairs (keep these — they're 100% accurate)
2. **Schema expansion:** Add grades, discipline, demographics, assessments, programs tables
3. **Seed with real data:** Download CDE data, build realistic seed database
4. **LLM augmentation:** Use Qwen2.5-72B (free on Modal or via HF Inference) to generate 5,000 new NL→SQL pairs
5. **Rephrasing:** For each of the 6,000+ pairs, generate 3-5 NL phrasings (formal, casual, abbreviated, typo-prone)
6. **Validation:** Run every SQL against seed data, discard failures
7. **Mix with Gretel:** Filter gretelai/synthetic_text_to_sql for relevant domains (government, healthcare, HR) and add 2,000 pairs as general SQL knowledge

**Target:** 15,000-25,000 validated pairs

---

## Part 3: Specific Recommendations for Your Hackathon

### Timeline Reality Check

You have until June 15. That's 7 days. Here's what's realistic:

| Approach | Pairs | Time | Quality | Recommended? |
|---|---|---|---|---|
| Templates only (current) | ~2K | Already done | High accuracy, low diversity | Keep as base |
| + LLM synthesis (local Qwen-72B or Modal) | +5K | 2-3 days | Medium-high | YES — best ROI |
| + Gretel dataset filtered | +2K | 1 day | Medium | YES — free, fast |
| + Rephrasing augmentation | ×3-5 | 1 day | Medium | YES — cheap multiplier |
| + CDE real data seed | N/A | 1 day | N/A | YES — makes everything more realistic |
| Full SING-SQL pipeline | +50K | 2 weeks | High | Too ambitious for hackathon |

### The Playbook (7-Day Plan)

**Day 1-2: Schema + Seed Data**
- Define 6 new tables (grades, discipline, demographics, assessments, programs, staff)
- Download CA Department of Education data files
- Build realistic seed database with 10K+ students
- Update prompts.py with expanded schema

**Day 3: LLM Synthesis**
- Use Qwen2.5-Coder-7B (or GPT-4 if you have credits) to generate NL→SQL pairs
- Prompt: "Given this DuckDB schema [schema], generate a natural language question and its corresponding SQL query. Complexity: [basic/aggregation/join/window]. Focus on: [table_name]."
- Target: 5,000 pairs across all tables

**Day 4: Validation + Filtering**
- Run every generated SQL against the seed database
- Discard any that fail to execute
- Discard any that return 0 rows (unless that's the expected answer)
- Verify column references match schema

**Day 5: Rephrasing + Augmentation**
- For each validated pair, generate 3-5 NL rephrasings
- Add typo variants ("Whats the avg gpa" instead of "What is the average GPA")
- Add informal variants ("How are our kids doing on tests?" for assessment queries)
- Filter Gretel dataset for relevant domains, add 1,500-2,000 pairs

**Day 6: Train v2**
- Update training config: lower LR (1e-4), higher LoRA rank (32), longer seq (4096)
- Train on expanded dataset (~15K-20K pairs)
- Monitor for overfitting

**Day 7: Evaluate + Deploy**
- Test v1 vs v2 on holdout questions
- Deploy to HF Space
- Smoke test with real-world questions

### Quick Wins You Can Do Today

1. **Download Gretel dataset** — it's free, Apache 2.0, and ready to use:
   ```python
   from datasets import load_dataset
   ds = load_dataset("gretelai/synthetic_text_to_sql")
   # Filter for relevant domains
   relevant = ds['train'].filter(lambda x: x['domain'] in [
       'education', 'government', 'public health', 'human resources',
       'insurance', 'social services', 'nonprofit'
   ])
   ```

2. **Download CDE data** — real CA school data:
   https://www.cde.ca.gov/ds/ad/downloadabledata.asp
   Key files: enrollment, absenteeism, demographics, test scores, discipline

3. **Look at OmniSQL's synthesis code** — open source, can adapt for your schema:
   https://github.com/RUCKBReasoning/OmniSQL/tree/main/data_synthesis

---

## Part 4: What the Kaggle Education Datasets Are (and Why They're Different)

You mentioned seeing datasets on Kaggle. Here's what's there and why they're not quite right:

| Dataset | What It Is | Why It's Different |
|---|---|---|
| Student Performance (UCI) | 649 students, flat CSV, Portuguese schools | Raw data, no NL→SQL pairs, foreign schools |
| Student Information | 200 students, 7 attributes | Tiny, toy dataset for SQL practice |
| Student Exam Performance | Demographics + test scores | Flat analysis dataset, not text-to-SQL |
| Sample Highschool Database | SQL file, 1K students | Closer but limited scope, no NL pairs |

**The gap:** Kaggle has education DATA but not education TEXT-TO-SQL TRAINING DATA. Nobody has done the work of turning education data into NL→SQL training pairs at scale. That's your opportunity.

---

## Part 5: The Big Opportunity

Nobody has built a production-quality text-to-SQL model specifically for K-12 school district analytics. This is a real gap:

- **Gretel** covers 100 domains but education is generic
- **Spider/BIRD** have no education schemas
- **OmniSQL/SQaLe** generate across all domains but not deep on education
- **Vanna AI** does RAG-based text-to-SQL but requires you to provide training pairs

If you build this dataset well — with real CA education data, realistic schemas, validated NL→SQL pairs covering enrollment, attendance, grades, discipline, demographics, assessments, programs — you'd have something genuinely valuable beyond the hackathon:

1. **Hackathon submission:** Fine-tuned model that does K-12 analytics
2. **Open-source dataset:** First high-quality education text-to-SQL dataset
3. **Product differentiator:** LTC can offer this to CA school districts
4. **Community contribution:** Publish to HuggingFace, get visibility

---

## Appendix: Key Resources

### Datasets
| Name | URL | Size | License |
|---|---|---|---|
| gretelai/synthetic_text_to_sql | huggingface.co/datasets/gretelai/synthetic_text_to_sql | 106K | Apache 2.0 |
| NumbersStation/NSText2SQL | huggingface.co/datasets/NumbersStation/NSText2SQL | 289K | Various |
| OmniSQL/SynSQL-2.5M | github.com/RUCKBReasoning/OmniSQL | 2.5M | Check repo |
| SQaLe | huggingface.co/datasets/trl-lab/SQaLe-text-to-SQL-dataset | 517K | Check paper |
| Student Performance (UCI) | kaggle.com/datasets/larsen0966/student-performance-data-set | 649 | CC0 |
| CDE Downloadable Data | cde.ca.gov/ds/ad/downloadabledata.asp | Real data | Public |

### Papers/Frameworks
| Name | What It Does | URL |
|---|---|---|
| SING-SQL | Best framework for single-database in-domain training | github.com/HasanAlpCaferoglu/SING-SQL |
| OmniSQL | Million-scale synthesis pipeline | github.com/RUCKBReasoning/OmniSQL |
| SQaLe | Schema-variety-driven dataset | huggingface.co/blog/cwolff/sqale |
| Vanna AI | RAG-based text-to-SQL (alternative to fine-tuning) | github.com/vanna-ai/vanna |

### Tutorials
| Name | What It Covers | URL |
|---|---|---|
| Rubrik + Gretel + Predibase | Full fine-tune tutorial with Gretel data | rubrik.com/blog/ai/24/... |
| Google Gemma QLoRA | Fine-tune Gemma on text-to-SQL with QLoRA | ai.google.dev/gemma/docs/core/huggingface_text_finetune_qlora |
| Towards AI GRPO series | 60 training sessions, Qwen2.5-Coder experiments | pub.towardsai.net/fine-tuning-open-source-llms-for-text-to-sql |
