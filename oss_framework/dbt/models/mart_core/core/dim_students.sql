-- models/mart_core/core/dim_students.sql
-- Dimension: Pseudonymized student demographics and attributes
-- Updated: Added race codes (RC1-RC5) and additional program flags

{{ config(
    materialized='table',
    schema='core',
    unique_key='student_id_hash',
    tags=['core', 'dimensions', 'students']
) }}

SELECT
    -- Hashed identifiers
    psh.student_id_hash,
    
    -- Demographics (no PII)
    psh.age_at_event,
    psh.gender,
    psh.ethnicity,
    -- Race codes (Aeries Race Categories)
    psh.race_code_1,
    psh.race_code_2,
    psh.race_code_3,
    psh.race_code_4,
    psh.race_code_5,
    -- Derived race description (Aeries codes)
    -- Note: These are Aeries-specific codes, not federal CALPADS codes
    -- 700=White, 600=Hispanic, 100=American Indian, 200s=Asian, 300s=Black, 400=Pacific Islander
    CASE 
        WHEN psh.race_code_1 IN ('700', '700.0') THEN 'White'
        WHEN psh.race_code_1 IN ('600', '600.0') THEN 'Hispanic/Latino'
        WHEN psh.race_code_1 IN ('100', '100.0') THEN 'American Indian/Alaska Native'
        WHEN psh.race_code_1 LIKE '2%' THEN 'Asian'
        WHEN psh.race_code_1 LIKE '3%' THEN 'Black/African American'
        WHEN psh.race_code_1 IN ('400', '400.0') THEN 'Native Hawaiian/Pacific Islander'
        WHEN psh.race_code_1 IN ('0', '0.0') THEN 'Not Specified'
        ELSE 'Other/Unknown'
    END as primary_race,
    -- Multi-race indicator
    CASE 
        WHEN psh.race_code_2 IS NOT NULL AND psh.race_code_2 != '' THEN true
        ELSE false
    END as is_multi_racial,
    psh.grade_level,
    psh.school_id,
    psh.academic_year,
    psh.home_language,
    
    -- Program participation flags
    psh.special_education_flag,
    psh.ell_status,
    psh.free_reduced_lunch_flag,
    psh.homeless_flag,
    psh.foster_care_flag,
    psh.section_504_flag,
    psh.gate_flag,
    psh.ell_program_flag,
    
    -- Cohort tracking
    CASE 
        WHEN psh.grade_level = 9 THEN 'FRESHMAN'
        WHEN psh.grade_level = 10 THEN 'SOPHOMORE'
        WHEN psh.grade_level = 11 THEN 'JUNIOR'
        WHEN psh.grade_level = 12 THEN 'SENIOR'
        ELSE 'OTHER'
    END as cohort,
    
    -- Risk indicators
    psh.special_education_flag OR psh.section_504_flag as high_need_flag,
    psh.ell_status != '' as language_support_needed,
    psh.free_reduced_lunch_flag as socioeconomic_risk,
    psh.homeless_flag as housing_risk,
    
    -- Enrollment status
    CASE 
        WHEN psh.enrollment_date IS NOT NULL AND psh.withdrawal_date IS NULL THEN 'ACTIVE'
        WHEN psh.withdrawal_date IS NOT NULL AND psh.withdrawal_date <= CURRENT_DATE THEN 'WITHDRAWN'
        ELSE 'UNKNOWN'
    END as enrollment_status,
    
    -- Audit
    psh.pseudonymization_timestamp,
    CURRENT_TIMESTAMP as dbt_processed_date

FROM {{ ref('priv_student_hashes') }} psh
