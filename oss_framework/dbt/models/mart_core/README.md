# Core Analytics Marts (mart_core)

## Overview

The core analytics marts provide business-logic-heavy, privacy-preserving analytics models built on top of the privacy layer. These models use pseudonymous identifiers and implement k-anonymity enforcement where appropriate.

## Purpose

Core marts serve as the foundation for:
- Executive dashboards and reporting
- Predictive analytics and ML features
- Compliance reporting (FERPA-compliant)
- Cross-domain analysis (attendance, academics, discipline)

## Architecture

```
Privacy Layer (priv_student_hashes)
            │
            ▼
┌───────────────────────────────────────────────────────┐
│              Core Dimensions                          │
│  - dim_students (pseudonymized demographics)          │
│  - dim_schools (reference data)                       │
│  - dim_student_demographics (aggregated, k≥5)         │
└───────────────────────────────────────────────────────┘
            │
            ▼
┌───────────────────────────────────────────────────────┐
│              Core Facts                               │
│  - fact_attendance (student-level, hashed)            │
│  - fact_academic_records (course grades, hashed)      │
│  - fact_discipline (incidents, hashed)                │
│  - fact_enrollment (enrollment periods, hashed)       │
│  - fact_attendance_daily (aggregated, k≥5)            │
└───────────────────────────────────────────────────────┘
```

## K-Anonymity Guarantees

### What is K-Anonymity?

K-anonymity ensures that every individual in a dataset is indistinguishable from at least k-1 other individuals based on **quasi-identifiers** (combinations of attributes that could identify individuals).

**FERPA Requirement**: Educational data aggregations must use **k≥5** to prevent re-identification of students.

### Quasi-Identifiers

**Quasi-identifiers** are attributes that, when combined, could potentially identify individuals:

| Model | Quasi-Identifiers | Explanation |
|-------|------------------|-------------|
| `dim_student_demographics` | grade_level, gender, ethnicity, school_id, special_education_flag, ell_status, free_reduced_lunch_flag | Demographic combinations |
| `fact_attendance_daily` | attendance_date, school_id, grade_level | Date + location + grade |

### Enforcement Implementation

K-anonymity is enforced via `HAVING COUNT(DISTINCT student_id_hash) >= 5` in SQL:

**Example from `dim_student_demographics`**:
```sql
SELECT
    grade_level,
    gender,
    ethnicity,
    school_id,
    special_education_flag,
    ell_status,
    free_reduced_lunch_flag,
    COUNT(DISTINCT student_id_hash) as student_count,
    -- aggregated metrics --
FROM {{ ref('priv_student_hashes') }}
GROUP BY /* all quasi-identifiers */
HAVING COUNT(DISTINCT student_id_hash) >= 5  -- Enforce k≥5
```

**Result**: Only groups with ≥5 students are included. Smaller groups are suppressed automatically.

### Suppression Rates

When k-anonymity filtering is applied, some groups may be suppressed:

**Current Data**:
- `dim_student_demographics`: ~60 small groups suppressed (out of ~400 total)
- `fact_attendance_daily`: ~324 date/school/grade combinations suppressed

**Implications**:
- ✅ FERPA compliant - no groups <5 students
- ⚠️ Some rare demographic combinations excluded from aggregates
- ℹ️ Student-level models (e.g., `dim_students`, `fact_attendance`) are NOT suppressed - they use pseudonymous identifiers instead

## Models

### Dimensions

#### `dim_students`

Student dimension with pseudonymized identifiers.

**Grain**: One row per student  
**Privacy**: Uses `student_id_hash` from privacy layer

**Key Columns**:
- `student_id_hash` - Pseudonymous identifier (SHA256)
- Demographics (age, gender, ethnicity, grade_level)
- Enrollment flags (special_education, ELL, free_reduced_lunch, etc.)
- Risk indicators (high_need_flag, housing_risk, etc.)

**Use Cases**:
- Join dimension for all fact tables
- Student cohort identification
- Risk stratification

---

#### `dim_student_demographics`

Aggregated demographics with k-anonymity enforcement (k≥5).

**Grain**: One row per unique demographic combination (with ≥5 students)  
**Privacy**: K-anonymity enforced via HAVING clause

**Key Columns**:
- Quasi-identifiers (grade_level, gender, ethnicity, school_id, flags)
- `student_count` - Number of students in this cohort (always ≥5)
- Aggregated metrics (avg_age, active_rate)

**Use Cases**:
- District-wide demographic reporting
- Equity gap analysis by subgroup
- Enrollment trend analysis

**⚠️ Important**: This model is pre-aggregated. Do NOT use generic k_anonymity tests on it - k-anonymity is enforced in the SQL.

---

#### `dim_schools`

School reference dimension.

**Grain**: One row per school  
**Key Columns**: school_id, school_name

---

### Facts

#### `fact_attendance`

Daily student attendance records with pseudonymized identifiers.

**Grain**: One row per student per attendance date  
**Privacy**: Uses `student_id_hash` (SHA256)

**Key Columns**:
- `student_id_hash` - Pseudonymous student identifier
- `attendance_date`, `school_id`
- Attendance flags (present, absent, tardy, excused, unexcused)

**Use Cases**:
- Individual student attendance tracking
- Chronic absenteeism identification
- Attendance pattern analysis

---

#### `fact_attendance_daily`

Daily attendance aggregations with k-anonymity enforcement (k≥5).

**Grain**: One row per date/school/grade combination (with ≥5 students)  
**Privacy**: K-anonymity enforced via HAVING clause

**Key Columns**:
- Quasi-identifiers (attendance_date, school_id, grade_level)
- `total_students` - Count of students (always ≥5)
- Aggregated counts (present_count, absent_count, tardy_count)
- `attendance_rate` - Percentage present

