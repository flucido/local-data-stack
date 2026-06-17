# Phase 4a: Option C Data Model Design

> Date: 2026-06-17
> Status: DRAFT — awaiting Frank's approval before implementation
> Decision: Option C (raw CDE staging tables for direct query + OBT mart for pre-computed dashboard queries)

---

## Design Principle

Option C means two query paths coexist in the warehouse:

1. **Direct query path** — CDE staging tables (`stg_cde__*`) remain available for ad-hoc
   NL→SQL queries. The model can generate `SELECT ... FROM main_cde.stg_cde__suspension`
   when a user asks "What's the suspension rate for Hispanic students in Alameda County?"

2. **Pre-computed path** — `mart_cde_school_accountability` OBT joins all CDE aggregate
   metrics onto `dim_schools` at the school × year × reporting_category grain. Dashboard
   queries hit this single wide table instead of joining 12 staging tables.

The NL→SQL router (future Phase 5) decides which path to use:
- Simple lookups → direct staging table query
- Complex multi-metric comparisons → OBT query (everything pre-joined)

---

## Grain

**OBT grain**: one row per `cds_code × academic_year × reporting_category`

This means a school with 15 reporting categories (TA + 7 race groups + 2 gender + 5
at-risk subgroups) in 4 years = 60 rows in the OBT. The `reporting_category = 'TA'` (Total
All Students) rows are the default for school-level dashboards; subgroup rows power equity
analysis.

**Why this grain and not school × year only:**
CDE reports every metric disaggregated by subgroup. Flattening to school × year would
either lose the subgroup dimension (unacceptable for equity analysis) or require 100+
columns (one per subgroup × metric). The school × year × subgroup grain keeps the table
wide but not absurdly wide.

---

## OBT Schema: `mart_cde_school_accountability`

Schema: `main_analytics` (consistent with existing analytics marts)

### Identity columns (shared with all CDE domains)
| Column | Type | Source | Description |
|--------|------|--------|-------------|
| cds_code | VARCHAR | all CDE tables | 14-char school identifier (join key) |
| academic_year | VARCHAR | all CDE tables | "2023-24" format |
| aggregate_level | VARCHAR | all CDE tables | T/C/D/S — always 'S' in OBT (school level) |
| reporting_category | VARCHAR | all CDE tables | TA, RA, RB, GM, GF, SE, EL, SWD, HOM, FOS, MIL, etc. |
| reporting_category_label | VARCHAR | derived | "Total (All Students)", "Hispanic/Latino", etc. |

### School identity (from dim_schools join)
| Column | Type | Source |
|--------|------|--------|
| school_id | VARCHAR | dim_schools (Aeries internal ID) |
| school_name | VARCHAR | CDE school directory or dim_schools |
| district_name | VARCHAR | CDE school directory |
| county_name | VARCHAR | CDE school directory |
| charter_school | BOOLEAN | CDE school directory |
| grade_span | VARCHAR | CDE school directory (K-5, 6-8, 9-12, etc.) |

### Chronic absenteeism metrics (from stg_cde__chronic_absenteeism)
| Column | Type | Description |
|--------|------|-------------|
| ca_eligible_enrollment | INTEGER | Students enrolled ≥ 31 days |
| ca_chronic_absent_count | INTEGER | Students missing ≥ 10% of days |
| ca_chronic_absent_rate_pct | DOUBLE | Rate (%) |

### Absenteeism reason metrics (from stg_cde__absenteeism_reason — NEW)
| Column | Type | Description |
|--------|------|-------------|
| ar_students_with_absences | INTEGER | Count with ≥ 1 absence |
| ar_avg_days_absent | DOUBLE | Average days absent per student |
| ar_total_days_absent | INTEGER | Total days lost |
| ar_pct_excused | DOUBLE | % excused |
| ar_pct_unexcused | DOUBLE | % unexcused |
| ar_pct_oss_absence | DOUBLE | % out-of-school suspension absences |
| ar_pct_incomplete_is | DOUBLE | % incomplete independent study |

### Enrollment metrics (from stg_cde__enrollment — NEW)
| Column | Type | Description |
|--------|------|-------------|
| en_cumulative_enrollment | INTEGER | Cumulative enrollment for the year |

### Suspension metrics (from stg_cde__suspension — NEW)
| Column | Type | Description |
|--------|------|-------------|
| su_total_suspensions | INTEGER | Total suspension incidents |
| su_unique_students_suspended | INTEGER | Unduplicated count |
| su_suspension_rate_pct | DOUBLE | Rate (%) |
| su_violent_injury | INTEGER | Violent incident (injury) count |
| su_violent_no_injury | INTEGER | Violent incident (no injury) count |
| su_weapons | INTEGER | Weapons possession count |
| su_drug_related | INTEGER | Illicit drug-related count |
| su_defiance_only | INTEGER | Defiance-only count |
| su_other_reasons | INTEGER | Other reasons count |

