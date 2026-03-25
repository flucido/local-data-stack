
-- models/mart_features/features/fct_chronic_absence_features.sql
-- Feature: Chronic absence risk indicators

{{ config(
    materialized='table',
    schema='features',
    unique_key='student_id_hash',
    tags=['features', 'attendance', 'chronic_absence']
) }}

-- NOTE: fact_attendance provides annual-grain summaries (not daily records).
-- Absence counts and rates below use the annual totals as proxy.
-- days_absent_30d/90d are estimated proportionally from annual data.

SELECT
    ds.student_id_hash,
    ds.school_id,
    ds.grade_level,
    
    -- Estimated recent absence count (30-day proxy from annual data)
    COALESCE(ROUND(fa.days_absent * 30.0 / NULLIF(fa.days_enrolled, 0)), 0) as days_absent_30d,
    
    -- Estimated historical absence (90-day proxy from annual data)
    COALESCE(ROUND(fa.days_absent * 90.0 / NULLIF(fa.days_enrolled, 0)), 0) as days_absent_90d,
    
    -- Unexcused absences (annual total)
    COALESCE(fa.days_unexcused, 0) as unexcused_absences_total,
    
    -- Tardies (annual total)
    COALESCE(fa.days_tardy, 0) as tardies_total,
    
    -- Attendance rate (annual; attendance_rate from staging is a 0-1 ratio)
    CASE 
        WHEN fa.days_enrolled > 0
        THEN ROUND(COALESCE(fa.attendance_rate, 0) * 100.0, 2)
        ELSE 100.0
    END as attendance_rate_30d,
    
    -- Risk characteristics
    ds.special_education_flag,
    ds.ell_status,
    ds.free_reduced_lunch_flag,
    ds.homeless_flag,
    
    -- Chronic absence flag (standard: absent >= 10% of enrolled days)
    CASE 
        WHEN fa.days_enrolled > 0
             AND (fa.days_absent * 1.0 / fa.days_enrolled) >= 0.10 THEN TRUE
        ELSE FALSE
    END as chronic_absence_flag,
    
    -- Audit
    CURRENT_TIMESTAMP as dbt_processed_date

FROM {{ ref('dim_students') }} ds
LEFT JOIN {{ ref('fact_attendance') }} fa ON ds.student_id_hash = fa.student_id_hash
GROUP BY ds.student_id_hash, ds.school_id, ds.grade_level, ds.special_education_flag, 
         ds.ell_status, ds.free_reduced_lunch_flag, ds.homeless_flag,
         fa.days_absent, fa.days_enrolled, fa.days_unexcused, fa.days_tardy, fa.attendance_rate

