-- models/mart_analytics/analytics/mart_cde_school_accountability.sql
-- Phase 4b: CDE School Accountability One Big Table (OBT)
--
-- Joins all CDE aggregate metrics at the school × academic_year × reporting_category grain.
-- Per Option C design: raw CDE staging tables remain queryable directly (Path A),
-- while this OBT provides pre-joined metrics for dashboard and multi-metric queries (Path B).
--
-- Grain: one row per cds_code × academic_year × reporting_category
-- Anchor: UNION of distinct grain keys from all OBT-grain staging models.
--   (TODO: when stg_cde__schools is wired to schldir.txt, expand anchor to
--    school_directory × years × standard_reporting_categories for fuller coverage.)
--
-- Design decisions (approved Frank 2026-06-17):
--   1. SBAC summarized to OBT grain (avg scores, sum counts across grades)
--   2. Raw counts/rates used for metrics; dashboard status as optional enrichment
--   3. Full school-directory anchor (implemented as grain UNION for now)
--   4. Aeries test data is dev dataset; OBT stays CDE-only
--
-- SIS-agnostic: this mart depends only on CDE data, not on any SIS vendor schema.

{{ config(
    materialized='table',
    schema='analytics',
    tags=['analytics', 'cde', 'obt', 'accountability']
) }}

-- ── Standard reporting categories (CDE-defined subgroup codes) ─────────
{% set standard_rcs = [
    'TA', 'RA', 'RB', 'RF', 'RH', 'RI', 'RP', 'RT', 'RW',
    'GM', 'GF', 'GX',
    'SE', 'EL', 'RFEP', 'IFEP', 'SWD', 'HOM', 'FOS', 'MIL',
    'GRTKKN', 'GR13', 'GR46', 'GR78', 'GR912', 'GRTK8'
] %}

-- ── Academic years present in the downloaded CDE data ──────────────────
{% set academic_years = ['2020-21', '2021-22', '2022-23', '2023-24', '2024-25'] %}

-- ── School dimension (Aeries → CDS mapping, if available) ───────────────
WITH school_dim AS (
    SELECT
        cds_code,
        school_id,
        school_name,
        cde_district_name AS district_name,
        cde_county AS county_name,
        latitude,
        longitude
    FROM {{ ref('dim_schools') }}
    WHERE cds_code IS NOT NULL
),

-- ── Grain: union of all (cds_code, academic_year, reporting_category) ───
-- from every OBT-grain staging model. This ensures every school×year×subgroup
-- that has data in ANY domain appears in the OBT, even if other domains are NULL.
grain AS (
    SELECT DISTINCT cds_code, academic_year, reporting_category
    FROM {{ ref('stg_cde__chronic_absenteeism') }}
    WHERE aggregate_level = 'S' AND cds_code IS NOT NULL

    UNION
    SELECT DISTINCT cds_code, academic_year, reporting_category
    FROM {{ ref('stg_cde__absenteeism_reason') }}
    WHERE aggregate_level = 'S' AND cds_code IS NOT NULL

    UNION
    SELECT DISTINCT cds_code, academic_year, reporting_category
    FROM {{ ref('stg_cde__enrollment') }}
    WHERE aggregate_level = 'S' AND cds_code IS NOT NULL

    UNION
    SELECT DISTINCT cds_code, academic_year, reporting_category
    FROM {{ ref('stg_cde__suspension') }}
    WHERE aggregate_level = 'S' AND cds_code IS NOT NULL

    UNION
    SELECT DISTINCT cds_code, academic_year, reporting_category
    FROM {{ ref('stg_cde__expulsion') }}
    WHERE aggregate_level = 'S' AND cds_code IS NOT NULL

    UNION
    SELECT DISTINCT cds_code, academic_year, reporting_category
    FROM {{ ref('stg_cde__homeless_enrollment') }}
    WHERE aggregate_level = 'S' AND cds_code IS NOT NULL

    UNION
    SELECT DISTINCT cds_code, academic_year, reporting_category
    FROM {{ ref('stg_cde__assessment_ela') }}
    WHERE cds_code IS NOT NULL

    UNION
    SELECT DISTINCT cds_code, academic_year, reporting_category
    FROM {{ ref('stg_cde__assessment_elpac') }}
    WHERE cds_code IS NOT NULL

    UNION
    SELECT DISTINCT cds_code, academic_year, reporting_category
    FROM {{ ref('stg_cde__assessment_caspp') }}
    WHERE cds_code IS NOT NULL

    UNION
    SELECT DISTINCT cds_code, academic_year, reporting_category
    FROM {{ ref('stg_cde__restraint_seclusion') }}
    WHERE aggregate_level = 'S' AND cds_code IS NOT NULL
),

