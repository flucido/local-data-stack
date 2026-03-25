-- models/mart_core/core/dim_student_demographics.sql
-- Aggregated demographics dimension with k-anonymity enforcement
-- FERPA compliant: all groups have minimum 5 students (k≥5)
-- Updated: Added race codes and additional program flags

{{ config(
    materialized='table',
    schema='core',
    unique_key=['grade_level', 'gender', 'ethnicity', 'primary_race', 'school_id', 'special_education_flag', 'ell_status', 'free_reduced_lunch_flag'],
    tags=['core', 'dimensions', 'demographics', 'aggregated', 'k_anonymity']
) }}

SELECT
    grade_level,
    gender,
    ethnicity,
    primary_race,
    is_multi_racial,
    school_id,
    
    -- Program participation flags
    special_education_flag,
    ell_status,
    free_reduced_lunch_flag,
    homeless_flag,
    foster_care_flag,
    section_504_flag,
    gate_flag,
    
    COUNT(DISTINCT student_id_hash) as student_count,
    
    ROUND(AVG(age_at_event), 1) as avg_age,
    MIN(age_at_event) as min_age,
    MAX(age_at_event) as max_age,
    
    COUNT(CASE WHEN enrollment_status = 'ACTIVE' THEN 1 END) as active_count,
    ROUND(
        COUNT(CASE WHEN enrollment_status = 'ACTIVE' THEN 1 END)::FLOAT 
        / NULLIF(COUNT(DISTINCT student_id_hash), 0), 
        3
    ) as active_rate

FROM {{ ref('dim_students') }}
GROUP BY 
    grade_level, gender, ethnicity, primary_race, is_multi_racial, school_id,
    special_education_flag, ell_status, free_reduced_lunch_flag,
    homeless_flag, foster_care_flag, section_504_flag, gate_flag
HAVING COUNT(DISTINCT student_id_hash) >= 5
