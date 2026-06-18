
-- models/mart_features/features/fct_chronic_absence_features.sql
-- Feature: Chronic absence risk indicators computed from daily attendance data.

{{ config(
    materialized='table',
    schema='features',
    unique_key='student_id_hash',
    tags=['features', 'attendance', 'chronic_absence']
) }}

WITH latest AS (
    SELECT MAX(CAST(attendance_date AS DATE)) AS latest_date
    FROM {{ source('raw', 'raw_attendance') }}
),

attendance_30d AS (
    SELECT
        sha256(CONCAT(
            COALESCE(ra.student_id::VARCHAR, ''),
            'oea_2026'
        ))                         AS student_id_hash,
        COUNT(*)                   AS days_enrolled,
        SUM(CASE WHEN CAST(ra.absent_flag AS BOOLEAN)    THEN 1 ELSE 0 END) AS days_absent,
        SUM(CASE WHEN CAST(ra.unexcused_flag AS BOOLEAN) THEN 1 ELSE 0 END) AS days_unexcused,
        SUM(CASE WHEN CAST(ra.tardy_flag AS BOOLEAN)     THEN 1 ELSE 0 END) AS days_tardy,
        ROUND(
            100.0 * SUM(CASE WHEN CAST(ra.present_flag AS BOOLEAN) THEN 1 ELSE 0 END)
            / NULLIF(COUNT(*), 0),
            2
        )                          AS attendance_rate_pct
    FROM {{ source('raw', 'raw_attendance') }} ra
    JOIN latest l
        ON CAST(ra.attendance_date AS DATE) >= l.latest_date - 30
    WHERE DAYOFWEEK(CAST(ra.attendance_date AS DATE)) NOT IN (0, 6)
    GROUP BY student_id_hash
),

attendance_90d AS (
    SELECT
        sha256(CONCAT(
            COALESCE(ra.student_id::VARCHAR, ''),
            'oea_2026'
        ))                         AS student_id_hash,
        COUNT(*)                   AS days_enrolled,
        SUM(CASE WHEN CAST(ra.absent_flag AS BOOLEAN)    THEN 1 ELSE 0 END) AS days_absent
    FROM {{ source('raw', 'raw_attendance') }} ra
    JOIN latest l
        ON CAST(ra.attendance_date AS DATE) >= l.latest_date - 90
    WHERE DAYOFWEEK(CAST(ra.attendance_date AS DATE)) NOT IN (0, 6)
    GROUP BY student_id_hash
),

attendance_annual AS (
    SELECT
        sha256(CONCAT(
            COALESCE(ra.student_id::VARCHAR, ''),
            'oea_2026'
        ))                         AS student_id_hash,
        COUNT(*)                   AS days_enrolled,
        SUM(CASE WHEN CAST(ra.absent_flag AS BOOLEAN) THEN 1 ELSE 0 END) AS days_absent,
        SUM(CASE WHEN CAST(ra.unexcused_flag AS BOOLEAN) THEN 1 ELSE 0 END) AS days_unexcused,
        SUM(CASE WHEN CAST(ra.tardy_flag AS BOOLEAN) THEN 1 ELSE 0 END) AS days_tardy
    FROM {{ source('raw', 'raw_attendance') }} ra
    WHERE DAYOFWEEK(CAST(ra.attendance_date AS DATE)) NOT IN (0, 6)
    GROUP BY student_id_hash
)

SELECT
    ds.student_id_hash,
    ds.school_id,
    ds.grade_level,

    COALESCE(a30.days_absent, 0)    AS days_absent_30d,
    COALESCE(a90.days_absent, 0)    AS days_absent_90d,
    COALESCE(aa.days_unexcused, 0)  AS unexcused_absences_total,
    COALESCE(aa.days_tardy, 0)      AS tardies_total,
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
LEFT JOIN attendance_30d    a30 ON ds.student_id_hash = a30.student_id_hash
LEFT JOIN attendance_90d    a90 ON ds.student_id_hash = a90.student_id_hash
LEFT JOIN attendance_annual aa  ON ds.student_id_hash = aa.student_id_hash
