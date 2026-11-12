-- models/staging/aeries/stg_aeries__students.sql
-- Staging: Standardize raw_students with schema normalization

{{ config(
    schema='staging',
    tags=['staging', 'students']
) }}

{% set raw_cols = (adapter.get_columns_in_relation(source('raw', 'raw_students')) | map(attribute='name') | map('lower') | list) if execute else [] %}

SELECT
    -- Identifiers (will be hashed in privacy layer)
    CAST(s.student_id AS VARCHAR) as student_id_raw,
    CAST(s.first_name AS VARCHAR) as first_name_raw,
    CAST(s.last_name AS VARCHAR) as last_name_raw,
    CAST(NULLIF(CAST(s.date_of_birth AS VARCHAR), '') AS DATE) as date_of_birth_raw,
    -- Demographics
    CAST(s.gender AS VARCHAR) as gender,
    CAST(s.ethnicity AS VARCHAR) as ethnicity,
    -- Race codes (use source race_code_1 if present, else derive from ethnicity)
    {% if 'race_code_1' in raw_cols %}
    COALESCE(
        NULLIF(CAST(s.race_code_1 AS VARCHAR), ''),
        CASE
            WHEN LOWER(COALESCE(CAST(s.ethnicity AS VARCHAR), '')) LIKE '%white%' THEN '700'
            WHEN LOWER(COALESCE(CAST(s.ethnicity AS VARCHAR), '')) LIKE '%hispanic%' OR LOWER(COALESCE(CAST(s.ethnicity AS VARCHAR), '')) LIKE '%latino%' THEN '600'
            WHEN LOWER(COALESCE(CAST(s.ethnicity AS VARCHAR), '')) LIKE '%black%' OR LOWER(COALESCE(CAST(s.ethnicity AS VARCHAR), '')) LIKE '%african%' THEN '300'
            WHEN LOWER(COALESCE(CAST(s.ethnicity AS VARCHAR), '')) LIKE '%asian%' THEN '200'
            WHEN LOWER(COALESCE(CAST(s.ethnicity AS VARCHAR), '')) LIKE '%indian%' OR LOWER(COALESCE(CAST(s.ethnicity AS VARCHAR), '')) LIKE '%native%' THEN '100'
            WHEN LOWER(COALESCE(CAST(s.ethnicity AS VARCHAR), '')) LIKE '%pacific%' OR LOWER(COALESCE(CAST(s.ethnicity AS VARCHAR), '')) LIKE '%hawaiian%' THEN '400'
            ELSE '0'
        END
    ) as race_code_1,
    {% else %}
    CASE
        WHEN LOWER(COALESCE(CAST(s.ethnicity AS VARCHAR), '')) LIKE '%white%' THEN '700'
        WHEN LOWER(COALESCE(CAST(s.ethnicity AS VARCHAR), '')) LIKE '%hispanic%' OR LOWER(COALESCE(CAST(s.ethnicity AS VARCHAR), '')) LIKE '%latino%' THEN '600'
        WHEN LOWER(COALESCE(CAST(s.ethnicity AS VARCHAR), '')) LIKE '%black%' OR LOWER(COALESCE(CAST(s.ethnicity AS VARCHAR), '')) LIKE '%african%' THEN '300'
        WHEN LOWER(COALESCE(CAST(s.ethnicity AS VARCHAR), '')) LIKE '%asian%' THEN '200'
        WHEN LOWER(COALESCE(CAST(s.ethnicity AS VARCHAR), '')) LIKE '%indian%' OR LOWER(COALESCE(CAST(s.ethnicity AS VARCHAR), '')) LIKE '%native%' THEN '100'
        WHEN LOWER(COALESCE(CAST(s.ethnicity AS VARCHAR), '')) LIKE '%pacific%' OR LOWER(COALESCE(CAST(s.ethnicity AS VARCHAR), '')) LIKE '%hawaiian%' THEN '400'
        ELSE '0'
    END as race_code_1,
    {% endif %}
    {% if 'race_code_2' in raw_cols %}CAST(s.race_code_2 AS VARCHAR){% else %}CAST(NULL AS VARCHAR){% endif %} as race_code_2,
    {% if 'race_code_3' in raw_cols %}CAST(s.race_code_3 AS VARCHAR){% else %}CAST(NULL AS VARCHAR){% endif %} as race_code_3,
    {% if 'race_code_4' in raw_cols %}CAST(s.race_code_4 AS VARCHAR){% else %}CAST(NULL AS VARCHAR){% endif %} as race_code_4,
    {% if 'race_code_5' in raw_cols %}CAST(s.race_code_5 AS VARCHAR){% else %}CAST(NULL AS VARCHAR){% endif %} as race_code_5,
    CAST(s.grade_level AS INTEGER) as grade_level,
    CAST(s.school_id AS VARCHAR) as school_id,
    COALESCE(
        {% if 'academic_year' in raw_cols %}NULLIF(CAST(s.academic_year AS VARCHAR), ''),{% endif %}
        {% if 'school_year' in raw_cols %}NULLIF(CAST(s.school_year AS VARCHAR), ''),{% endif %}
        CASE
            WHEN TRY_CAST(NULLIF(CAST(s.enrollment_date AS VARCHAR), '') AS DATE) IS NOT NULL THEN
                CASE
                    WHEN MONTH(TRY_CAST(NULLIF(CAST(s.enrollment_date AS VARCHAR), '') AS DATE)) >= 7
                        THEN CAST(YEAR(TRY_CAST(NULLIF(CAST(s.enrollment_date AS VARCHAR), '') AS DATE)) AS VARCHAR) || '-' || CAST(YEAR(TRY_CAST(NULLIF(CAST(s.enrollment_date AS VARCHAR), '') AS DATE)) + 1 AS VARCHAR)
                    ELSE CAST(YEAR(TRY_CAST(NULLIF(CAST(s.enrollment_date AS VARCHAR), '') AS DATE)) - 1 AS VARCHAR) || '-' || CAST(YEAR(TRY_CAST(NULLIF(CAST(s.enrollment_date AS VARCHAR), '') AS DATE)) AS VARCHAR)
                END
            ELSE NULL
        END,
        '2024-2025'
    ) as academic_year,
    -- Calculated demographics
    TRY_CAST(DATE_PART('year', AGE(CURRENT_DATE, TRY_CAST(NULLIF(CAST(s.date_of_birth AS VARCHAR), '') AS DATE))) AS INTEGER) as age,
    CASE
        WHEN TRY_CAST(s.grade_level AS INTEGER) BETWEEN 1 AND 5 THEN 'Elementary'
        WHEN TRY_CAST(s.grade_level AS INTEGER) BETWEEN 6 AND 8 THEN 'Middle'
        WHEN TRY_CAST(s.grade_level AS INTEGER) BETWEEN 9 AND 12 THEN 'High'
        ELSE 'Unknown'
    END as grade_level_category,

    -- Enrollment status flags
    CAST(NULL AS VARCHAR) as attendance_program_code,
    COALESCE(TRY_CAST(s.ell_status AS BOOLEAN), FALSE) as ell_status,
    COALESCE(TRY_CAST(s.special_education AS BOOLEAN), FALSE) as special_education_flag,
    COALESCE(TRY_CAST(s.free_reduced_lunch AS BOOLEAN), FALSE) as free_reduced_lunch_flag,
    COALESCE(TRY_CAST(s.homeless AS BOOLEAN), FALSE) as homeless_flag,
    COALESCE(TRY_CAST(s.foster_care AS BOOLEAN), FALSE) as foster_care_flag,
    COALESCE(TRY_CAST(s.section_504 AS BOOLEAN), FALSE) as section_504_flag,
    false as gate_flag,
    COALESCE(TRY_CAST(s.ell_status AS BOOLEAN), FALSE) as ell_program_flag,
    -- Language
    COALESCE(CAST(s.home_language AS VARCHAR), 'E') as home_language,
    -- Enrollment dates
    TRY_CAST(NULLIF(CAST(s.enrollment_date AS VARCHAR), '') AS DATE) as enrollment_date,
    {% if 'withdrawal_date' in raw_cols %}TRY_CAST(NULLIF(CAST(s.withdrawal_date AS VARCHAR), '') AS DATE){% else %}CAST(NULL AS DATE){% endif %} as withdrawal_date,
    -- Calculated enrollment status
    true as is_currently_enrolled,
    CURRENT_TIMESTAMP as dbt_load_timestamp,
    '{{ run_started_at }}' as dbt_run_timestamp
FROM {{ source('raw', 'raw_students') }} s
