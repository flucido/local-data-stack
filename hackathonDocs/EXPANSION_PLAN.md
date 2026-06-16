# LFED Training Data Expansion Plan

> **Last updated:** 2026-06-08
> **Goal:** Expand from 1,289 pairs on 2 tables → 10,000+ pairs across 8+ analytics domains

---

## Current State

### What We Have Now
- **Tables:** 2 (enrollment, attendance)
- **Training pairs:** 1,289 (template-generated)
- **Templates:** 32
- **Coverage:** Chronic absenteeism, enrollment counts, absence rates
- **Quality:** Good for narrow domain, but synthetic-feeling

### What's in local-data-stack (Untapped Analytics Domains)

From `/Users/flucido/projects/local-data-stack/rill_project/data/`:

| Domain | Table | Rows | Key Columns |
|---|---|---|---|
| Chronic Absenteeism Risk | chronic_absenteeism_risk | 1,700 | risk_score, risk_level, attendance_rate_30d/90d, discipline_incidents, demographics |
| Student Wellbeing | wellbeing_risk_profiles | 1,700 | attendance/discipline/academic_risk_scores, wellbeing_risk_level, primary_concern |
| Performance Correlations | performance_correlations | 3 | correlation_pair, coefficient, strength |
| Class Effectiveness | class_effectiveness | 300 | avg_grade, pct_passed, effectiveness_rating, ELL/SpEd/FRL pass rates |
| Equity Outcomes | equity_outcomes_by_demographics | 10 | race_ethnicity, ELL, SpEd, FRL, avg_gpa, pct_below_c |

---

## Phase 1: Schema Expansion (Add 6 New Tables)

Add these tables to the DuckDB seed data and update prompts.py:

### 1.1 grades
```sql
CREATE TABLE grades (
    student_id INTEGER,
    school_name VARCHAR,
    school_year VARCHAR,
    grade_level INTEGER,
    course_name VARCHAR,
    term VARCHAR,              -- 'Fall', 'Spring'
    letter_grade VARCHAR,      -- 'A', 'B', 'C', 'D', 'F'
    grade_numeric DOUBLE,      -- 4.0, 3.0, etc.
    gpa DOUBLE,
    credit_hours DOUBLE
);
```

### 1.2 discipline
```sql
CREATE TABLE discipline (
    incident_id INTEGER,
    student_id INTEGER,
    school_name VARCHAR,
    school_year VARCHAR,
    grade_level INTEGER,
    incident_type VARCHAR,     -- 'Defiance', 'Fighting', 'Vandalism', 'Substance', 'Bullying'
    incident_date DATE,
    severity VARCHAR,          -- 'Minor', 'Major', 'Severe'
    action_taken VARCHAR,      -- 'Warning', 'Detention', 'Suspension', 'Expulsion'
    days_suspended INTEGER
);
```

### 1.3 demographics
```sql
CREATE TABLE demographics (
    student_id INTEGER,
    school_name VARCHAR,
    school_year VARCHAR,
    grade_level INTEGER,
    gender VARCHAR,
    race_ethnicity VARCHAR,
    english_learner BOOLEAN,
    special_education BOOLEAN,
    economically_disadvantaged BOOLEAN,
    homeless_flag BOOLEAN,
    migrant_flag BOOLEAN,
    foster_youth BOOLEAN
);
```

### 1.4 assessments
```sql
CREATE TABLE assessments (
    student_id INTEGER,
    school_name VARCHAR,
    school_year VARCHAR,
    grade_level INTEGER,
    assessment_type VARCHAR,   -- 'SBAC', 'CAASPP', 'CELCAST', 'District Benchmark'
    subject VARCHAR,           -- 'ELA', 'Math', 'Science'
    score DOUBLE,
    proficiency_level VARCHAR, -- 'Below Standard', 'Near Standard', 'At/Above Standard'
    growth_percentile INTEGER
);
```

### 1.5 programs
```sql
CREATE TABLE programs (
    student_id INTEGER,
    school_name VARCHAR,
    school_year VARCHAR,
    program_type VARCHAR,      -- 'Title I', 'ELL Support', 'SpEd IEP', '504 Plan', 'MTSS Tier 1/2/3'
    start_date DATE,
    end_date DATE,
    status VARCHAR             -- 'Active', 'Exited', 'Transferred'
);
```

