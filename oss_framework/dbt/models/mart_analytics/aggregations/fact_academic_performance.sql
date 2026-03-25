{{ config(
    materialized='table',
    schema='analytics',
    unique_id='fact_academic_performance'
) }}

WITH academic_base AS (
    SELECT
        ar.student_id_hash AS student_key,
        CASE
            WHEN ar.grade = 'A+' OR ar.grade = 'A' THEN 4.0
            WHEN ar.grade = 'A-' THEN 3.7
            WHEN ar.grade = 'B+' THEN 3.3
            WHEN ar.grade = 'B' THEN 3.0
            WHEN ar.grade = 'B-' THEN 2.7
            WHEN ar.grade = 'C+' THEN 2.3
            WHEN ar.grade = 'C' THEN 2.0
            WHEN ar.grade = 'C-' THEN 1.7
            WHEN ar.grade = 'D+' THEN 1.3
            WHEN ar.grade = 'D' THEN 1.0
            WHEN ar.grade = 'D-' THEN 0.7
            ELSE 0.0
        END AS grade_numeric,
        -- gpa_points from staging provides a coarser numeric grade
        ar.gpa_points AS assignment_grade_percent,
        ar.grade AS grade_letter,
        ar.created_at AS _loaded_at
    FROM {{ ref('fact_academic_records') }} ar
    WHERE ar.grade IS NOT NULL
)

SELECT
    student_key,
    ROUND(AVG(grade_numeric), 2) AS grade_numeric,
    ROUND(AVG(assignment_grade_percent), 2) AS assignment_grade_percent,
    COUNT(*) AS assignment_count,
    SUM(CASE WHEN grade_numeric >= 2.0 THEN 1 ELSE 0 END) AS passing_assignments,
    ROUND(
        100.0 * SUM(CASE WHEN grade_numeric >= 2.0 THEN 1 ELSE 0 END) / 
        NULLIF(COUNT(*), 0),
        2
    ) AS pct_passing,
    MAX(_loaded_at) AS _loaded_at
FROM academic_base
GROUP BY 1
