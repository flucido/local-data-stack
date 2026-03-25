-- models/mart_analytics/hex_ready/math_8_cohort_tracking.sql
-- Cohort Tracking: 7th Grade Math 8 → 8th Grade Algebra 1
-- Tracks students from 7th grade Math pathways to their 8th grade Algebra 1 outcomes

{{ config(
    materialized='table',
    schema='analytics',
    tags=['analytics', 'hex', 'cohort', 'pathways']
) }}

WITH 
-- Step 1: Identify 7th graders in Math 8 (course 325) by year
math_8_7th_graders AS (
    SELECT DISTINCT
        ar.student_id_hash,
        ar.school_year,
        d.primary_race,
        d.gender,
        d.is_multi_racial,
        'Math 8' as pathway_7th_grade
    FROM {{ ref('fact_academic_records') }} ar
    JOIN {{ ref('dim_students') }} d ON ar.student_id_hash = d.student_id_hash
    WHERE ar.course_id = '325'
      AND d.grade_level = 7
),

-- Step 2: Identify 7th graders in Apex Math 8 (course 329) by year
apex_math_8_7th_graders AS (
    SELECT DISTINCT
        ar.student_id_hash,
        ar.school_year,
        d.primary_race,
        d.gender,
        d.is_multi_racial,
        'Apex Math 8' as pathway_7th_grade
    FROM {{ ref('fact_academic_records') }} ar
    JOIN {{ ref('dim_students') }} d ON ar.student_id_hash = d.student_id_hash
    WHERE ar.course_id = '329'
      AND d.grade_level = 7
),

-- Step 3: All 7th grade math pathway students
all_7th_math_students AS (
    SELECT * FROM math_8_7th_graders
    UNION ALL
    SELECT * FROM apex_math_8_7th_graders
),

-- Step 4: Identify 8th graders who took Algebra 1 (course 308)
algebra_1_8th_graders AS (
    SELECT DISTINCT
        ar.student_id_hash,
        ar.school_year,
        ar.grade as algebra_1_grade,
        ar.gpa_points as algebra_1_gpa,
        ar.is_passing as algebra_1_passing,
        ar.term as algebra_1_term
    FROM {{ ref('fact_academic_records') }} ar
    WHERE ar.course_id = '308'
),

-- Step 5: Match 7th grade students to their 8th grade Algebra 1 outcomes
-- A student in 7th grade in 2022-2023 should be in 8th grade in 2023-2024
cohort_tracking AS (
    SELECT 
        s7.student_id_hash,
        s7.school_year as year_7th_grade,
        -- Calculate expected 8th grade year (current year + 1)
        CASE 
            WHEN s7.school_year = '2020-2021' THEN '2021-2022'
            WHEN s7.school_year = '2021-2022' THEN '2022-2023'
            WHEN s7.school_year = '2022-2023' THEN '2023-2024'
            WHEN s7.school_year = '2023-2024' THEN '2024-2025'
            WHEN s7.school_year = '2024-2025' THEN '2025-2026'
            WHEN s7.school_year = '2025-2026' THEN '2026-2027'
        END as expected_year_8th_grade,
        s7.primary_race,
        s7.gender,
        s7.is_multi_racial,
        s7.pathway_7th_grade,
        -- Algebra 1 outcomes (joined on student and next year)
        a8.algebra_1_grade,
        a8.algebra_1_gpa,
        a8.algebra_1_passing,
        a8.algebra_1_term,
        CASE WHEN a8.student_id_hash IS NOT NULL THEN true ELSE false END as took_algebra_1_in_8th
    FROM all_7th_math_students s7
    LEFT JOIN algebra_1_8th_graders a8 
        ON s7.student_id_hash = a8.student_id_hash
        AND a8.school_year = CASE 
            WHEN s7.school_year = '2020-2021' THEN '2021-2022'
            WHEN s7.school_year = '2021-2022' THEN '2022-2023'
            WHEN s7.school_year = '2022-2023' THEN '2023-2024'
            WHEN s7.school_year = '2023-2024' THEN '2024-2025'
            WHEN s7.school_year = '2024-2025' THEN '2025-2026'
            WHEN s7.school_year = '2025-2026' THEN '2026-2027'
        END
)

SELECT 
    year_7th_grade,
    pathway_7th_grade,
    primary_race,
    gender,
    is_multi_racial,
    took_algebra_1_in_8th,
    algebra_1_grade,
    algebra_1_gpa,
    algebra_1_passing,
    algebra_1_term,
    COUNT(*) as student_count,
    CURRENT_TIMESTAMP as _loaded_at
FROM cohort_tracking
GROUP BY 
    year_7th_grade, pathway_7th_grade, primary_race, gender, is_multi_racial,
    took_algebra_1_in_8th, algebra_1_grade, algebra_1_gpa, algebra_1_passing, algebra_1_term
ORDER BY year_7th_grade, pathway_7th_grade, primary_race, gender
