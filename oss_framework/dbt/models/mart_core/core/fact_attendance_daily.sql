
-- models/mart_core/core/fact_attendance_daily.sql
-- Daily attendance aggregations with k-anonymity enforcement
-- FERPA compliant: minimum 5 students per group
-- NOTE: fact_attendance provides annual-grain summaries, not daily records.
-- This model aggregates annual data by school/grade as the best available proxy.

{{ config(
    materialized='table',
    schema='core',
    unique_key=['school_id', 'grade_level'],
    tags=['core', 'facts', 'attendance', 'aggregated', 'k_anonymity']
) }}

WITH attendance_with_demographics AS (
    SELECT
        fa.school_id,
        fa.academic_year,
        ph.grade_level,
        fa.student_id_hash,
        fa.days_enrolled,
        fa.days_present,
        fa.days_absent,
        fa.days_tardy,
        fa.days_excused,
        fa.days_unexcused
    FROM {{ ref('fact_attendance') }} fa
    JOIN {{ ref('priv_student_hashes') }} ph
        ON fa.student_id_hash = ph.student_id_hash
    WHERE fa.days_enrolled > 0
)

SELECT
    academic_year AS school_year,
    school_id,
    grade_level,
    
    COUNT(DISTINCT student_id_hash) as total_students,
    SUM(days_present) as present_count,
    SUM(days_absent) as absent_count,
    SUM(days_tardy) as tardy_count,
    SUM(days_excused) as excused_count,
    SUM(days_unexcused) as unexcused_count,
    
    ROUND(
        SUM(days_present)::FLOAT 
        / NULLIF(SUM(days_enrolled), 0),
        4
    ) as attendance_rate

FROM attendance_with_demographics
GROUP BY 
    academic_year, school_id, grade_level
HAVING COUNT(DISTINCT student_id_hash) >= 5

