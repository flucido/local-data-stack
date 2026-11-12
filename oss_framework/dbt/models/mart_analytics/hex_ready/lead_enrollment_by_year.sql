-- models/mart_analytics/hex_ready/lead_enrollment_by_year.sql
-- LEAD Program Enrollment by Year with Demographics (5-Year Historical)
-- Course code 1205 (001205 in Aeries)
-- FERPA: cells with fewer than 5 distinct students are suppressed (k >= 5).

{{ config(
    materialized='table',
    schema='analytics',
    tags=['analytics', 'hex', 'enrollment', 'lead', 'k_anonymity']
) }}

SELECT
    ar.school_year,
    d.primary_race,
    d.gender,
    d.is_multi_racial,
    d.grade_level,
    COUNT(DISTINCT ar.student_id_hash) as student_count,
    CURRENT_TIMESTAMP as _loaded_at
FROM {{ ref('fact_academic_records') }} ar
JOIN {{ ref('dim_students') }} d
    ON ar.student_id_hash = d.student_id_hash
    AND ar.school_year = d.academic_year
WHERE ar.course_id = '1205'  -- LEAD Program
GROUP BY ar.school_year, d.primary_race, d.gender, d.is_multi_racial, d.grade_level
HAVING COUNT(DISTINCT ar.student_id_hash) >= 5
ORDER BY ar.school_year, student_count DESC