-- ── Chronic Absenteeism ────────────────────────────────────────────────
ca AS (
    SELECT cds_code, academic_year, reporting_category,
           eligible_enrollment, chronic_absent_count, chronic_absent_rate_pct,
           is_suppressed AS ca_is_suppressed
    FROM {{ ref('stg_cde__chronic_absenteeism') }}
    WHERE aggregate_level = 'S'
),

-- ── Absenteeism by Reason ──────────────────────────────────────────────
ar AS (
    SELECT cds_code, academic_year, reporting_category,
           count_of_students_with_one_or_more_absences AS ar_students_with_absences,
           average_days_absent AS ar_avg_days_absent,
           total_days_absent AS ar_total_days_absent,
           excused_absences_percent AS ar_pct_excused,
           unexcused_absences_percent AS ar_pct_unexcused,
           out_of_school_suspension_absences_percent AS ar_pct_oss_absence,
           incomplete_independent_study_absences_percent AS ar_pct_incomplete_is
    FROM {{ ref('stg_cde__absenteeism_reason') }}
    WHERE aggregate_level = 'S'
),

-- ── Cumulative Enrollment ──────────────────────────────────────────────
en AS (
    SELECT cds_code, academic_year, reporting_category,
           cumulative_enrollment AS en_cumulative_enrollment
    FROM {{ ref('stg_cde__enrollment') }}
    WHERE aggregate_level = 'S'
),

-- ── Suspension ─────────────────────────────────────────────────────────
su AS (
    SELECT cds_code, academic_year, reporting_category,
           total_suspensions AS su_total_suspensions,
           unduplicated_count_of_students_suspended_total AS su_unique_students_suspended,
           suspension_rate_total AS su_suspension_rate_pct,
           suspension_count_violent_incident_injury AS su_violent_injury,
           suspension_count_violent_incident_no_injury AS su_violent_no_injury,
           suspension_count_weapons_possession AS su_weapons,
           suspension_count_illicit_drug_related AS su_drug_related,
           suspension_count_defiance_only AS su_defiance_only,
           suspension_count_other_reasons AS su_other_reasons
    FROM {{ ref('stg_cde__suspension') }}
    WHERE aggregate_level = 'S'
),

-- ── Expulsion ──────────────────────────────────────────────────────────
ex AS (
    SELECT cds_code, academic_year, reporting_category,
           total_expulsions AS ex_total_expulsions,
           unduplicated_count_of_students_expelled_total AS ex_unique_students_expelled,
           expulsion_rate_total AS ex_expulsion_rate_pct
    FROM {{ ref('stg_cde__expulsion') }}
    WHERE aggregate_level = 'S'
),

-- ── Homeless Student Enrollment ────────────────────────────────────────
hs AS (
    SELECT cds_code, academic_year, reporting_category,
           cumulative_enrollment AS hs_cumulative_enrollment,
           homeless_student_enrollment AS hs_homeless_count,
           temporarily_doubled_up_percent AS hs_doubled_up_pct,
           temporary_shelters_percent AS hs_shelters_pct,
           hotels_motels_percent AS hs_hotels_pct,
           temporarily_unsheltered_percent AS hs_unsheltered_pct
    FROM {{ ref('stg_cde__homeless_enrollment') }}
    WHERE aggregate_level = 'S'
),

-- ── FRPM (school grain — no reporting_category, joins to all RCs) ──────
frpm AS (
    SELECT cds_code, academic_year,
           enrollment_k12 AS frpm_enrollment_k12,
           free_meal_count_k12 AS frpm_free_count_k12,
           percent_eligible_free_k12 AS frpm_free_pct_k12,
           frpm_count_k12 AS frpm_reduced_count_k12,
           percent_eligible_frpm_k12 AS frpm_reduced_pct_k12
    FROM {{ ref('stg_cde__frpm') }}
),

-- ── ELA Assessment ─────────────────────────────────────────────────────
ela AS (
    SELECT cds_code, academic_year, reporting_category,
           currdenom AS ela_currdenom,
           currstatus AS ela_currstatus,
           statuslevel AS ela_status
    FROM {{ ref('stg_cde__assessment_ela') }}
),

-- ── ELPAC Assessment ───────────────────────────────────────────────────
elpac AS (
    SELECT cds_code, academic_year, reporting_category,
           pctcurrprogressed AS elpac_progressed_pct,
           pctcurrmaintainpl4 AS elpac_maintained_pl4_pct,
           pctcurrdeclined AS elpac_declined_pct
    FROM {{ ref('stg_cde__assessment_elpac') }}
),

