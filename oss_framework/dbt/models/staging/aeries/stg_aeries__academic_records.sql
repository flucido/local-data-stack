-- models/staging/stg_academic_records.sql
-- Staging: Standardize raw_academic_records with schema normalization

{{ config(
    schema='staging',
    tags=['staging', 'academic_records']
) }}

SELECT
    CAST(g.student_id AS VARCHAR) as student_id_raw,
    CAST(g.school_id AS VARCHAR) as school_id,
    CAST(g.course_id AS VARCHAR) as course_id,
    CAST(g.section_id AS VARCHAR) as section_id,
    CAST(g.teacher_id AS VARCHAR) as teacher_id,
    CAST(g.grade AS VARCHAR) as grade,
    CAST(g.score AS DOUBLE) as score,
    CAST(g.term AS VARCHAR) as term,
    CAST(g.school_year AS VARCHAR) as school_year,
    CAST(g.record_id AS VARCHAR) as academic_record_sk,
    -- Derived fields
    1.0 as credit_earned,
    CASE
        WHEN g.grade = 'A' THEN 4.0
        WHEN g.grade = 'B' THEN 3.0
        WHEN g.grade = 'C' THEN 2.0
        WHEN g.grade = 'D' THEN 1.0
        ELSE 0.0
    END as gpa_points,
    CASE
        WHEN g.grade IN ('A', 'B', 'C', 'D') THEN true
        ELSE false
    END as is_passing,
    CURRENT_TIMESTAMP as dbt_load_timestamp,
    '{{ run_started_at }}' as dbt_run_timestamp
FROM {{ source('raw', 'raw_academic_records') }} g
