
-- models/mart_scoring/scoring/score_academic_risk.sql
-- Risk Score: Academic Performance Risk (0-100)

{{ config(
    materialized='table',
    schema='scoring',
    unique_key='student_id_hash',
    tags=['scoring', 'risk', 'academic']
) }}

SELECT
    aaf.student_id_hash,
    aaf.school_id,
    aaf.grade_level,
    
    -- Grade metrics (avg_score is on GPA 0-4 scale from gpa_points)
    COALESCE(aaf.avg_score, 0) as avg_score,
    COALESCE(aaf.passing_rate, 0) as passing_rate,
    aaf.grade_trend,
    
    -- Academic risk score (0-100, based on GPA 0-4 scale)
    CASE 
        WHEN aaf.avg_score < 1.0 THEN 90
        WHEN aaf.avg_score < 2.0 THEN 70
        WHEN aaf.avg_score < 2.5 THEN 40
        WHEN aaf.avg_score < 3.0 THEN 15
        ELSE 5
    END as academic_risk_score,
    
    -- Risk classification (based on GPA 0-4 scale)
    CASE 
        WHEN aaf.avg_score < 1.0 THEN 'CRITICAL'
        WHEN aaf.avg_score < 2.0 THEN 'HIGH'
        WHEN aaf.avg_score < 2.5 THEN 'MEDIUM'
        ELSE 'LOW'
    END as risk_level,
    
    -- Count data
    aaf.total_records,
    aaf.above_average_count,
    aaf.average_count,
    aaf.below_average_count,
    
    -- Recommendations (based on GPA 0-4 scale)
    CASE 
        WHEN aaf.avg_score < 1.0 AND aaf.grade_trend = 'DECLINING' THEN 'URGENT: Failing trajectory, academic intervention required'
        WHEN aaf.avg_score < 2.0 THEN 'HIGH: Consider tutoring or course support'
        WHEN aaf.avg_score < 2.5 AND aaf.grade_trend = 'DECLINING' THEN 'MEDIUM: Monitor progress, provide support if decline continues'
        WHEN aaf.grade_trend = 'IMPROVING' THEN 'POSITIVE: Student showing improvement'
        ELSE 'On track'
    END as recommended_action,
    
    CURRENT_TIMESTAMP as calculated_at

FROM {{ ref('fct_academic_features') }} aaf

