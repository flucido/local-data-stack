{{ config(
    materialized='table',
    schema='analytics',
    post_hook="ANALYZE {{ this }}"
) }}

-- DuckDB Optimization: Materialized as table for faster dashboard queries.
-- See: docs/tasks/backend/2026-01-27/database-index-optimization/

WITH att_gpa_corr AS (
    SELECT
        'Attendance ↔ GPA' AS correlation_pair,
        ROUND(
            CORR(a.attendance_rate, COALESCE(acad.grade_numeric, 0)),
            3
        ) AS correlation_coefficient,
        'Positive' AS expected_direction,
        COUNT(*) AS data_points,
        CURRENT_TIMESTAMP AS _loaded_at
    FROM {{ ref('agg_attendance_windows') }} a
    JOIN {{ ref('fact_academic_performance') }} acad 
        ON a.student_key = acad.student_key
    WHERE a.window_type = 'term'
),

disc_grades_corr AS (
    SELECT
        'Discipline ↔ Grades' AS correlation_pair,
        ROUND(
            CORR(
                COALESCE(dis.incident_count, 0),
                COALESCE(acad.grade_numeric, 0)
            ),
            3
        ) AS correlation_coefficient,
        'Negative' AS expected_direction,
        COUNT(*) AS data_points,
        CURRENT_TIMESTAMP AS _loaded_at
    FROM {{ ref('agg_discipline_windows') }} dis
    JOIN {{ ref('fact_academic_performance') }} acad 
        ON dis.student_key = acad.student_key
    WHERE dis.window_type = 'term'
),

-- Additional correlation: Attendance & Engagement (using discipline as inverse)
att_engagement_corr AS (
    SELECT
        'Attendance ↔ Engagement' AS correlation_pair,
        ROUND(
            CORR(
                a.attendance_rate,
                100.0 - COALESCE(dis.incident_count, 0) * 10
            ),
            3
        ) AS correlation_coefficient,
        'Positive' AS expected_direction,
        COUNT(*) AS data_points,
        CURRENT_TIMESTAMP AS _loaded_at
    FROM {{ ref('agg_attendance_windows') }} a
    LEFT JOIN {{ ref('agg_discipline_windows') }} dis 
        ON a.student_key = dis.student_key AND a.window_type = dis.window_type
    WHERE a.window_type = 'term'
)

SELECT
    correlation_pair,
    ROUND(COALESCE(correlation_coefficient, 0), 3) AS correlation_coefficient,
    expected_direction,
    COALESCE(data_points, 0) AS data_points,
    CASE
        WHEN COALESCE(correlation_coefficient, 0) IS NULL THEN 'Insufficient Data'
        WHEN ABS(COALESCE(correlation_coefficient, 0)) >= 0.7 THEN 'Strong'
        WHEN ABS(COALESCE(correlation_coefficient, 0)) >= 0.4 THEN 'Moderate'
        WHEN ABS(COALESCE(correlation_coefficient, 0)) >= 0.1 THEN 'Weak'
        ELSE 'Negligible'
    END AS strength,
    _loaded_at

FROM att_gpa_corr

UNION ALL

SELECT
    correlation_pair,
    correlation_coefficient,
    expected_direction,
    data_points,
    CASE
        WHEN COALESCE(correlation_coefficient, 0) IS NULL THEN 'Insufficient Data'
        WHEN ABS(COALESCE(correlation_coefficient, 0)) >= 0.7 THEN 'Strong'
        WHEN ABS(COALESCE(correlation_coefficient, 0)) >= 0.4 THEN 'Moderate'
        WHEN ABS(COALESCE(correlation_coefficient, 0)) >= 0.1 THEN 'Weak'
        ELSE 'Negligible'
    END AS strength,
    _loaded_at
FROM disc_grades_corr

UNION ALL

SELECT
    correlation_pair,
    correlation_coefficient,
    expected_direction,
    data_points,
    CASE
        WHEN COALESCE(correlation_coefficient, 0) IS NULL THEN 'Insufficient Data'
        WHEN ABS(COALESCE(correlation_coefficient, 0)) >= 0.7 THEN 'Strong'
        WHEN ABS(COALESCE(correlation_coefficient, 0)) >= 0.4 THEN 'Moderate'
        WHEN ABS(COALESCE(correlation_coefficient, 0)) >= 0.1 THEN 'Weak'
        ELSE 'Negligible'
    END AS strength,
    _loaded_at
FROM att_engagement_corr
