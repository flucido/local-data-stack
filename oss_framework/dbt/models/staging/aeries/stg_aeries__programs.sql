-- models/staging/stg_aeries__programs.sql
-- Staging: Standardize raw_aeries_programs with schema normalization
-- Provides program participation data for student demographics

{{ config(
    schema='staging',
    tags=['staging', 'programs']
) }}

SELECT
    CAST(StudentID AS VARCHAR) as student_id_raw,
    CAST(ProgramCode AS VARCHAR) as program_code,
    CAST(ProgramDescription AS VARCHAR) as program_description,
    CAST(AcademicYear AS VARCHAR) as academic_year,
    CAST(EligibilityStartDate AS DATE) as eligibility_start_date,
    CAST(EligibilityEndDate AS DATE) as eligibility_end_date,
    CAST(ParticipationStartDate AS DATE) as participation_start_date,
    CAST(ParticipationEndDate AS DATE) as participation_end_date,
    CASE
        WHEN ParticipationEndDate IS NULL THEN true
        ELSE false
    END as is_currently_active,
    CAST(ProgramDescription AS VARCHAR) as program_category,
    CURRENT_TIMESTAMP as dbt_load_timestamp,
    '{{ run_started_at }}' as dbt_run_timestamp
FROM {{ source('raw', 'raw_aeries_programs') }}
