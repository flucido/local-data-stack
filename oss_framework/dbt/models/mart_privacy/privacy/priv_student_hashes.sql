-- models/mart_privacy/privacy/priv_student_hashes.sql
-- Pseudonymization: Hash student identifiers for privacy compliance
-- Maintains ability to link records while protecting PII
-- Updated: Added race codes (RC1-RC5) and additional program flags

{{ config(
    materialized='table',
    schema='privacy',
    unique_key='student_id_hash',
    tags=['privacy', 'pseudonymization']
) }}

SELECT
    -- Hashed identifier (deterministic, allows linkage)
    {{ hash_pii_secure('student_id_raw') }} as student_id_hash,
    
    -- Masked PII (irreversible, display only)
    {{ mask_name('first_name_raw', 1) }} as first_name_masked,
    {{ mask_name('last_name_raw', 1) }} as last_name_masked,
    
    -- Demographics (no hashing needed - not PII)
    gender,
    ethnicity,
    -- Race codes (Federal Race Categories - up to 5 races per student)
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
    
    -- Age at event (not DOB - better privacy)
    CAST(EXTRACT(YEAR FROM CURRENT_DATE) - EXTRACT(YEAR FROM date_of_birth_raw) AS INTEGER) as age_at_event,
    
    -- Enrollment tracking
    enrollment_date,
    withdrawal_date,
    
    -- Audit
    CAST(NULL AS TIMESTAMP) as created_at,
    CURRENT_TIMESTAMP as pseudonymization_timestamp,
    'SHA256_HASHED_AND_MASKED' as pseudonymization_method

FROM {{ ref('stg_aeries__students') }}
