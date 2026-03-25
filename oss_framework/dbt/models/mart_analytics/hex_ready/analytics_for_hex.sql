-- models/mart_analytics/hex_ready/analytics_for_hex.sql
-- Analytics tables optimized for Hex dashboards
-- Includes race_code_1 (primary race) for equity analysis

{{ config(
    materialized='table',
    schema='analytics',
    tags=['analytics', 'hex', 'motherduck']
) }}

-- Main student analytics with race breakdown
SELECT 
    -- Identifiers
    d.student_id_hash,
    
    -- Demographics
    d.gender,
    d.ethnicity,
    d.race_code_1 as primary_race_code,
    d.primary_race,
    CASE WHEN d.race_code_2 IS NOT NULL AND d.race_code_2 != '' THEN true ELSE false END as is_multi_racial,
    d.grade_level,
    d.school_id,
    d.home_language,
    
    -- Program participation
    d.special_education_flag,
    d.ell_status,
    d.free_reduced_lunch_flag,
    d.homeless_flag,
    d.foster_care_flag,
    d.section_504_flag,
    d.gate_flag,
    
    -- Risk indicators
    d.high_need_flag,
    d.socioeconomic_risk,
    d.housing_risk,
    
    -- Enrollment
    d.enrollment_status,
    d.cohort,
    
    -- Attendance metrics (from fact_attendance)
    COALESCE(a.attendance_rate, 0) as attendance_rate,
    COALESCE(a.days_absent, 0) as days_absent,
    COALESCE(a.days_present, 0) as days_present,
    COALESCE(a.days_tardy, 0) as days_tardy,
    
    -- Discipline metrics (from fact_discipline)
    COALESCE(dis.incident_count, 0) as discipline_incidents,
    COALESCE(dis.suspension_count, 0) as suspension_count,
    
    -- Academic metrics (from fact_academic_records)
    COALESCE(acad.avg_gpa_points, 0) as avg_gpa,
    COALESCE(acad.total_credits, 0) as credits_earned,
    COALESCE(acad.course_count, 0) as course_count,
    
    -- Derived risk score
    CASE 
        WHEN COALESCE(a.attendance_rate, 0) < 90 
             OR COALESCE(dis.incident_count, 0) > 2 
             OR COALESCE(acad.avg_gpa_points, 0) < 2.0 
        THEN 'High Risk'
        WHEN COALESCE(a.attendance_rate, 0) < 95 
             OR COALESCE(dis.incident_count, 0) > 0 
             OR COALESCE(acad.avg_gpa_points, 0) < 2.5 
        THEN 'Moderate Risk'
        ELSE 'Low Risk'
    END as risk_level,
    
    CURRENT_TIMESTAMP as _loaded_at

FROM {{ ref('dim_students') }} d
LEFT JOIN (
    SELECT 
        student_id_hash,
        AVG(attendance_rate) as attendance_rate,
        SUM(days_absent) as days_absent,
        SUM(days_present) as days_present,
        SUM(days_tardy) as days_tardy
    FROM {{ ref('fact_attendance') }}
    GROUP BY student_id_hash
) a ON d.student_id_hash = a.student_id_hash
LEFT JOIN (
    SELECT 
        student_id_hash,
        COUNT(*) as incident_count,
        SUM(suspension_flag) as suspension_count
    FROM {{ ref('fact_discipline') }}
    GROUP BY student_id_hash
) dis ON d.student_id_hash = dis.student_id_hash
LEFT JOIN (
    SELECT 
        student_id_hash,
        AVG(COALESCE(gpa_points, 0)) as avg_gpa_points,
        SUM(COALESCE(credit_earned, 0)) as total_credits,
        COUNT(DISTINCT course_id) as course_count
    FROM {{ ref('fact_academic_records') }}
    GROUP BY student_id_hash
) acad ON d.student_id_hash = acad.student_id_hash
