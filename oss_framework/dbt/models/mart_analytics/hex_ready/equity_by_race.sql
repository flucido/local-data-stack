-- models/mart_analytics/hex_ready/equity_by_race.sql
-- Aggregated equity outcomes by academic_year and primary race

{{ config(
    materialized='table',
    schema='analytics',
    tags=['analytics', 'hex', 'motherduck', 'equity']
) }}

SELECT
    -- Grain
    academic_year,
    primary_race,
    is_multi_racial,

    -- Group sizes
    COUNT(DISTINCT student_id_hash) AS student_count,

    -- Demographics breakdown (suppress subgroup counts < 5)
    CASE WHEN SUM(CASE WHEN special_education_flag THEN 1 ELSE 0 END) >= 5
         THEN SUM(CASE WHEN special_education_flag THEN 1 ELSE 0 END)
         ELSE NULL END AS special_ed_count,
    CASE WHEN SUM(CASE WHEN free_reduced_lunch_flag THEN 1 ELSE 0 END) >= 5
         THEN SUM(CASE WHEN free_reduced_lunch_flag THEN 1 ELSE 0 END)
         ELSE NULL END AS frl_count,
    CASE WHEN SUM(CASE WHEN ell_status THEN 1 ELSE 0 END) >= 5
         THEN SUM(CASE WHEN ell_status THEN 1 ELSE 0 END)
         ELSE NULL END AS ell_count,
    CASE WHEN SUM(CASE WHEN homeless_flag THEN 1 ELSE 0 END) >= 5
         THEN SUM(CASE WHEN homeless_flag THEN 1 ELSE 0 END)
         ELSE NULL END AS homeless_count,

    -- Attendance outcomes (consistent 0..100 scale matching analytics_for_hex and school_summary)
    ROUND(AVG(attendance_rate), 2) AS avg_attendance_rate,
    ROUND(100.0 * SUM(CASE WHEN attendance_rate >= 90 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) AS pct_good_attendance,
    ROUND(AVG(days_absent), 1) AS avg_days_absent,

    -- Discipline outcomes
    SUM(discipline_incident_count) AS incident_count,
    ROUND(AVG(discipline_incidents), 2) AS avg_discipline_incidents,
    ROUND(100.0 * SUM(CASE WHEN discipline_incidents = 0 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) AS pct_no_discipline,
    ROUND(100.0 * SUM(CASE WHEN suspension_count > 0 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) AS pct_suspended,

    -- Academic outcomes
    ROUND(AVG(avg_gpa), 2) AS avg_gpa,
    ROUND(100.0 * SUM(CASE WHEN avg_gpa >= 2.5 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) AS pct_gpa_2_5_plus,
    ROUND(100.0 * SUM(CASE WHEN avg_gpa < 2.0 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) AS pct_below_c,

    -- Risk distribution
    ROUND(100.0 * SUM(CASE WHEN risk_level = 'High Risk' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) AS pct_high_risk,
    ROUND(100.0 * SUM(CASE WHEN risk_level = 'Moderate Risk' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) AS pct_moderate_risk,
    ROUND(100.0 * SUM(CASE WHEN risk_level = 'Low Risk' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) AS pct_low_risk,

    CURRENT_TIMESTAMP AS _loaded_at

FROM {{ ref('analytics_for_hex') }}
GROUP BY academic_year, primary_race, is_multi_racial
HAVING COUNT(DISTINCT student_id_hash) >= 5
ORDER BY academic_year, student_count DESC