### Expulsion metrics (from stg_cde__expulsion — NEW)
| Column | Type | Description |
|--------|------|-------------|
| ex_total_expulsions | INTEGER | Total expulsion incidents |
| ex_unique_students_expelled | INTEGER | Unduplicated count |
| ex_expulsion_rate_pct | DOUBLE | Rate (%) |

### Homeless student enrollment (from stg_cde__homeless_enrollment — NEW)
| Column | Type | Description |
|--------|------|-------------|
| hs_cumulative_enrollment | INTEGER | Total enrollment |
| hs_homeless_count | INTEGER | Homeless student enrollment |
| hs_doubled_up_pct | DOUBLE | % temporarily doubled up |
| hs_shelters_pct | DOUBLE | % temporary shelters |
| hs_hotels_pct | DOUBLE | % hotels/motels |
| hs_unsheltered_pct | DOUBLE | % temporarily unsheltered |

### FRPM / poverty (from stg_cde__frpm — NEW)
| Column | Type | Description |
|--------|------|-------------|
| frpm_enrollment_k12 | INTEGER | K-12 enrollment |
| frpm_free_count_k12 | INTEGER | Free meal count (K-12) |
| frpm_free_pct_k12 | DOUBLE | % eligible free (K-12) |
| frpm_reduced_count_k12 | INTEGER | FRPM count (K-12) |
| frpm_reduced_pct_k12 | DOUBLE | % eligible FRPM (K-12) |

### Assessment metrics (from stg_cde__assessment_ela, stg_cde__assessment_elpac — NEW)
| Column | Type | Description |
|--------|------|-------------|
| ela_status | VARCHAR | Dashboard status (e.g., "Yellow", "Green") |
| ela_currdenom | INTEGER | Current denominator |
| ela_currstatus | DOUBLE | Current status metric |
| elpac_progressed_pct | DOUBLE | % progressed |
| elpac_maintained_pl4_pct | DOUBLE | % maintained PL4 |
| elpac_declined_pct | DOUBLE | % declined |

### SBAC/CAASPP scores (from stg_cde__assessment_caspp — NEW)
| Column | Type | Description |
|--------|------|-------------|
| sbac_mean_scale_score | DOUBLE | Mean scale score |
| sbac_pct_standard_exceeded | DOUBLE | % exceeded standard |
| sbac_pct_standard_met_above | DOUBLE | % met or above |
| sbac_pct_standard_not_met | DOUBLE | % not met standard |
| sbac_students_tested | INTEGER | Students tested |

### Data quality flags
| Column | Type | Description |
|--------|------|-------------|
| is_suppressed | BOOLEAN | Any CDE metric suppressed (n < 11) |
| has_cde_data | BOOLEAN | At least one CDE domain has data for this row |
| data_domains_present | INTEGER | Count of CDE domains with non-null data |

---

## Standalone Staging Tables (NOT in the OBT)

These domains have different grains or use cases that don't fit the school × year ×
subgroup OBT. They stay as standalone staging tables the NL→SQL model can query directly:

| Table | Why standalone |
|-------|---------------|
| `stg_cde__schools` | School directory — one row per school, no year/subgroup dimension |
| `stg_cde__cbedsora` | Staff demographics — different grain (staff, not students) |
| `stg_cde__enrollment_by_grade` | Grade-level enrollment counts — grain is school × year (no subgroup) |
| `stg_cde__enrollment_by_subgroup` | Percentage breakdowns — different unit (% not count) |
| `stg_cde__teacher_prep` | 113-column teacher credential data — doesn't belong in student accountability OBT |
| `stg_cde__teacher_misassign` | Teacher misassignment counts — different domain |
| `stg_cde__teacher_out_of_field` | Teacher out-of-field counts — different domain |
| `stg_cde__class_assign` | Class assignment data — different grain |
| `stg_cde__restraint_seclusion` | Very sparse data, different reporting structure |

These can still be queried by the NL→SQL model — they're just not pre-joined into the OBT.
The router decides: "How many teachers are misassigned at Lincoln Elementary?" → query
`stg_cde__teacher_misassign` directly.

---

## Aeries Integration (the other half of Option C)

The Aeries student-level data lives in `main_core`:
- `dim_students` (student_id_hash, demographics, program flags)
- `dim_schools` (school_id, cds_code, school/district/county names)
- `fact_attendance` (student_id_hash, school_id, year, days_enrolled/absent/present)
- `fact_discipline` (student_id_hash, incident_id, incident_type, suspension_days)
- `fact_enrollment` (student_id_hash, school_id, grade_level, enrollment_status)
- `fact_academic_records` (student_id_hash, course_id, term, grade, gpa_points)

