
-- models/mart_core/core/fact_academic_records.sql
-- Fact: Student academic performance data

{{ config(
    materialized='table',
    schema='core',
    unique_key=['student_id_hash', 'course_id', 'term', 'school_year'],
    tags=['core', 'facts', 'academics']
) }}

SELECT
    -- Composite primary key (no record_id in source)
    {{ dbt_utils.generate_surrogate_key(['sar.student_id_raw', 'sar.course_id', 'sar.section_id', 'sar.term', 'sar.school_year']) }} as academic_record_sk,
    -- Foreign keys
    {{ hash_pii_secure('sar.student_id_raw') }} as student_id_hash,
    {{ hash_pii_secure('sar.teacher_id') }} as teacher_id_hash,
    sar.school_id,
    sar.course_id,
    sar.section_id,
    sar.term,
    sar.school_year,
    
    -- Grade data
    sar.grade,
    sar.credit_earned,
    
    -- Derived features (use gpa_points from staging, not raw score)
    sar.gpa_points,
    sar.is_passing,
    
    -- Audit
    CAST(NULL AS TIMESTAMP) as created_at,
    CURRENT_TIMESTAMP as dbt_processed_date

FROM {{ ref('stg_aeries__academic_records') }} sar

