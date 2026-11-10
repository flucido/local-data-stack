{% set rill_export_dir = env_var('RILL_EXPORT_DIR', '../../rill_project/data') %}
{{
  config(
    materialized='external',
    location=rill_export_dir ~ '/chronic_absenteeism_risk.parquet',
    format='parquet',
    tags=['rill_export']
  )
}}

SELECT
    academic_year,
    school_id,
    grade_level,
    COUNT(*) AS student_count,
    SUM(chronic_absence_flag) AS chronic_absent_count,
    ROUND(100.0 * SUM(chronic_absence_flag) / NULLIF(COUNT(*), 0), 2) AS chronic_absent_rate_pct,
    ROUND(AVG(attendance_rate_30d), 2) AS avg_attendance_rate_30d,
    ROUND(AVG(attendance_rate_90d), 2) AS avg_attendance_rate_90d,
    ROUND(AVG(chronic_absenteeism_risk_score), 2) AS avg_risk_score,
    MAX(snapshot_date) AS snapshot_date,
    CURRENT_TIMESTAMP AS _loaded_at
FROM {{ ref('v_chronic_absenteeism_risk') }}
GROUP BY academic_year, school_id, grade_level
HAVING COUNT(*) >= 5
