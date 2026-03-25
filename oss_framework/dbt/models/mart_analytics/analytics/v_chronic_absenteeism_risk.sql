{{ config(
    materialized='table',
    schema='analytics',
    post_hook="ANALYZE {{ this }}"
) }}

-- DuckDB Optimization: Materialized as table for 100x faster dashboard queries.
-- Views recompute risk scores on every query; tables pre-compute once.
-- See: docs/tasks/backend/2026-01-27/database-index-optimization/

WITH risk_base AS (
    SELECT
        d.student_id_hash AS student_key,
        d.grade_level,
        d.school_id,
        COALESCE(d.gender, 'Unknown') AS gender,
        COALESCE(d.ethnicity, 'Unknown') AS race_ethnicity,
        COALESCE(d.ell_program_flag, false) AS english_learner,
        COALESCE(d.special_education_flag, false) AS special_education,
        COALESCE(d.free_reduced_lunch_flag, false) AS economically_disadvantaged,
        COALESCE(d.homeless_flag, false) AS homeless_flag,
        
        -- 30-day metrics
        COALESCE(a30.attendance_rate, 100) AS attendance_rate_30d,
        COALESCE(a30.unexcused_absence_rate, 0) AS unexcused_absence_rate_30d,
        COALESCE(a30.discipline_incidents_in_window, 0) AS discipline_incidents_30d,
        COALESCE(a30.absence_discipline_correlation_score, 0) AS absence_discipline_correlation_score,
        
        -- 90-day trend
        COALESCE(a90.attendance_rate, 100) AS attendance_rate_90d,
        COALESCE(a90.pattern_direction, 'stable') AS attendance_trend_90d,
        
        -- Risk scoring
        CASE 
            WHEN (100.0 - COALESCE(a30.attendance_rate, 100)) >= 10.0 THEN 1 ELSE 0
        END AS chronic_absence_flag,
        
        -- Composite risk score (0-100)
        -- Components: attendance (40%), unexcused absences (20%), discipline (20%), trend (10%), correlation (10%)
        ROUND(
            LEAST(
                GREATEST(
                    (100.0 - COALESCE(a30.attendance_rate, 100)) * 0.4 +
                    LEAST((COALESCE(a30.unexcused_absence_rate, 0) / 15.0) * 100, 100) * 0.2 +
                    LEAST(COALESCE(a30.discipline_incidents_in_window, 0) * 5, 100) * 0.2 +
                    (CASE WHEN COALESCE(a90.pattern_direction, 'stable') = 'declining' THEN 100 ELSE 0 END) * 0.1 +
                    LEAST(COALESCE(a30.absence_discipline_correlation_score, 0) * 10, 100) * 0.1,
                    0
                ),
                100
            ),
            1
        ) AS chronic_absenteeism_risk_score

    FROM {{ ref('dim_students') }} d
    LEFT JOIN {{ ref('agg_attendance_windows') }} a30 
        ON d.student_id_hash = a30.student_key 
        AND a30.window_type = '30d'
    LEFT JOIN {{ ref('agg_attendance_windows') }} a90 
        ON d.student_id_hash = a90.student_key 
        AND a90.window_type = '90d'
)

SELECT
    *,
    -- Risk classification
    CASE 
        WHEN chronic_absenteeism_risk_score > 70 THEN 'Critical'
        WHEN chronic_absenteeism_risk_score > 50 THEN 'High'
        WHEN chronic_absenteeism_risk_score > 30 THEN 'Medium'
        ELSE 'Low'
    END AS risk_level,
    
    CURRENT_TIMESTAMP AS _loaded_at

FROM risk_base
ORDER BY chronic_absenteeism_risk_score DESC