**Join key**: `dim_schools.cds_code` connects Aeries school_id to CDE cds_code.

The OBT enriches `dim_schools` with CDE accountability metrics. But the student-level
facts stay separate — the NL→SQL model queries them when the user asks student-level
questions ("Which students are chronically absent AND failing math?").

**No Aeries data goes INTO the OBT.** The OBT is CDE-only aggregate metrics. Aeries
student-level queries hit the core fact tables directly. The OBT + Aeries facts are
complementary, not merged.

---

## OBT Construction Pattern

```sql
-- Pseudo-code for the mart dbt model

WITH school_dim AS (
    SELECT cds_code, school_id, school_name, district_name, county_name,
           charter_school, grade_span
    FROM {{ ref('dim_schools') }}
    WHERE cds_code IS NOT NULL
),

-- Build the grain: school × year × reporting_category
-- Use chronic absenteeism as the anchor (it has the most complete subgroup coverage)
grain AS (
    SELECT DISTINCT cds_code, academic_year, reporting_category
    FROM {{ ref('stg_cde__chronic_absenteeism') }}
    WHERE aggregate_level = 'S'
),

-- Left join each CDE domain onto the grain
-- Each domain contributes its prefixed columns
final AS (
    SELECT
        g.cds_code,
        g.academic_year,
        g.reporting_category,
        -- ... labels from shared macro ...
        sch.school_id, sch.school_name, sch.district_name, ...

        ca.eligible_enrollment AS ca_eligible_enrollment,
        ca.chronic_absent_count AS ca_chronic_absent_count,
        ca.chronic_absent_rate_pct AS ca_chronic_absent_rate_pct,

        su.total_suspensions AS su_total_suspensions,
        -- ... etc for each domain ...
    FROM grain g
    LEFT JOIN school_dim sch ON g.cds_code = sch.cds_code
    LEFT JOIN stg_cde__chronic_absenteeism ca
        ON g.cds_code = ca.cds_code
        AND g.academic_year = ca.academic_year
        AND g.reporting_category = ca.reporting_category
        AND ca.aggregate_level = 'S'
    LEFT JOIN stg_cde__suspension su
        ON g.cds_code = su.cds_code
        AND g.academic_year = su.academic_year
        AND g.reporting_category = su.reporting_category
        AND su.aggregate_level = 'S'
    -- ... repeat for each domain ...
)
SELECT * FROM final
```

---

## Shared dbt Macro: Reporting Category Labels

Extract the CASE block from `stg_cde__chronic_absenteeism.sql` into a reusable macro so
every staging model and the OBT use the same labels:

```sql
-- macros/cde_reporting_category.sql
{% macro cde_reporting_category_label(column_name='reporting_category') %}
    CASE {{ column_name }}
        WHEN 'TA' THEN 'Total (All Students)'
        WHEN 'RA' THEN 'Asian'
        WHEN 'RB' THEN 'Black/African American'
        -- ... full mapping from existing model ...
    END
{% endmacro %}
```

---

## Schema Registration for NL→SQL

After the OBT is built, update `nl_query/data_engine.py` schema exposure:

Current exposed schemas:
```
core, main_core, analytics, main_analytics, cde, main_cde
```

The OBT lands in `main_analytics`, which is already exposed. The NL→SQL model will see
both the OBT and the standalone staging tables. The prompts.py DEFAULT_SCHEMA should be
updated to include:

```python
"main_analytics.mart_cde_school_accountability": [
    ("cds_code", "VARCHAR", "14-char school identifier"),
    ("academic_year", "VARCHAR", "School year (format 'YYYY-YY')"),
    ("reporting_category", "VARCHAR", "Subgroup code (TA=all, RA=Asian, SE=Socioeconomically Disadvantaged, etc.)"),
    ("school_name", "VARCHAR", "School name"),
    ("ca_chronic_absent_rate_pct", "DOUBLE", "Chronic absenteeism rate (%)"),
    ("su_suspension_rate_pct", "DOUBLE", "Suspension rate (%)"),
    ("ex_expulsion_rate_pct", "DOUBLE", "Expulsion rate (%)"),
    # ... key columns for the model to know about ...
],
```

---

## Implementation Order (Phase 4b)

1. Create shared macro `cde_reporting_category.sql`
2. Build all `stg_cde__*` staging models (Phase 3 — each domain gets one)
3. Build `mart_cde_school_accountability.sql` joining all staging models
4. Add tests: row count invariants, CDS code not null at school level, rate columns 0-100
5. Run `dbt build` against the warehouse
6. Verify the OBT has data by spot-checking a known school
7. Update `nl_query/prompts.py` with OBT schema

---

## Aeries Test Data Integration (updated 2026-06-17)

The Aeries test data inventory is complete. Full report at
`~/.hermes/hermes-agent/AERIES_DATA_INVENTORY.md`.

