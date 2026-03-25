-- models/mart_analytics/hex_ready/lead_program_enrollment.sql
-- LEAD Program Enrollment & Demographics (5-Year Historical)
-- Course code 1205 (001205 in Aeries with leading zeros)

{{ config(
    materialized='table',
    schema='analytics',
    tags=['analytics', 'hex', 'lead']
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
JOIN {{ ref('dim_students') }} d ON ar.student_id_hash = d.student_id_hash
WHERE ar.course_id = '1205'  -- LEAD Program
GROUP BY ar.school_year, d.primary_race, d.gender, d.is_multi_racial, d.grade_level
ORDER BY ar.school_year, student_count DESC
