-- models/staging/stg_students.sql
-- Staging: Standardize raw_students with schema normalization
-- Light transformations: age calculation, enrollment status, grade categorization

{{ config(
    schema='staging',
    tags=['staging', 'students']
) }}

SELECT
    -- Identifiers (will be hashed in privacy layer)
    CAST(s.student_id AS VARCHAR) as student_id_raw,
    CAST(s.first_name AS VARCHAR) as first_name_raw,
    CAST(s.last_name AS VARCHAR) as last_name_raw,
    CAST(NULLIF(s.date_of_birth, '') AS DATE) as date_of_birth_raw,
    -- Demographics
    CAST(s.gender AS VARCHAR) as gender,
    CAST(s.ethnicity AS VARCHAR) as ethnicity,
    -- Race codes (not present in synthetic test data)
    CAST(NULL AS VARCHAR) as race_code_1,
    CAST(NULL AS VARCHAR) as race_code_2,
    CAST(NULL AS VARCHAR) as race_code_3,
    CAST(NULL AS VARCHAR) as race_code_4,
    CAST(NULL AS VARCHAR) as race_code_5,
    CAST(s.grade_level AS INTEGER) as grade_level,
    CAST(s.school_id AS VARCHAR) as school_id,
    '2024-2025' as academic_year,
    -- Calculated demographics
    TRY_CAST(DATE_PART('year', AGE(CURRENT_DATE, CAST(NULLIF(s.date_of_birth, '') AS DATE))) AS INTEGER) as age,
    CASE
        WHEN TRY_CAST(s.grade_level AS INTEGER) BETWEEN 1 AND 5 THEN 'Elementary'
        WHEN TRY_CAST(s.grade_level AS INTEGER) BETWEEN 6 AND 8 THEN 'Middle'
        WHEN TRY_CAST(s.grade_level AS INTEGER) BETWEEN 9 AND 12 THEN 'High'
        ELSE 'Unknown'
    END as grade_level_category,

    -- Enrollment status flags
    CAST(NULL AS VARCHAR) as attendance_program_code,
    CASE WHEN s.ell_status = 'True' OR s.ell_status = 'true' THEN true ELSE false END as ell_status,
    CAST(s.special_education AS BOOLEAN) as special_education_flag,
    CAST(s.free_reduced_lunch AS BOOLEAN) as free_reduced_lunch_flag,
    CAST(s.homeless AS BOOLEAN) as homeless_flag,
    CAST(s.foster_care AS BOOLEAN) as foster_care_flag,
    CAST(s.section_504 AS BOOLEAN) as section_504_flag,
    false as gate_flag,
    false as ell_program_flag,
    -- Language
    COALESCE(CAST(s.home_language AS VARCHAR), 'E') as home_language,
    -- Enrollment dates
    CAST(NULLIF(s.enrollment_date, '') AS DATE) as enrollment_date,
    CAST(NULL AS DATE) as withdrawal_date,
    -- Calculated enrollment status
    true as is_currently_enrolled,
    CURRENT_TIMESTAMP as dbt_load_timestamp,
    '{{ run_started_at }}' as dbt_run_timestamp
FROM {{ source('raw', 'raw_students') }} s