### 1.6 staff
```sql
CREATE TABLE staff (
    staff_id INTEGER,
    school_name VARCHAR,
    school_year VARCHAR,
    role VARCHAR,              -- 'Teacher', 'Counselor', 'Admin', 'Aide'
    subject_area VARCHAR,
    years_experience INTEGER,
    credential_type VARCHAR,
    student_load INTEGER
);
```

---

## Phase 2: Training Data Expansion (1,289 → 10,000+ pairs)

### 2.1 New Template Categories (add ~150 templates)

#### Grades & GPA (~30 templates)
- Average GPA by school/grade/demographic
- Grade distribution (A/B/C/D/F counts and percentages)
- GPA trends over time
- Failing rate by course/teacher
- GPA comparison between schools
- Students below 2.0 GPA
- Honor roll counts

#### Discipline (~30 templates)
- Incident counts by type, school, year
- Suspension rates by demographic
- Discipline trends over time
- Most common incident types
- Students with multiple incidents
- Days lost to suspension by school
- Discipline correlation with attendance

#### Demographics (~20 templates)
- Enrollment by race/ethnicity
- ELL student counts and percentages
- SpEd population by school
- Economically disadvantaged rates
- Foster/homeless student counts
- Demographic breakdowns of outcomes

#### Assessments (~30 templates)
- Proficiency rates by subject and school
- Growth percentiles by grade
- Assessment score trends
- Below-standard student counts
- Demographic gaps in test scores
- School performance rankings

#### Programs (~20 templates)
- Active program counts by type
- MTSS tier distribution
- IEP/504 plan counts
- Program participation by school
- Title I eligible counts

#### Cross-Table Joins (~20 templates)
- Attendance vs. grades correlation
- Discipline incidents vs. GPA
- ELL status vs. assessment scores
- SpEd vs. chronic absenteeism
- Program participation vs. outcomes

### 2.2 Data Augmentation Strategies

#### A. Rephrasing (3-5x multiplier)
For each template, generate additional natural-language phrasings:
- **Formal:** "What is the average GPA for 9th graders at Jefferson High?"
- **Informal:** "What's the avg GPA for freshmen at Jefferson?"
- **Abbreviated:** "9th grade GPA at Jefferson High?"
- **Typo-prone:** "Whats the avg gpa for 9th graders at jefferson hiogh?"
- **Context-rich:** "I'm preparing for the board meeting — need 9th grade GPA at Jefferson High for 2023-2024"

Implementation: Use a small LLM (Qwen2.5-1.5B) to rephrase each template's question while keeping the SQL identical.

#### B. Question Decomposition
Train on multi-part questions:
- Q: "Compare chronic absenteeism rates and average GPA between Lincoln Elementary and Jefferson High"
- SQL: Two CTEs or UNION ALL

#### C. Ambiguous Questions
Train the model to ask clarifying questions or make reasonable assumptions:
- Q: "How are our students doing?"
- SQL: SELECT school_name, AVG(gpa) ... (with a reasonable default)

#### D. Error Recovery
Train on edge cases:
- Questions referencing non-existent columns → model should generate closest valid query
- Questions about data that doesn't exist → model should return empty result gracefully

### 2.3 Seed Data Expansion

Current: 2,900 students, 5 schools, 4 years

Expand to:
- **10,000 students** across 8 schools
- **6 school years** (2019-2025)
- **Realistic distributions:**
  - Chronic absenteeism: 15% (current) — keep
  - GPA distribution: normal around 2.8, std 0.8
  - Discipline: 8% of students with 1+ incident
  - ELL: 18%, SpEd: 12%, FRL: 45%
  - Assessment proficiency: 55% at/above standard

### 2.4 Quality Assurance Pipeline

1. **SQL Validation:** Run every generated SQL against seed data — must return results (or empty for legitimate queries)
2. **Schema Match:** Every column/table referenced must exist in schema
3. **Dedup:** Exact-match dedup on questions, near-match dedup on SQL structure
4. **Balance Check:** Ensure even coverage across all tables and query patterns
5. **Human Review:** Sample 5% of pairs for manual review

---

## Phase 3: Training Improvements

