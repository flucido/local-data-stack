{{ config(
    materialized='table',
    schema='analytics',
    post_hook="ANALYZE {{ this }}"
) }}

-- DuckDB Optimization: Materialized as table for faster dashboard queries.
-- See: docs/tasks/backend/2026-01-27/database-index-optimization/

SELECT
    COALESCE(d.ethnicity, 'Unknown') AS race_ethnicity,
    COALESCE(d.ell_program_flag, false) AS english_learner,
    COALESCE(d.special_education_flag, false) AS special_education,
    COALESCE(d.free_reduced_lunch_flag, false) AS economically_disadvantaged,
    
    COUNT(DISTINCT d.student_id_hash) AS cohort_size,
    
    -- Attendance outcomes
    ROUND(100.0 * SUM(CASE WHEN COALESCE(a.attendance_rate, 0) > 90 THEN 1 ELSE 0 END) / 
        NULLIF(COUNT(DISTINCT d.student_id_hash), 0), 1) AS pct_good_attendance,
    
    -- Discipline outcomes
    ROUND(100.0 * SUM(CASE WHEN COALESCE(dis.incident_count, 0) = 0 THEN 1 ELSE 0 END) / 
        NULLIF(COUNT(DISTINCT d.student_id_hash), 0), 1) AS pct_no_discipline,
    
    -- Academic outcomes
    ROUND(AVG(acad.grade_numeric), 2) AS avg_gpa,
    ROUND(100.0 * SUM(CASE WHEN COALESCE(acad.grade_numeric, 0) >= 2.5 THEN 1 ELSE 0 END) / 
        NULLIF(COUNT(DISTINCT d.student_id_hash), 0), 1) AS pct_gpa_2_5_plus,
    
    -- Low grade alert
    ROUND(100.0 * SUM(CASE WHEN COALESCE(acad.grade_numeric, 0) < 2.0 THEN 1 ELSE 0 END) / 
        NULLIF(COUNT(DISTINCT d.student_id_hash), 0), 1) AS pct_below_c,
    
    CURRENT_TIMESTAMP AS _loaded_at
    
FROM {{ ref('dim_students') }} d
LEFT JOIN {{ ref('agg_attendance_windows') }} a 
    ON d.student_id_hash = a.student_key AND a.window_type = 'term'
LEFT JOIN {{ ref('agg_discipline_windows') }} dis 
    ON d.student_id_hash = dis.student_key AND dis.window_type = 'term'
LEFT JOIN {{ ref('fact_academic_performance') }} acad 
    ON d.student_id_hash = acad.student_key

GROUP BY 1, 2, 3, 4
ORDER BY race_ethnicity, english_learner, special_education, economically_disadvantaged
