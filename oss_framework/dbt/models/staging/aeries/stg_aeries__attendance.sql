-- models/staging/stg_attendance.sql
-- Staging: Aggregate raw daily attendance into student-level summaries.
-- Raw data is daily grain (one row per student per day). This model
-- aggregates to one row per student per academic year, computing
-- days_present, days_absent, attendance_rate, etc. from the daily flags.

{{ config(
    schema='staging',
    tags=['staging', 'attendance']
) }}

WITH daily AS (
    SELECT
        CAST(student_id AS VARCHAR) as student_id_raw,
        CAST(school_id AS VARCHAR) as school_id,
        '2024-2025' as academic_year,
        CAST(present_flag AS BOOLEAN) as present_flag,
        CAST(absent_flag AS BOOLEAN) as absent_flag,
        CAST(tardy_flag AS BOOLEAN) as tardy_flag,
        CAST(excused_flag AS BOOLEAN) as excused_flag,
        CAST(unexcused_flag AS BOOLEAN) as unexcused_flag,
        CAST(NULLIF(attendance_date, '') AS DATE) as attendance_date
    FROM {{ source('raw', 'raw_attendance') }}
    WHERE DAYOFWEEK(CAST(NULLIF(attendance_date, '') AS DATE)) NOT IN (0, 6)  -- exclude weekends
),

aggregated AS (
    SELECT
        student_id_raw,
        school_id,
        academic_year,

        -- Day counts
        COUNT(*) as days_enrolled,
        SUM(CASE WHEN present_flag THEN 1 ELSE 0 END) as days_present,
        SUM(CASE WHEN absent_flag THEN 1 ELSE 0 END) as days_absent,
        SUM(CASE WHEN excused_flag THEN 1 ELSE 0 END) as days_excused,
        SUM(CASE WHEN unexcused_flag THEN 1 ELSE 0 END) as days_unexcused,
        SUM(CASE WHEN tardy_flag THEN 1 ELSE 0 END) as days_tardy,

        -- Truancy / suspension not in synthetic data — default to 0
        0 as days_truancy,
        0 as days_suspended,
        0 as days_in_school_suspension,
        0 as days_complete_independent_study,
        0 as days_incomplete_independent_study,

        -- Period-based not in synthetic data — default to NULL
        CAST(NULL AS INTEGER) as periods_expected,
        CAST(NULL AS INTEGER) as periods_attended,
        CAST(NULL AS INTEGER) as periods_excused_absence,
        CAST(NULL AS INTEGER) as periods_unexcused_absence,
        CAST(NULL AS INTEGER) as periods_out_of_school_suspension,
        CAST(NULL AS INTEGER) as periods_in_school_suspension

    FROM daily
    GROUP BY student_id_raw, school_id, academic_year
)

SELECT
    student_id_raw,
    school_id,
    academic_year,
    CAST(NULL AS VARCHAR) as attendance_program_code,

    -- Daily flags not meaningful at student grain (aggregated away)
    CAST(NULL AS BOOLEAN) as present_flag,
    CAST(NULL AS BOOLEAN) as absent_flag,
    CAST(NULL AS BOOLEAN) as tardy_flag,
    CAST(NULL AS BOOLEAN) as excused_flag,
    CAST(NULL AS BOOLEAN) as unexcused_flag,
    CAST(NULL AS VARCHAR) as absence_reason,
    CAST(NULL AS VARCHAR) as attendance_status,
    CAST(NULL AS DATE) as attendance_date,
    CAST(NULL AS VARCHAR) as day_of_week_name,
    CAST(NULL AS INTEGER) as day_of_week_number,
    CAST(NULL AS INTEGER) as week_of_year,
    CAST(NULL AS INTEGER) as month_number,
    CAST(NULL AS BOOLEAN) as is_weekend,
    CAST(NULL AS INTEGER) as school_quarter,

    -- Calculated rates (now populated!)
    ROUND(days_present::DOUBLE / NULLIF(days_enrolled, 0), 4) as attendance_rate,
    ROUND(days_absent::DOUBLE / NULLIF(days_enrolled, 0), 4) as absence_rate,
    ROUND(days_excused::DOUBLE / NULLIF(days_enrolled, 0), 4) as excused_absence_rate,

    -- Day counts (now populated!)
    days_enrolled,
    days_present,
    days_absent,
    days_excused,
    days_unexcused,
    days_tardy,
    days_truancy,
    days_suspended,
    days_in_school_suspension,
    days_complete_independent_study,
    days_incomplete_independent_study,

    periods_expected,
    periods_attended,
    periods_excused_absence,
    periods_unexcused_absence,
    periods_out_of_school_suspension,
    periods_in_school_suspension,

    CURRENT_TIMESTAMP as dbt_load_timestamp,
    '{{ run_started_at }}' as dbt_run_timestamp
FROM aggregated
