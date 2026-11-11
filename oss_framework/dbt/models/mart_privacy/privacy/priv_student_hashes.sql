-- models/mart_privacy/privacy/priv_student_hashes.sql
-- Pseudonymization: Hash student identifiers for privacy compliance (no masked names)

{{ config(
    materialized='table',
    schema='privacy',
    unique_key=['student_id_hash', 'academic_year'],
    tags=['privacy', 'pseudonymization']
) }}

SELECT
    -- Hashed identifier (deterministic, allows linkage)
    {{ hash_pii_secure('student_id_raw') }} as student_id_hash,

    -- Demographics (no PII)
    gender,
    ethnicity,
    race_code_1,
    race_code_2,
    race_code_3,
    race_code_4,
    race_code_5,
    grade_level,
    school_id,
    academic_year,
    -- Program participation flags
    special_education_flag,
    ell_status,
    free_reduced_lunch_flag,
    homeless_flag,
    foster_care_flag,
    section_504_flag,
    gate_flag,
    ell_program_flag,
    home_language,

    -- Age at event (uses pre-computed integer age from staging)
    age as age_at_event,

    -- Enrollment tracking
    enrollment_date,
    withdrawal_date,

    -- Audit
    CAST(NULL AS TIMESTAMP) as created_at,
    CURRENT_TIMESTAMP as pseudonymization_timestamp,
    'HMAC_SHA256_HASHED' as pseudonymization_method

FROM {{ ref('stg_aeries__students') }}
