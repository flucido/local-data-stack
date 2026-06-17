-- models/staging/stg_enrollment.sql
-- Staging: Standardize raw_enrollment with schema normalization

{{ config(
    schema='staging',
    tags=['staging', 'enrollment']
) }}

SELECT
    CAST(e.student_id AS VARCHAR) as student_id_raw,
    CAST(e.school_id AS VARCHAR) as school_id,
    CAST(e.school_year AS VARCHAR) as school_year,
    CAST(NULLIF(e.enrollment_date, '') AS DATE) as enrollment_date,
    CAST(NULL AS DATE) as withdrawal_date,
    CAST(e.grade_level AS INTEGER) as grade_level,
    CAST(e.enrollment_status AS VARCHAR) as enrollment_status,
    CURRENT_TIMESTAMP as dbt_load_timestamp,
    '{{ run_started_at }}' as dbt_run_timestamp
FROM {{ source('raw', 'raw_enrollment') }} e