### Source data summary
- 60 CSVs across 9 subdirectories, 6 academic years (2020-21 through 2025-26)
- ~850 students per year, ~5,300 total across years
- Contains REAL un-redacted student PII — anonymization is mandatory before warehouse load

### Aeries → warehouse mapping (after anonymization)

| Aeries source | Warehouse target | Grain | Key columns |
|---------------|-----------------|-------|------------|
| `students/` (demographics) | `stg_aeries__students` → `dim_students` | student × year | student_id_hash, gender, grade, race codes, language codes, program flags |
| `attendance_transformed/` | `stg_aeries__attendance` → `fact_attendance` | student × school × year | student_id_hash, school_id, days_enrolled/present/absent, period counts |
| `enrollment/` | `stg_aeries__enrollment` → `fact_enrollment` | student × school × year | student_id_hash, school_id, grade, enter/leave dates, exit reason |
| `grades_gpa/gpa_*.csv` | `stg_aeries__academic_records` (GPA portion) → `fact_academic_records` | student × year | student_id_hash, GPA_Cumulative*, class_rank, credits |
| `grades_transformed/` | `stg_aeries__academic_records` (course grades portion) → `fact_academic_records` | student × course × term × year | student_id_hash, course_id, MP_Mark, MP_Credit, MP_Total* |
| `discipline_transformed/` | `stg_aeries__discipline` → `fact_discipline` | student × incident × year | student_id_hash, incident_date, violation_codes, disposition, suspension_days |
| `programs/` | `stg_aeries__programs` → `fact_programs` | student × program × year | student_id_hash, program_code, start/end dates |

### Anonymization approach (in progress — background sub-agent)
1. Hash StudentID with SHA-256 + fixed salt across ALL files (consistent joins)
2. Hash staff IDs (TeacherNumber, CounselorNumber, etc.) with separate salt
3. Drop all name, DOB, address, phone, email, login fields
4. NULL out free-text fields (Comment, ShortDescription, Initials)
5. Drop unknown UserCode fields
6. Strip whitespace (critical for 2022-23 file)
7. Output as Parquet to `data/aeries_anonymized/`
8. Source from `_transformed/` files where available (already flattened)

### Aeries → CDE join path

```
Aeries fact_attendance.school_id → dim_schools.school_id → dim_schools.cds_code → CDE stg_cde__*.cds_code
```

The existing `dim_schools` already maps Aeries school_id to CDE cds_code. After
anonymized Aeries data is loaded into the warehouse, the OBT can optionally add an
Aeries-enriched view with internal attendance/discipline rates alongside CDE benchmarks.

**Design decision**: The OBT stays CDE-only. Aeries data enrichment happens through a
separate view (`v_school_benchmarks` already exists and does this for chronic
absenteeism). Extend that pattern — don't bloat the OBT with student-level aggregates.

---

## Resolved Design Decisions (approved by Frank 2026-06-17)

1. **SBAC grain**: Summarize SBAC/CAASPP assessment scores to the OBT's school × year ×
   reporting_category grain. Keep the raw staging table (`stg_cde__assessment_caspp`)
   for detailed queries that need grade-level or subject-level breakdowns.

2. **Dashboard vs. raw files**: OBT uses raw counts/rates for all metrics. Dashboard
   status columns (statuslevel, color, changeLevel) join as optional enrichment columns
   where available. The raw staging tables are the source of truth; dashboard versions
   (`chronicdownload`, `suspdownload`, `eladownload`) stay as separate staging tables for
   accountability-specific queries.

3. **Grain anchor**: Use the CDE school directory (all CA schools) × academic years ×
   standard reporting categories as the OBT grain anchor. Schools without chronic
   absenteeism or other CDE data appear with NULL metric rows. This produces the fullest
   possible OBT.

4. **Aeries test data**: ~850 students/year, one district — confirmed as the development
   dataset. The OBT and pipeline are SIS-agnostic by design; Aeries is just the first
   SIS adapter.

## Future Pin: Multi-SIS Flexibility

> Pinned by Frank 2026-06-17: The warehouse architecture must remain SIS-agnostic.
> Aeries is the first adapter; PowerSchool and other SIS providers will follow.
> The staging layer (`stg_<sis>__*`) is per-SIS, but the core fact/dimension tables
> (`dim_students`, `fact_attendance`, `fact_discipline`, etc.) use generic column names
> not tied to any SIS vendor. When adding a new SIS:
>   1. Write a new extraction script (like `anonymize_aeries.py` but for the new SIS)
>   2. Write `stg_<sis>__*` staging models that map vendor columns to the canonical schema
>   3. The core marts and OBT don't change — they read from `dim_*` / `fact_*` which are
>      SIS-agnostic
> This is a documentation/design constraint, not a current implementation task.
