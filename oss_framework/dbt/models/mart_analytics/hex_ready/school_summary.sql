-- models/mart_analytics/hex_ready/school_summary.sql
-- School-level summary metrics unified across dbt, Desktop, and NL->SQL

{{ config(
    materialized='table',
    schema='analytics',
    tags=['analytics', 'hex', 'motherduck']
) }}

SELECT
    h.academic_year,
    h.school_id,
    COALESCE(s.school_name, 'SCHOOL_' || h.school_id) AS school_name,

    -- Enrollment (both aliases exposed for cross-surface compatibility)
    COUNT(DISTINCT h.student_id_hash) AS total_students,
    COUNT(DISTINCT h.student_id_hash) AS student_count,

    -- Demographics
    ROUND(100.0 * SUM(CASE WHEN h.special_education_flag THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) AS pct_special_ed,
    ROUND(100.0 * SUM(CASE WHEN h.free_reduced_lunch_flag THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) AS pct_frl,
    ROUND(100.0 * SUM(CASE WHEN h.ell_status THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) AS pct_ell,

    -- Race breakdown
    ROUND(100.0 * SUM(CASE WHEN h.primary_race = 'White' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) AS pct_white,
    ROUND(100.0 * SUM(CASE WHEN h.primary_race = 'Hispanic/Latino' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) AS pct_hispanic,
    ROUND(100.0 * SUM(CASE WHEN h.primary_race = 'Asian' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) AS pct_asian,
    ROUND(100.0 * SUM(CASE WHEN h.primary_race = 'Black/African American' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) AS pct_black,
    ROUND(100.0 * SUM(CASE WHEN h.is_multi_racial THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) AS pct_multi_racial,

    -- Grade levels
    ROUND(AVG(h.grade_level), 1) AS avg_grade_level,

    -- Outcomes (attendance_rate normalized to 0..100 in analytics_for_hex)
    ROUND(AVG(h.attendance_rate), 2) AS avg_attendance_rate,
    ROUND(100.0 * SUM(CASE WHEN h.attendance_rate >= 90 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) AS pct_good_attendance,
    ROUND(AVG(h.discipline_incidents), 2) AS avg_discipline_incidents,
    SUM(h.discipline_incident_count) AS total_incidents,
    ROUND(AVG(h.gpa_unweighted), 2) AS avg_gpa,

    -- Risk
    ROUND(100.0 * SUM(CASE WHEN h.risk_level = 'High Risk' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) AS pct_high_risk,

    CURRENT_TIMESTAMP AS _loaded_at

FROM {{ ref('analytics_for_hex') }} h
LEFT JOIN {{ ref('dim_schools') }} s
    ON h.school_id = s.school_id
GROUP BY
    h.academic_year,
    h.school_id,
    COALESCE(s.school_name, 'SCHOOL_' || h.school_id)
HAVING COUNT(DISTINCT h.student_id_hash) >= 5
ORDER BY h.academic_year, student_count DESC