-- ── SBAC/CAASPP (already summarized to OBT grain in staging) ───────────
sbac AS (
    SELECT cds_code, academic_year, reporting_category,
           mean_scale_score AS sbac_mean_scale_score,
           percentage_standard_exceeded AS sbac_pct_standard_exceeded,
           percentage_standard_met_and_above AS sbac_pct_standard_met_above,
           percentage_standard_not_met AS sbac_pct_standard_not_met,
           students_tested AS sbac_students_tested
    FROM {{ ref('stg_cde__assessment_caspp') }}
),

-- ── Restraint & Seclusion ──────────────────────────────────────────────
rs AS (
    SELECT cds_code, academic_year, reporting_category,
           count_of_mechanical_restraints AS rs_mechanical_restraints,
           count_of_physical_restraints AS rs_physical_restraints,
           count_of_seclusions AS rs_seclusions
    FROM {{ ref('stg_cde__restraint_seclusion') }}
    WHERE aggregate_level = 'S'
),

-- ── Join everything onto the grain ────────────────────────────────────
joined AS (
    SELECT
        g.cds_code,
        g.academic_year,
        g.reporting_category,
        {{ cde_reporting_category_label('g.reporting_category') }} AS reporting_category_label,

        -- School identity (from Aeries dim_schools if mapped)
        sch.school_id,
        sch.school_name,
        sch.district_name,
        sch.county_name,
        sch.latitude,
        sch.longitude,

        -- Chronic absenteeism
        ca.eligible_enrollment AS ca_eligible_enrollment,
        ca.chronic_absent_count AS ca_chronic_absent_count,
        ca.chronic_absent_rate_pct AS ca_chronic_absent_rate_pct,

        -- Absenteeism by reason
        ar.ar_students_with_absences,
        ar.ar_avg_days_absent,
        ar.ar_total_days_absent,
        ar.ar_pct_excused,
        ar.ar_pct_unexcused,
        ar.ar_pct_oss_absence,
        ar.ar_pct_incomplete_is,

        -- Enrollment
        en.en_cumulative_enrollment,

        -- Suspension
        su.su_total_suspensions,
        su.su_unique_students_suspended,
        su.su_suspension_rate_pct,
        su.su_violent_injury,
        su.su_violent_no_injury,
        su.su_weapons,
        su.su_drug_related,
        su.su_defiance_only,
        su.su_other_reasons,

        -- Expulsion
        ex.ex_total_expulsions,
        ex.ex_unique_students_expelled,
        ex.ex_expulsion_rate_pct,

        -- Homeless
        hs.hs_cumulative_enrollment,
        hs.hs_homeless_count,
        hs.hs_doubled_up_pct,
        hs.hs_shelters_pct,
        hs.hs_hotels_pct,
        hs.hs_unsheltered_pct,

        -- FRPM (school grain, same for all reporting categories)
        frpm.frpm_enrollment_k12,
        frpm.frpm_free_count_k12,
        frpm.frpm_free_pct_k12,
        frpm.frpm_reduced_count_k12,
        frpm.frpm_reduced_pct_k12,

        -- ELA assessment
        ela.ela_currdenom,
        ela.ela_currstatus,
        ela.ela_status,

        -- ELPAC assessment
        elpac.elpac_progressed_pct,
        elpac.elpac_maintained_pl4_pct,
        elpac.elpac_declined_pct,

        -- SBAC/CAASPP
        sbac.sbac_mean_scale_score,
        sbac.sbac_pct_standard_exceeded,
        sbac.sbac_pct_standard_met_above,
        sbac.sbac_pct_standard_not_met,
        sbac.sbac_students_tested,

        -- Restraint & seclusion
        rs.rs_mechanical_restraints,
        rs.rs_physical_restraints,
        rs.rs_seclusions,

        -- Metadata
        CURRENT_TIMESTAMP AS dbt_loaded_at

    FROM grain g
    LEFT JOIN school_dim sch ON g.cds_code = sch.cds_code
    LEFT JOIN ca  ON g.cds_code = ca.cds_code  AND g.academic_year = ca.academic_year  AND g.reporting_category = ca.reporting_category
    LEFT JOIN ar  ON g.cds_code = ar.cds_code  AND g.academic_year = ar.academic_year  AND g.reporting_category = ar.reporting_category
    LEFT JOIN en  ON g.cds_code = en.cds_code  AND g.academic_year = en.academic_year  AND g.reporting_category = en.reporting_category
    LEFT JOIN su  ON g.cds_code = su.cds_code  AND g.academic_year = su.academic_year  AND g.reporting_category = su.reporting_category
    LEFT JOIN ex  ON g.cds_code = ex.cds_code  AND g.academic_year = ex.academic_year  AND g.reporting_category = ex.reporting_category
    LEFT JOIN hs  ON g.cds_code = hs.cds_code  AND g.academic_year = hs.academic_year  AND g.reporting_category = hs.reporting_category
    LEFT JOIN frpm ON g.cds_code = frpm.cds_code AND g.academic_year = frpm.academic_year
    LEFT JOIN ela  ON g.cds_code = ela.cds_code  AND g.academic_year = ela.academic_year  AND g.reporting_category = ela.reporting_category
    LEFT JOIN elpac ON g.cds_code = elpac.cds_code AND g.academic_year = elpac.academic_year AND g.reporting_category = elpac.reporting_category
    LEFT JOIN sbac ON g.cds_code = sbac.cds_code AND g.academic_year = sbac.academic_year AND g.reporting_category = sbac.reporting_category
    LEFT JOIN rs   ON g.cds_code = rs.cds_code   AND g.academic_year = rs.academic_year   AND g.reporting_category = rs.reporting_category
),

