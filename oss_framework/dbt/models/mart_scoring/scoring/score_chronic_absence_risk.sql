
-- models/mart_scoring/scoring/score_chronic_absence_risk.sql
-- Risk Score: Chronic Absence Risk (0-100)
-- Algorithm: Weighted combination of absence metrics

{{ config(
    materialized='table',
    schema='scoring',
    unique_key='student_id_hash',
    tags=['scoring', 'risk', 'chronic_absence']
) }}

WITH scored AS (
    SELECT
        caf.student_id_hash,
        caf.school_id,
        caf.grade_level,
        
        -- Component scores (0-100 each)
        LEAST(100, CEIL(CAST(caf.days_absent_30d AS FLOAT) * 10)) as recent_absence_score,
        LEAST(100, CEIL(CAST(caf.days_absent_90d AS FLOAT) * 3)) as trend_absence_score,
        LEAST(100, CEIL(CAST(caf.unexcused_absences_total AS FLOAT) * 5)) as unexcused_score,
        
        -- Composite risk score (weighted average)
        ROUND(
            (LEAST(100, CEIL(CAST(caf.days_absent_30d AS FLOAT) * 10)) * 0.5 +
             LEAST(100, CEIL(CAST(caf.days_absent_90d AS FLOAT) * 3)) * 0.3 +
             LEAST(100, CEIL(CAST(caf.unexcused_absences_total AS FLOAT) * 5)) * 0.2),
            1
        ) as chronic_absence_risk_score,
        
        -- Raw metrics for reference
        caf.days_absent_30d,
        caf.days_absent_90d,
        caf.attendance_rate_30d,
        caf.chronic_absence_flag
    FROM {{ ref('fct_chronic_absence_features') }} caf
)

SELECT
    student_id_hash,
    school_id,
    grade_level,
    recent_absence_score,
    trend_absence_score,
    unexcused_score,
    chronic_absence_risk_score,
    
    -- Risk classification (based on composite score)
    CASE 
        WHEN chronic_absence_risk_score > 70 THEN 'CRITICAL'
        WHEN chronic_absence_risk_score > 50 THEN 'HIGH'
        WHEN chronic_absence_risk_score > 30 THEN 'MEDIUM'
        ELSE 'LOW'
    END as risk_level,
    
    days_absent_30d,
    days_absent_90d,
    attendance_rate_30d,
    chronic_absence_flag,
    
    -- Recommendations
    CASE 
        WHEN chronic_absence_flag THEN 'CRITICAL: Schedule immediate parent conference and intervention plan'
        WHEN chronic_absence_risk_score > 50 THEN 'HIGH: Monitor closely, trending towards chronic absence'
        WHEN chronic_absence_risk_score > 30 THEN 'MEDIUM: Preventive outreach recommended'
        ELSE 'LOW: On track'
    END as recommended_action,
    
    CURRENT_TIMESTAMP as calculated_at

FROM scored

