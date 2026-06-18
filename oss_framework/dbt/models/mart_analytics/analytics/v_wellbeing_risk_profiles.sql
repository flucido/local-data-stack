{{ config(
    materialized='table',
    schema='analytics',
    post_hook="ANALYZE {{ this }}"
) }}

-- DuckDB Optimization: Materialized as table for faster dashboard queries.
-- See: docs/tasks/backend/2026-01-27/database-index-optimization/

WITH snapshot AS (
    SELECT MAX(CAST(attendance_date AS DATE)) AS snapshot_date
    FROM {{ source('raw', 'raw_attendance') }}
),

risk_domains AS (
    SELECT
        d.student_id_hash AS student_key,
        d.grade_level,
        d.school_id,
        d.academic_year,

        -- Attendance risk (0-100)
        ROUND(
            LEAST(100.0 - COALESCE(a.attendance_rate, 100), 100.0),
            1
        ) AS attendance_risk_score,

        -- Discipline risk (0-100)
        ROUND(
            LEAST(COALESCE(dis.incident_count, 0) * 10, 100.0),
            1
        ) AS discipline_risk_score,

        -- Academic risk (0-100)
        ROUND(
            CASE
                WHEN COALESCE(acad.grade_numeric, 2.0) < 1.5 THEN 100
                WHEN COALESCE(acad.grade_numeric, 2.0) < 2.0 THEN 70
                WHEN COALESCE(acad.grade_numeric, 2.0) < 2.5 THEN 40
                ELSE 10
            END,
            1
        ) AS academic_risk_score,

        -- Count domains at high risk (>50)
        CASE
            WHEN LEAST(100.0 - COALESCE(a.attendance_rate, 100), 100.0) > 50 THEN 1 ELSE 0
        END +
        CASE
            WHEN LEAST(COALESCE(dis.incident_count, 0) * 10, 100.0) > 50 THEN 1 ELSE 0
        END +
        CASE
            WHEN COALESCE(acad.grade_numeric, 2.0) < 2.0 THEN 1 ELSE 0
        END AS high_risk_domain_count

    FROM {{ ref('dim_students') }} d
    LEFT JOIN {{ ref('agg_attendance_windows') }} a
        ON d.student_id_hash = a.student_key AND a.window_type = '30d'
    LEFT JOIN {{ ref('agg_discipline_windows') }} dis
        ON d.student_id_hash = dis.student_key AND dis.window_type = '30d'
    LEFT JOIN {{ ref('fact_academic_performance') }} acad
        ON d.student_id_hash = acad.student_key
)

SELECT
    student_key,
    grade_level,
    school_id,
    academic_year,
    attendance_risk_score,
    discipline_risk_score,
    academic_risk_score,
    COALESCE(high_risk_domain_count, 0) AS high_risk_domain_count,

    -- Composite well-being risk score
    ROUND(
        ((attendance_risk_score + discipline_risk_score + academic_risk_score) / 3.0) *
        (1.0 + GREATEST(COALESCE(high_risk_domain_count, 0) - 1, 0) * 0.25),
        1
    ) AS wellbeing_risk_score,

    -- Risk level classification
    CASE
        WHEN ROUND(
            ((attendance_risk_score + discipline_risk_score + academic_risk_score) / 3.0) *
            (1.0 + GREATEST(COALESCE(high_risk_domain_count, 0) - 1, 0) * 0.25),
            1
        ) <= 30 THEN 'Low'
        WHEN ROUND(
            ((attendance_risk_score + discipline_risk_score + academic_risk_score) / 3.0) *
            (1.0 + GREATEST(COALESCE(high_risk_domain_count, 0) - 1, 0) * 0.25),
            1
        ) <= 60 THEN 'Moderate'
        WHEN ROUND(
            ((attendance_risk_score + discipline_risk_score + academic_risk_score) / 3.0) *
            (1.0 + GREATEST(COALESCE(high_risk_domain_count, 0) - 1, 0) * 0.25),
            1
        ) <= 80 THEN 'High'
        ELSE 'Critical'
    END AS wellbeing_risk_level,

    -- Primary concern
    CASE
        WHEN COALESCE(high_risk_domain_count, 0) >= 2 THEN 'Multi-factor'
        WHEN attendance_risk_score > discipline_risk_score AND attendance_risk_score > academic_risk_score THEN 'Attendance'
        WHEN discipline_risk_score > academic_risk_score THEN 'Behavior'
        ELSE 'Academic'
    END AS primary_concern,

    (SELECT snapshot_date FROM snapshot) AS snapshot_date,
    CURRENT_TIMESTAMP AS _loaded_at

FROM risk_domains
ORDER BY wellbeing_risk_score DESC
