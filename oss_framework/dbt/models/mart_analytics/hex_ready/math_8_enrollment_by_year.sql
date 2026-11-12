-- models/mart_analytics/hex_ready/math_8_enrollment_by_year.sql
-- 7th Grade Math 8 Enrollment by Year with Demographics
-- Course code 325 (000325 in Aeries)
-- FERPA: cells with fewer than 5 distinct students are suppressed (k >= 5).

{{ config(
    materialized='table',
    schema='analytics',
    tags=['analytics', 'hex', 'enrollment', 'math8', 'k_anonymity']
) }}

SELECT
    ar.school_year,
    d.primary_race,
    d.gender,
    d.is_multi_racial,
    COUNT(DISTINCT ar.student_id_hash) as student_count,
    CURRENT_TIMESTAMP as _loaded_at
FROM {{ ref('fact_academic_records') }} ar
JOIN {{ ref('dim_students') }} d
    ON ar.student_id_hash = d.student_id_hash
    AND ar.school_year = d.academic_year
WHERE ar.course_id = '325'  -- Math 8
  AND d.grade_level = 7
GROUP BY ar.school_year, d.primary_race, d.gender, d.is_multi_racial
HAVING COUNT(DISTINCT ar.student_id_hash) >= 5
ORDER BY ar.school_year, student_count DESC
