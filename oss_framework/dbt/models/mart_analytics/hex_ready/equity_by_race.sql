-- models/mart_analytics/hex_ready/equity_by_race.sql
-- Aggregated equity outcomes by primary race for Hex dashboards
-- Focus on race_code_1 (primary race) only

{{ config(
    materialized='table',
    schema='analytics',
    tags=['analytics', 'hex', 'motherduck', 'equity']
) }}

SELECT 
    -- Race breakdown
    primary_race,
    is_multi_racial,
    
    -- Group sizes
    COUNT(DISTINCT student_id_hash) as student_count,
    
    -- Demographics breakdown
    SUM(CASE WHEN special_education_flag THEN 1 ELSE 0 END) as special_ed_count,
    SUM(CASE WHEN free_reduced_lunch_flag THEN 1 ELSE 0 END) as frl_count,
    SUM(CASE WHEN ell_status IS NOT NULL AND ell_status != '' THEN 1 ELSE 0 END) as ell_count,
    SUM(CASE WHEN homeless_flag THEN 1 ELSE 0 END) as homeless_count,
    
    -- Attendance outcomes
    ROUND(AVG(attendance_rate), 1) as avg_attendance_rate,
    ROUND(100.0 * SUM(CASE WHEN attendance_rate >= 90 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) as pct_good_attendance,
    ROUND(AVG(days_absent), 1) as avg_days_absent,
    
    -- Discipline outcomes  
    ROUND(AVG(discipline_incidents), 2) as avg_discipline_incidents,
    ROUND(100.0 * SUM(CASE WHEN discipline_incidents = 0 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) as pct_no_discipline,
    ROUND(100.0 * SUM(CASE WHEN suspension_count > 0 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) as pct_suspended,
    
    -- Academic outcomes
    ROUND(AVG(avg_gpa), 2) as avg_gpa,
    ROUND(100.0 * SUM(CASE WHEN avg_gpa >= 2.5 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) as pct_gpa_2_5_plus,
    ROUND(100.0 * SUM(CASE WHEN avg_gpa < 2.0 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) as pct_below_c,
    
    -- Risk distribution
    ROUND(100.0 * SUM(CASE WHEN risk_level = 'High Risk' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) as pct_high_risk,
    ROUND(100.0 * SUM(CASE WHEN risk_level = 'Moderate Risk' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) as pct_moderate_risk,
    ROUND(100.0 * SUM(CASE WHEN risk_level = 'Low Risk' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) as pct_low_risk,
    
    CURRENT_TIMESTAMP as _loaded_at

FROM {{ ref('analytics_for_hex') }}
GROUP BY primary_race, is_multi_racial
ORDER BY student_count DESC
