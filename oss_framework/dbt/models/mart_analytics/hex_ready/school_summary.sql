-- models/mart_analytics/hex_ready/school_summary.sql
-- School-level summary metrics for Hex dashboards

{{ config(
    materialized='table',
    schema='analytics',
    tags=['analytics', 'hex', 'motherduck']
) }}

SELECT 
    school_id,
    
    -- Enrollment
    COUNT(DISTINCT student_id_hash) as student_count,
    
    -- Demographics
    ROUND(100.0 * SUM(CASE WHEN special_education_flag THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) as pct_special_ed,
    ROUND(100.0 * SUM(CASE WHEN free_reduced_lunch_flag THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) as pct_frl,
    ROUND(100.0 * SUM(CASE WHEN ell_status IS NOT NULL AND ell_status != '' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) as pct_ell,
    
    -- Race breakdown
    ROUND(100.0 * SUM(CASE WHEN primary_race = 'White' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) as pct_white,
    ROUND(100.0 * SUM(CASE WHEN primary_race = 'Hispanic/Latino' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) as pct_hispanic,
    ROUND(100.0 * SUM(CASE WHEN primary_race = 'Asian' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) as pct_asian,
    ROUND(100.0 * SUM(CASE WHEN primary_race = 'Black/African American' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) as pct_black,
    ROUND(100.0 * SUM(CASE WHEN is_multi_racial THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) as pct_multi_racial,
    
    -- Grade levels
    ROUND(AVG(grade_level), 1) as avg_grade_level,
    
    -- Outcomes
    ROUND(AVG(attendance_rate), 1) as avg_attendance_rate,
    ROUND(100.0 * SUM(CASE WHEN attendance_rate >= 90 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) as pct_good_attendance,
    ROUND(AVG(discipline_incidents), 2) as avg_discipline_incidents,
    ROUND(AVG(avg_gpa), 2) as avg_gpa,
    
    -- Risk
    ROUND(100.0 * SUM(CASE WHEN risk_level = 'High Risk' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) as pct_high_risk,
    
    CURRENT_TIMESTAMP as _loaded_at

FROM {{ ref('analytics_for_hex') }}
GROUP BY school_id
ORDER BY student_count DESC
