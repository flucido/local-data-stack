-- models/mart_analytics/hex_ready/algebra_1_outcomes.sql
-- 8th Grade Algebra 1 Outcomes (course 308)
-- Grade distribution for students completing Algebra 1

{{ config(
    materialized='table',
    schema='analytics',
    tags=['analytics', 'hex', 'algebra']
) }}

SELECT 
    ar.school_year,
    ar.term,
    d.primary_race,
    d.gender,
    d.is_multi_racial,
    ar.grade,
    ar.gpa_points,
    ar.is_passing,
    COUNT(DISTINCT ar.student_id_hash) as student_count,
    CURRENT_TIMESTAMP as _loaded_at
FROM {{ ref('fact_academic_records') }} ar
JOIN {{ ref('dim_students') }} d ON ar.student_id_hash = d.student_id_hash
WHERE ar.course_id = '308'  -- Algebra 1
  AND d.grade_level = 8
GROUP BY ar.school_year, ar.term, d.primary_race, d.gender, d.is_multi_racial, ar.grade, ar.gpa_points, ar.is_passing
ORDER BY ar.school_year, ar.term, student_count DESC