-- ── Data quality flags ─────────────────────────────────────────────────
flagged AS (
    SELECT
        j.*,

        -- Suppression: any domain suppressed for this row
        CASE
            WHEN ca_chronic_absent_count IS NULL AND ca_eligible_enrollment IS NULL THEN FALSE
            WHEN ca_eligible_enrollment IS NULL THEN TRUE
            ELSE FALSE
        END AS is_suppressed,

        -- Count of CDE domains with non-null data for this row
        (CASE WHEN ca_eligible_enrollment IS NOT NULL THEN 1 ELSE 0 END) +
        (CASE WHEN ar_students_with_absences IS NOT NULL THEN 1 ELSE 0 END) +
        (CASE WHEN en_cumulative_enrollment IS NOT NULL THEN 1 ELSE 0 END) +
        (CASE WHEN su_total_suspensions IS NOT NULL THEN 1 ELSE 0 END) +
        (CASE WHEN ex_total_expulsions IS NOT NULL THEN 1 ELSE 0 END) +
        (CASE WHEN hs_homeless_count IS NOT NULL THEN 1 ELSE 0 END) +
        (CASE WHEN frpm_enrollment_k12 IS NOT NULL THEN 1 ELSE 0 END) +
        (CASE WHEN ela_currstatus IS NOT NULL THEN 1 ELSE 0 END) +
        (CASE WHEN elpac_progressed_pct IS NOT NULL THEN 1 ELSE 0 END) +
        (CASE WHEN sbac_mean_scale_score IS NOT NULL THEN 1 ELSE 0 END) +
        (CASE WHEN rs_mechanical_restraints IS NOT NULL THEN 1 ELSE 0 END)
        AS data_domains_present,

        -- Boolean: at least one CDE domain has data
        CASE WHEN
            ca_eligible_enrollment IS NOT NULL OR
            ar_students_with_absences IS NOT NULL OR
            en_cumulative_enrollment IS NOT NULL OR
            su_total_suspensions IS NOT NULL OR
            ex_total_expulsions IS NOT NULL OR
            hs_homeless_count IS NOT NULL OR
            frpm_enrollment_k12 IS NOT NULL OR
            ela_currstatus IS NOT NULL OR
            elpac_progressed_pct IS NOT NULL OR
            sbac_mean_scale_score IS NOT NULL OR
            rs_mechanical_restraints IS NOT NULL
        THEN TRUE ELSE FALSE END AS has_cde_data,

        -- Subgroup classification flags (from shared macro logic)
        CASE WHEN reporting_category LIKE 'R%' THEN TRUE ELSE FALSE END AS is_race_ethnicity_subgroup,
        CASE WHEN reporting_category IN ('GF', 'GM', 'GX') THEN TRUE ELSE FALSE END AS is_gender_subgroup,
        CASE WHEN reporting_category IN ('SE', 'EL', 'RFEP', 'IFEP', 'SWD', 'HOM', 'FOS', 'MIL') THEN TRUE ELSE FALSE END AS is_atrisk_subgroup,
        CASE WHEN reporting_category LIKE 'GR%' THEN TRUE ELSE FALSE END AS is_grade_level_subgroup,

        -- Aggregate level (always School in OBT)
        'S'::VARCHAR AS aggregate_level,
        'School'::VARCHAR AS aggregate_level_label

    FROM joined j
)

SELECT * FROM flagged