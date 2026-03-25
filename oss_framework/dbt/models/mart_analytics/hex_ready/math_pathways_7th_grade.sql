-- models/mart_analytics/hex_ready/math_pathways_7th_grade.sql
-- 7th Grade Math Pathways: Math 8 (325) vs Apex Math 8 (329)
-- Course codes from Aeries with leading zeros stripped

{{ config(
    materialized='table',
    schema='analytics',
    tags=['analytics', 'hex', 'pathways']
) }}

WITH math_8 AS (
    -- Regular Math 8 (course 325)
    SELECT 
        ar.student_id_hash,
        ar.school_year,
        d.primary_race,
        d.gender,
        d.is_multi_racial,
        'Math 8' as pathway
    FROM {{ ref('fact_academic_records') }} ar
    JOIN {{ ref('dim_students') }} d ON ar.student_id_hash = d.student_id_hash
    WHERE ar.course_id = '325' AND d.grade_level = 7
),
apex_math_8 AS (
    -- Apex Math 8 (course 329)
    SELECT 
        ar.student_id_hash,
        ar.school_year,
        d.primary_race,
        d.gender,
        d.is_multi_racial,
        'Apex Math 8' as pathway
    FROM {{ ref('fact_academic_records') }} ar
    JOIN {{ ref('dim_students') }} d ON ar.student_id_hash = d.student_id_hash
    WHERE ar.course_id = '329' AND d.grade_level = 7
),
combined AS (
    SELECT * FROM math_8
    UNION ALL
    SELECT * FROM apex_math_8
)

SELECT 
    school_year,
    pathway,
    primary_race,
    gender,
    is_multi_racial,
    COUNT(DISTINCT student_id_hash) as student_count,
    CURRENT_TIMESTAMP as _loaded_at
FROM combined
GROUP BY school_year, pathway, primary_race, gender, is_multi_racial
ORDER BY school_year, pathway, student_count DESC
