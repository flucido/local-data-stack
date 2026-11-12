-- models/mart_features/features/fct_chronic_absence_features.sql
-- Feature: Chronic absence risk indicators computed from daily attendance data at (student_id_hash, academic_year) grain.

{{ config(
    materialized='table',
    schema='features',
    unique_key=['student_id_hash', 'academic_year'],
    tags=['features', 'attendance', 'chronic_absence']
) }}

WITH base_daily AS (
    SELECT
        {{ hash_pii_secure('ra.student_id') }} AS student_id_hash,
        CASE
            WHEN TRY_CAST(ra.attendance_date AS DATE) IS NOT NULL THEN
                CASE
                    WHEN MONTH(TRY_CAST(ra.attendance_date AS DATE)) >= 7
                        THEN CAST(YEAR(TRY_CAST(ra.attendance_date AS DATE)) AS VARCHAR) || '-' || CAST(YEAR(TRY_CAST(ra.attendance_date AS DATE)) + 1 AS VARCHAR)
                    ELSE CAST(YEAR(TRY_CAST(ra.attendance_date AS DATE)) - 1 AS VARCHAR) || '-' || CAST(YEAR(TRY_CAST(ra.attendance_date AS DATE)) AS VARCHAR)
                END
            ELSE '2024-2025'
        END AS academic_year,
        CAST(ra.attendance_date AS DATE) AS attendance_date,
        CAST(ra.present_flag AS BOOLEAN) AS present_flag,
        CAST(ra.absent_flag AS BOOLEAN) AS absent_flag,
        CAST(ra.unexcused_flag AS BOOLEAN) AS unexcused_flag,
        CAST(ra.tardy_flag AS BOOLEAN) AS tardy_flag
    FROM {{ source('raw', 'raw_attendance') }} ra
    WHERE DAYOFWEEK(CAST(ra.attendance_date AS DATE)) NOT IN (0, 6)
),

latest_by_year AS (
    SELECT
        academic_year,
        MAX(attendance_date) AS latest_date
    FROM base_daily
    GROUP BY academic_year
),

attendance_30d AS (
    SELECT
        bd.student_id_hash,
        bd.academic_year,
        COUNT(*) AS days_enrolled,
        SUM(CASE WHEN bd.absent_flag THEN 1 ELSE 0 END) AS days_absent,
        SUM(CASE WHEN bd.unexcused_flag THEN 1 ELSE 0 END) AS days_unexcused,
        SUM(CASE WHEN bd.tardy_flag THEN 1 ELSE 0 END) AS days_tardy,
        ROUND(
            100.0 * SUM(CASE WHEN bd.present_flag THEN 1 ELSE 0 END)
            / NULLIF(COUNT(*), 0),
            2
        ) AS attendance_rate_pct
    FROM base_daily bd
    JOIN latest_by_year l
        ON bd.academic_year = l.academic_year
       AND bd.attendance_date >= l.latest_date - 30
    GROUP BY bd.student_id_hash, bd.academic_year
),

attendance_90d AS (
    SELECT
        bd.student_id_hash,
        bd.academic_year,
        COUNT(*) AS days_enrolled,
        SUM(CASE WHEN bd.absent_flag THEN 1 ELSE 0 END) AS days_absent
    FROM base_daily bd
    JOIN latest_by_year l
        ON bd.academic_year = l.academic_year
       AND bd.attendance_date >= l.latest_date - 90
    GROUP BY bd.student_id_hash, bd.academic_year
),

attendance_annual AS (
    SELECT
        bd.student_id_hash,
        bd.academic_year,
        COUNT(*) AS days_enrolled,
        SUM(CASE WHEN bd.absent_flag THEN 1 ELSE 0 END) AS days_absent,
        SUM(CASE WHEN bd.unexcused_flag THEN 1 ELSE 0 END) AS days_unexcused,
        SUM(CASE WHEN bd.tardy_flag THEN 1 ELSE 0 END) AS days_tardy
    FROM base_daily bd
    GROUP BY bd.student_id_hash, bd.academic_year
)

SELECT
    ds.student_id_hash,
    ds.academic_year,
    ds.school_id,
    ds.grade_level,

    COALESCE(a30.days_absent, 0) AS days_absent_30d,
    COALESCE(a90.days_absent, 0) AS days_absent_90d,
    COALESCE(aa.days_unexcused, 0) AS unexcused_absences_total,
    COALESCE(aa.days_tardy, 0) AS tardies_total,
    COALESCE(a30.attendance_rate_pct, 100.0) AS attendance_rate_30d,

    ds.special_education_flag,
    ds.ell_status,
    ds.free_reduced_lunch_flag,
    ds.homeless_flag,

    CASE
        WHEN aa.days_enrolled > 0
         AND (aa.days_absent * 1.0 / aa.days_enrolled) >= 0.10
        THEN TRUE
        ELSE FALSE
    END AS chronic_absence_flag,

    CURRENT_TIMESTAMP AS dbt_processed_date

FROM {{ ref('dim_students') }} ds
LEFT JOIN attendance_30d a30
    ON ds.student_id_hash = a30.student_id_hash
   AND ds.academic_year = a30.academic_year
LEFT JOIN attendance_90d a90
    ON ds.student_id_hash = a90.student_id_hash
   AND ds.academic_year = a90.academic_year
LEFT JOIN attendance_annual aa
    ON ds.student_id_hash = aa.student_id_hash
   AND ds.academic_year = aa.academic_year
