{{ config(
    materialized='table',
    schema='analytics'
) }}

-- NOTE: fact_attendance provides annual-grain summaries. Internal metrics are
-- computed from annual aggregate counts (days_present, days_absent, days_enrolled).
-- CDE benchmarks report chronic absenteeism rates (% of students chronically absent).
-- This model compares chronic absence rates (apples-to-apples) rather than
-- mixing attendance rate with chronic absence rate.

WITH internal_schools AS (
    SELECT
        school_id,
        school_name,
        cds_code,
        cde_district_name,
        cde_city,
        cde_county,
        latitude,
        longitude
    FROM {{ ref('dim_schools') }}
    WHERE cds_code IS NOT NULL
),

school_attendance_rates AS (
    SELECT
        fa.school_id,
        COUNT(DISTINCT fa.student_id_hash) as our_student_count,
        SUM(fa.days_present) as present_days,
        SUM(fa.days_absent) as absent_days,
        SUM(fa.days_enrolled) as total_enrolled_days,
        ROUND(
            100.0 * SUM(fa.days_present) /
            NULLIF(SUM(fa.days_enrolled), 0),
            2
        ) as our_attendance_rate_pct,
        ROUND(
            100.0 * SUM(fa.days_absent) /
            NULLIF(SUM(fa.days_enrolled), 0),
            2
        ) as our_absence_rate_pct
    FROM {{ ref('fact_attendance') }} fa
    WHERE fa.days_enrolled > 0
    GROUP BY fa.school_id
),

student_level_chronic_absence AS (
    SELECT
        fa.school_id,
        fa.student_id_hash,
        fa.days_enrolled as enrolled_days,
        fa.days_absent as total_absences,
        CASE
            WHEN fa.days_enrolled > 0
                 AND (100.0 * fa.days_absent / fa.days_enrolled) >= 10.0
            THEN 1
            ELSE 0
        END as is_chronically_absent
    FROM {{ ref('fact_attendance') }} fa
    WHERE fa.days_enrolled > 0
),

school_chronic_absence_rollup AS (
    SELECT
        school_id,
        SUM(is_chronically_absent) as our_chronic_absent_count,
        ROUND(
            100.0 * SUM(is_chronically_absent) / NULLIF(COUNT(DISTINCT student_id_hash), 0),
            2
        ) as our_chronic_absent_rate_pct
    FROM student_level_chronic_absence
    GROUP BY school_id
),

cde_benchmarks AS (
    SELECT
        cds_code,
        academic_year,
        eligible_enrollment as cde_student_count,
        chronic_absent_count as cde_chronic_absent_count,
        chronic_absent_rate_pct as cde_chronic_absent_rate_pct
    FROM {{ ref('stg_cde__chronic_absenteeism') }}
    WHERE aggregate_level = 'S'
    AND reporting_category = 'TA'
    AND NOT is_suppressed
),

joined AS (
    SELECT
        -- School identifiers
        sch.school_id,
        sch.school_name,
        sch.cds_code,
        sch.cde_district_name as district_name,
        sch.cde_city as city,
        sch.cde_county as county,
        sch.latitude,
        sch.longitude,

        -- CDE benchmarks (chronic absence rates only - comparable metric)
        cde.academic_year as cde_academic_year,
        cde.cde_student_count,
        cde.cde_chronic_absent_count,
        cde.cde_chronic_absent_rate_pct,

        -- Internal metrics
        att.our_student_count,
        att.our_attendance_rate_pct,
        att.our_absence_rate_pct,
        ca.our_chronic_absent_count,
        ca.our_chronic_absent_rate_pct,

        -- Gap analysis (chronic absence rate: apples-to-apples comparison)
        ca.our_chronic_absent_rate_pct - cde.cde_chronic_absent_rate_pct as chronic_absent_rate_gap_pct,

        -- Performance flags (using comparable chronic absence metric)
        CASE
            WHEN ca.our_chronic_absent_rate_pct < cde.cde_chronic_absent_rate_pct THEN 'Better than State'
            WHEN ca.our_chronic_absent_rate_pct > cde.cde_chronic_absent_rate_pct THEN 'Worse than State'
            ELSE 'Same as State'
        END as chronic_absence_comparison,

        -- Data quality flags
        CASE WHEN att.our_student_count IS NULL THEN TRUE ELSE FALSE END as missing_internal_data,
        CASE WHEN cde.cde_student_count IS NULL THEN TRUE ELSE FALSE END as missing_cde_data,
        ABS(COALESCE(att.our_student_count, 0) - COALESCE(cde.cde_student_count, 0)) as enrollment_difference,
        CASE
            WHEN ABS(COALESCE(att.our_student_count, 0) - COALESCE(cde.cde_student_count, 0)) > 50 THEN TRUE
            ELSE FALSE
        END as large_enrollment_discrepancy

    FROM internal_schools sch
    LEFT JOIN school_attendance_rates att ON sch.school_id = att.school_id
    LEFT JOIN school_chronic_absence_rollup ca ON sch.school_id = ca.school_id
    LEFT JOIN cde_benchmarks cde ON sch.cds_code = cde.cds_code
)

SELECT
    *,
    -- Summary flags for filtering
    CASE
        WHEN missing_internal_data OR missing_cde_data THEN 'Incomplete Data'
        WHEN large_enrollment_discrepancy THEN 'Data Quality Issue'
        WHEN chronic_absence_comparison = 'Worse than State' THEN 'Needs Improvement'
        WHEN chronic_absence_comparison = 'Better than State' THEN 'Outperforming State'
        ELSE 'On Par with State'
    END as overall_status
FROM joined
