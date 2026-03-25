{{ config(
    materialized='table',
    schema='analytics',
    unique_id='fact_class_effectiveness'
) }}

WITH academic_base AS (
    SELECT
        ar.student_id_hash,
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
        ar.course_id,
        ar.school_id,
        ar.term
    FROM {{ ref('fact_academic_records') }} ar
    WHERE ar.grade IS NOT NULL
),

enrollment_with_grades AS (
    SELECT
        ab.course_id,
        ab.school_id,
        ds.grade_level,
        ds.ell_program_flag AS english_learner,
        ds.special_education_flag AS special_education,
        ds.free_reduced_lunch_flag AS free_reduced_lunch,
        ab.student_id_hash,
        ab.grade_numeric,
        CASE
            WHEN ab.grade_numeric >= 2.0 THEN 1
            ELSE 0
        END AS passed,
        CASE
            WHEN ab.grade_numeric >= 3.3 THEN 1
            ELSE 0
        END AS grade_a_or_b,
        ab.term
    FROM academic_base ab
    LEFT JOIN {{ ref('dim_students') }} ds ON ab.student_id_hash = ds.student_id_hash
)

SELECT
    course_id,
    school_id,
    grade_level,
    COUNT(DISTINCT student_id_hash) AS enrollment_count,
    ROUND(AVG(grade_numeric), 2) AS avg_grade_numeric,
    ROUND(
        100.0 * SUM(passed) / NULLIF(COUNT(*), 0),
        2
    ) AS pct_passed,
    ROUND(
        100.0 * SUM(grade_a_or_b) / NULLIF(COUNT(*), 0),
        2
    ) AS pct_a_b_grades,
    -- Disaggregated by subgroup
    ROUND(
        100.0 * SUM(CASE WHEN english_learner THEN passed ELSE 0 END) / 
        NULLIF(SUM(CASE WHEN english_learner THEN 1 ELSE 0 END), 0),
        2
    ) AS pct_passed_ell,
    ROUND(
        100.0 * SUM(CASE WHEN special_education THEN passed ELSE 0 END) / 
        NULLIF(SUM(CASE WHEN special_education THEN 1 ELSE 0 END), 0),
        2
    ) AS pct_passed_sped,
    ROUND(
        100.0 * SUM(CASE WHEN free_reduced_lunch THEN passed ELSE 0 END) / 
        NULLIF(SUM(CASE WHEN free_reduced_lunch THEN 1 ELSE 0 END), 0),
        2
    ) AS pct_passed_frl,
    term,
    CURRENT_TIMESTAMP AS _loaded_at
FROM enrollment_with_grades
GROUP BY 1, 2, 3, term
