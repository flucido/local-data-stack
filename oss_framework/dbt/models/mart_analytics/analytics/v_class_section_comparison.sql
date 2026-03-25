{{ config(
    materialized='table',
    schema='analytics',
    post_hook="ANALYZE {{ this }}"
) }}

-- DuckDB Optimization: Materialized as table for faster dashboard queries.
-- See: docs/tasks/backend/2026-01-27/database-index-optimization/

SELECT
    ace.course_id,
    ace.school_id,
    ace.grade_level,
    ace.enrollment_count,
    ace.avg_grade_numeric,
    ace.pct_passed,
    ace.pct_a_b_grades,
    
    -- Comparison to same course
    ROUND(
        (SELECT AVG(avg_grade_numeric) 
        FROM {{ ref('fact_class_effectiveness') }} ace2 
        WHERE ace2.course_id = ace.course_id AND ace2.term = ace.term),
        2
    ) AS course_avg_grade,
    
    ROUND(
        ace.avg_grade_numeric - 
        (SELECT AVG(avg_grade_numeric) 
        FROM {{ ref('fact_class_effectiveness') }} ace2 
        WHERE ace2.course_id = ace.course_id AND ace2.term = ace.term),
        2
    ) AS grade_diff_from_course_avg,
    
    -- Equity: Subgroup effectiveness
    COALESCE(ace.pct_passed_ell, 0) AS pct_passed_ell,
    COALESCE(ace.pct_passed_sped, 0) AS pct_passed_sped,
    COALESCE(ace.pct_passed_frl, 0) AS pct_passed_frl,
    
    -- Ranking within course
    RANK() OVER (PARTITION BY ace.course_id, ace.term ORDER BY ace.pct_passed DESC) AS pass_rate_rank,
    RANK() OVER (PARTITION BY ace.course_id, ace.term ORDER BY ace.avg_grade_numeric DESC) AS grade_rank,
    
    -- Overall effectiveness rating
    CASE
        WHEN ace.pct_passed >= 90 AND ace.avg_grade_numeric >= 3.3 THEN 'Highly Effective'
        WHEN ace.pct_passed >= 80 AND ace.avg_grade_numeric >= 3.0 THEN 'Effective'
        WHEN ace.pct_passed >= 70 AND ace.avg_grade_numeric >= 2.5 THEN 'Adequate'
        ELSE 'Needs Improvement'
    END AS effectiveness_rating,
    
    ace.term,
    ace._loaded_at

FROM {{ ref('fact_class_effectiveness') }} ace
WHERE ace.term = (SELECT MAX(term) FROM {{ ref('fact_class_effectiveness') }})
ORDER BY ace.course_id, pass_rate_rank