### 3.1 Data Quality
| Current | Target |
|---|---|
| 1,289 pairs | 10,000+ pairs |
| 2 tables | 8 tables |
| 32 templates | 150+ templates |
| Template-only questions | Template + LLM-rephrased + typo variants |
| No join queries | 20% multi-table joins |
| No ambiguous queries | 5% ambiguous/clarification-needed |

### 3.2 Training Config Improvements

| Param | Current | Proposed | Why |
|---|---|---|---|
| Epochs | 3 | 2 | More data needs fewer epochs to avoid overfitting |
| Learning rate | 2e-4 | 1e-4 | More data = can use lower LR for better convergence |
| LoRA rank | 16 | 32 | More data supports higher rank without overfitting |
| Max seq length | 2048 | 4096 | Multi-table joins need longer sequences |
| Batch size | 4×4=16 | 4×8=32 | Larger effective batch for larger dataset |

### 3.3 Evaluation Metrics

Add eval set (10% holdout):
- **Exact match:** Generated SQL matches expected SQL
- **Execution match:** Generated SQL returns same results as expected
- **Schema validity:** All referenced columns/tables exist
- **Safety:** No DDL/DML statements generated

---

## Phase 4: Implementation Order

| Step | Task | Effort | Priority |
|---|---|---|---|
| 1 | Define new table schemas (above) | 1 hour | P0 |
| 2 | Generate seed data for 6 new tables | 2 hours | P0 |
| 3 | Add new templates for grades + discipline (60 templates) | 3 hours | P0 |
| 4 | Run synthetic generation → 5,000+ pairs | 30 min | P0 |
| 5 | SQL validation pass (run all pairs against seed data) | 1 hour | P0 |
| 6 | Add demographic + assessment templates (50 templates) | 2 hours | P1 |
| 7 | LLM rephrasing augmentation (3x multiplier) | 2 hours | P1 |
| 8 | Add cross-table join templates (20 templates) | 1 hour | P1 |
| 9 | Re-run generation → 10,000+ pairs | 30 min | P1 |
| 10 | Train v2 model with expanded data | 2-3 hours | P1 |
| 11 | Eval v1 vs v2 on holdout set | 1 hour | P2 |
| 12 | Deploy v2 to HF Space | 30 min | P2 |

**Total estimated effort:** ~15-18 hours of work

---

## Phase 5: Quick Wins (Do First)

### 5.1 Expand Seed Data (immediate)
Write a `generate_seed_v2.py` that creates all 6 new tables with realistic distributions. This unblocks everything else.

### 5.2 Port local-data-stack Patterns
The local-data-stack already has analytics models for:
- Chronic absenteeism risk scoring
- Wellbeing composite scores
- Class effectiveness ratings
- Equity outcome comparisons

Port these SQL patterns into training templates. The queries are already validated — just need NL phrasings.

### 5.3 Add Join Templates
The biggest gap in current training is zero join queries. Even 20 join templates would dramatically improve the model's ability to answer cross-domain questions.

---

## Appendix: local-data-stack Column Reference

### chronic_absenteeism_risk
student_key, grade_level, school_id, gender, race_ethnicity, english_learner, special_education, economically_disadvantaged, homeless_flag, attendance_rate_30d, unexcused_absence_rate_30d, discipline_incidents_30d, absence_discipline_correlation_score, attendance_rate_90d, attendance_trend_90d, chronic_absence_flag, chronic_absenteeism_risk_score, risk_level

### wellbeing_risk_profiles
student_key, grade_level, school_id, attendance_risk_score, discipline_risk_score, academic_risk_score, high_risk_domain_count, wellbeing_risk_score, wellbeing_risk_level, primary_concern

### class_effectiveness
course_id, school_id, grade_level, enrollment_count, avg_grade_numeric, pct_passed, pct_a_b_grades, course_avg_grade, grade_diff_from_course_avg, pct_passed_ell, pct_passed_sped, pct_passed_frl, pass_rate_rank, grade_rank, effectiveness_rating, term

### equity_outcomes_by_demographics
race_ethnicity, english_learner, special_education, economically_disadvantaged, cohort_size, pct_good_attendance, pct_no_discipline, avg_gpa, pct_gpa_2_5_plus, pct_below_c
