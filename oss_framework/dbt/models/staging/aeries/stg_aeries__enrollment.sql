
-- models/staging/stg_enrollment.sql
-- Staging: Standardize raw_enrollment with schema normalization

{{ config(
    schema='staging',
    tags=['staging', 'enrollment']
) }}

SELECT
    CAST(StudentID AS VARCHAR) as student_id_raw,
    CAST(SchoolCode AS VARCHAR) as school_id,
    CAST(StudentNumber AS VARCHAR) as student_number,
    CAST(AcademicYear AS VARCHAR) as school_year,
    CAST(Grade AS INTEGER) as grade_level,
    CAST(Track AS VARCHAR) as track,
    CAST(EnterDate AS DATE) as enrollment_date,
    CAST(LeaveDate AS DATE) as withdrawal_date,
    CAST(ExitReasonCode AS VARCHAR) as exit_reason_code,

    CASE
        WHEN LeaveDate IS NULL THEN 'ACTIVE'
        ELSE 'WITHDRAWN'
    END as enrollment_status,

    CAST(AttendanceProgramCode AS VARCHAR) as attendance_program_code,
    CAST(AttendanceProgramCodeAdditional1 AS VARCHAR) as attendance_program_code_add1,

    CURRENT_TIMESTAMP as dbt_load_timestamp,
    '{{ run_started_at }}' as dbt_run_timestamp
FROM {{ source('raw', 'raw_enrollment') }}
