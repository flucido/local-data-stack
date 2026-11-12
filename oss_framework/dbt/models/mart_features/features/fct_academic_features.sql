-- models/mart_features/features/fct_academic_features.sql
-- Feature: Academic performance indicators

{{ config(
    materialized='table',
    schema='features',
    unique_key=['student_id_hash', 'academic_year'],
    tags=['features', 'academic']
) }}

WITH latest_academic AS (
    SELECT MAX(created_at) AS max_created_at
    FROM {{ ref('fact_academic_records') }}
)

SELECT
    ds.student_id_hash,
    ds.academic_year,
    ds.school_id,
    ds.grade_level,

    -- Grade metrics (using gpa_points from fact_academic_records, scale 0-4)
    COALESCE(ROUND(AVG(far.gpa_points), 2), 0) as avg_score,
    COALESCE(MIN(far.gpa_points), 0) as min_score,
    COALESCE(MAX(far.gpa_points), 0) as max_score,

    -- Record count
    COALESCE(COUNT(far.grade), 0) as total_records,

    -- Passing percentage (is_passing from staging)
    CASE
        WHEN COUNT(far.grade) > 0 THEN ROUND(100.0 * COUNT(CASE WHEN far.is_passing THEN 1 END) / COUNT(far.grade), 2)
        ELSE 0
    END as passing_rate,

    -- Letter grade distribution (using grade column from fact_academic_records)
    COALESCE(COUNT(CASE WHEN far.grade IN ('A+', 'A', 'A-', 'B+', 'B', 'B-') THEN 1 END), 0) as above_average_count,
    COALESCE(COUNT(CASE WHEN far.grade IN ('C+', 'C', 'C-') THEN 1 END), 0) as average_count,
    COALESCE(COUNT(CASE WHEN far.grade IN ('D+', 'D', 'D-', 'F', 'NP') THEN 1 END), 0) as below_average_count,

    -- Grade trend anchored on snapshot max(created_at)
    CASE
        WHEN AVG(CASE WHEN far.created_at >= la.max_created_at - INTERVAL '15 days' THEN far.gpa_points END) >
             AVG(CASE WHEN far.created_at < la.max_created_at - INTERVAL '15 days' THEN far.gpa_points END) THEN 'IMPROVING'
        WHEN AVG(CASE WHEN far.created_at >= la.max_created_at - INTERVAL '15 days' THEN far.gpa_points END) <
             AVG(CASE WHEN far.created_at < la.max_created_at - INTERVAL '15 days' THEN far.gpa_points END) THEN 'DECLINING'
        ELSE 'STABLE'
    END as grade_trend,

    -- Audit
    CURRENT_TIMESTAMP as dbt_processed_date

FROM {{ ref('dim_students') }} ds
CROSS JOIN latest_academic la
LEFT JOIN {{ ref('fact_academic_records') }} far
    ON ds.student_id_hash = far.student_id_hash
    AND ds.academic_year = far.school_year
GROUP BY ds.student_id_hash, ds.academic_year, ds.school_id, ds.grade_level, la.max_created_at
