-- models/mart_analytics/hex_ready/apex_math_8_enrollment_by_year.sql
-- 7th Grade Apex Math 8 Enrollment by Year with Demographics
-- Course code 329 (000329 in Aeries)

{{ config(
    materialized='table',
    schema='analytics',
    tags=['analytics', 'hex', 'enrollment', 'apex']
) }}

SELECT 
    ar.school_year,
    d.primary_race,
    d.gender,
    d.is_multi_racial,
    COUNT(DISTINCT ar.student_id_hash) as student_count,
    CURRENT_TIMESTAMP as _loaded_at
FROM {{ ref('fact_academic_records') }} ar
JOIN {{ ref('dim_students') }} d ON ar.student_id_hash = d.student_id_hash
WHERE ar.course_id = '329'  -- Apex Math 8
  AND d.grade_level = 7
GROUP BY ar.school_year, d.primary_race, d.gender, d.is_multi_racial
ORDER BY ar.school_year, student_count DESC
