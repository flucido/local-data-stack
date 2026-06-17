-- models/staging/stg_attendance.sql
-- Staging: Standardize raw_attendance with schema normalization

{{ config(
    schema='staging',
    tags=['staging', 'attendance']
) }}

SELECT
    CAST(a.student_id AS VARCHAR) as student_id_raw,
    CAST(a.school_id AS VARCHAR) as school_id,
    '2024-2025' as academic_year,
    CAST(NULL AS VARCHAR) as attendance_program_code,

    -- Daily attendance flags
    CAST(a.present_flag AS BOOLEAN) as present_flag,
    CAST(a.absent_flag AS BOOLEAN) as absent_flag,
    CAST(a.tardy_flag AS BOOLEAN) as tardy_flag,
    CAST(a.excused_flag AS BOOLEAN) as excused_flag,
    CAST(a.unexcused_flag AS BOOLEAN) as unexcused_flag,
    CAST(a.absence_reason AS VARCHAR) as absence_reason,
    CAST(a.attendance_status AS VARCHAR) as attendance_status,

    -- Date-derived fields
    CAST(NULLIF(a.attendance_date, '') AS DATE) as attendance_date,
    DAYNAME(CAST(NULLIF(a.attendance_date, '') AS DATE)) as day_of_week_name,
    DAYOFWEEK(CAST(NULLIF(a.attendance_date, '') AS DATE)) as day_of_week_number,
    WEEK(CAST(NULLIF(a.attendance_date, '') AS DATE)) as week_of_year,
    MONTH(CAST(NULLIF(a.attendance_date, '') AS DATE)) as month_number,
    CASE
        WHEN DAYOFWEEK(CAST(NULLIF(a.attendance_date, '') AS DATE)) IN (0, 6) THEN true
        ELSE false
    END as is_weekend,
    CASE
        WHEN MONTH(CAST(NULLIF(a.attendance_date, '') AS DATE)) IN (8, 9, 10) THEN 1
        WHEN MONTH(CAST(NULLIF(a.attendance_date, '') AS DATE)) IN (11, 12, 1) THEN 2
        WHEN MONTH(CAST(NULLIF(a.attendance_date, '') AS DATE)) IN (2, 3) THEN 3
        ELSE 4
    END as school_quarter,

    -- Placeholder aggregated metrics (computed downstream)
    CAST(NULL AS DOUBLE) as attendance_rate,
    CAST(NULL AS DOUBLE) as absence_rate,
    CAST(NULL AS DOUBLE) as excused_absence_rate,

    -- Day counts (available in real Aeries data, NULL for synthetic)
    CAST(NULL AS INTEGER) as days_enrolled,
    CAST(NULL AS INTEGER) as days_present,
    CAST(NULL AS INTEGER) as days_absent,
    CAST(NULL AS INTEGER) as days_excused,
    CAST(NULL AS INTEGER) as days_unexcused,
    CAST(NULL AS INTEGER) as days_tardy,
    CAST(NULL AS INTEGER) as days_truancy,
    CAST(NULL AS INTEGER) as days_suspended,
    CAST(NULL AS INTEGER) as days_in_school_suspension,
    CAST(NULL AS INTEGER) as days_complete_independent_study,
    CAST(NULL AS INTEGER) as days_incomplete_independent_study,

    CAST(NULL AS INTEGER) as periods_expected,
    CAST(NULL AS INTEGER) as periods_attended,
    CAST(NULL AS INTEGER) as periods_excused_absence,
    CAST(NULL AS INTEGER) as periods_unexcused_absence,
    CAST(NULL AS INTEGER) as periods_out_of_school_suspension,
    CAST(NULL AS INTEGER) as periods_in_school_suspension,

    CURRENT_TIMESTAMP as dbt_load_timestamp,
    '{{ run_started_at }}' as dbt_run_timestamp
FROM {{ source('raw', 'raw_attendance') }} a