**Use Cases**:
- Daily attendance rate monitoring by school
- Grade-level attendance patterns
- Trend analysis over time

**⚠️ Important**: This model is pre-aggregated. K-anonymity is enforced in the SQL.

---

#### `fact_academic_records`

Student academic performance data with pseudonymized identifiers.

**Grain**: One row per student per course per term  
**Privacy**: Uses `student_id_hash` (SHA256)

**Key Columns**:
- `student_id_hash` - Pseudonymous student identifier
- `teacher_id_hash` - Pseudonymous teacher identifier
- Course identifiers (course_id, section_id)
- Grade data (grade, score)
- Derived fields (academic_status: PASSING/FAILING)

**Use Cases**:
- Course performance analysis
- Teacher effectiveness analysis
- Grade distribution reporting

---

#### `fact_discipline`

Student discipline incident records with pseudonymized identifiers.

**Grain**: One row per incident  
**Privacy**: Uses `student_id_hash` (SHA256)

**Key Columns**:
- `student_id_hash` - Pseudonymous student identifier
- Incident data (incident_date, incident_type, severity)
- Consequences (suspension_days, resolution)
- Derived flags (suspension_flag, serious_incident_flag)

**Use Cases**:
- Discipline incident tracking
- Suspension rate analysis
- Disproportionality analysis

---

#### `fact_enrollment`

Student enrollment records with pseudonymized identifiers.

**Grain**: One row per enrollment period  
**Privacy**: Uses `student_id_hash` (SHA256)

**Key Columns**:
- `student_id_hash` - Pseudonymous student identifier
- Enrollment data (enrollment_date, withdrawal_date, grade_level)
- Status (enrollment_status, enrollment_status_derived)

**Use Cases**:
- Enrollment tracking
- Withdrawal analysis
- Mobility reporting

## Data Quality

**Tests Implemented**:
- ✅ Uniqueness tests on primary keys
- ✅ Not-null constraints on required fields
- ✅ Referential integrity (all fact tables join to `priv_student_hashes`)
- ✅ Accepted values for categorical fields
- ✅ K-anonymity enforced in SQL (no explicit tests on aggregated models)

**Test Coverage**: 62 tests across 10 models (100% passing)

**Run Tests**:
```bash
dbt test --select mart_core
```

## Best Practices

### When to Use Student-Level vs. Aggregated Models

| Use Case | Model Type | Example |
|----------|-----------|---------|
| Individual student tracking | Student-level facts | `fact_attendance`, `fact_academic_records` |
| Cohort analysis | Student-level dimensions | `dim_students` |
| Public reporting | Aggregated models | `dim_student_demographics`, `fact_attendance_daily` |
| Dashboards (with proper access control) | Either | Depends on audience |

### Joining Models

**✅ Correct**:
```sql
-- Join fact to dimension on pseudonymous identifier
SELECT
    ds.grade_level,
    ds.gender,
    COUNT(*) as student_count,
    AVG(fa.attendance_rate) as avg_attendance
FROM {{ ref('fact_attendance') }} fa
JOIN {{ ref('dim_students') }} ds
    ON fa.student_id_hash = ds.student_id_hash
GROUP BY ds.grade_level, ds.gender
HAVING COUNT(DISTINCT fa.student_id_hash) >= 5  -- Enforce k-anonymity
```

**❌ Incorrect**:
```sql
-- NEVER join to priv_pii_lookup_table in analytics queries
SELECT
    p.first_name_raw,  -- Raw PII exposed!
    fa.attendance_rate
FROM {{ ref('fact_attendance') }} fa
JOIN {{ ref('priv_pii_lookup_table') }} p
    ON fa.student_id_hash = p.student_id_hash  -- FERPA violation!
```

### Creating New Aggregated Models

When creating new aggregated models with k-anonymity:

1. **Identify quasi-identifiers** (attributes that could identify individuals)
2. **Group by ALL quasi-identifiers**
3. **Add HAVING clause** with `COUNT(DISTINCT student_id_hash) >= 5`
4. **Document quasi-identifiers** in model description
5. **Do NOT add generic k_anonymity test** (test won't work on aggregated data)

**Template**:
```sql
SELECT
    quasi_id_1,
    quasi_id_2,
    quasi_id_3,
    COUNT(DISTINCT student_id_hash) as student_count,
    -- aggregated metrics --
FROM {{ ref('priv_student_hashes') }}
GROUP BY quasi_id_1, quasi_id_2, quasi_id_3
HAVING COUNT(DISTINCT student_id_hash) >= 5  -- K-anonymity enforcement
```

## FERPA Compliance

The core marts achieve FERPA compliance through:

- ✅ **Pseudonymization**: All facts use `student_id_hash` (SHA256)
- ✅ **K-anonymity**: Aggregated models enforce k≥5
- ✅ **No raw PII**: No exposure of names, DOBs, or other identifiers
- ✅ **Access controls**: Separation from `priv_pii_lookup_table`

**Compliance Verification**:
```bash
# Verify no raw PII in core models
dbt test --select mart_core

# Verify all relationships to privacy layer are valid
dbt test --select mart_core --select test_type:relationships
```

## Related Documentation

- [Privacy Layer README](../mart_privacy/README.md) - Pseudonymization and hashing details
- [Macros README](../../macros/README.md) - Hashing and masking macros
- [Staging Layer README](../staging/aeries/README.md) - Source data structure

## Metrics

**Current State**:
- ✅ 10 core models (6 facts, 4 dimensions)
- ✅ 2 aggregated models with k-anonymity enforcement
- ✅ 62 data tests (100% passing)
- ✅ All facts use SHA256 hashing
- ✅ FERPA-compliant design

**Last Updated**: 2026-01-28
