
-- models/mart_core/core/fact_enrollment.sql
-- Fact: Course enrollment records

{{ config(
    materialized='table',
    schema='core',
    unique_key=['student_id_hash', 'school_year', 'school_id', 'enrollment_date'],
    tags=['core', 'facts', 'enrollment']
) }}

SELECT
    -- Composite primary key (no enrollment_id in source)
    {{ dbt_utils.generate_surrogate_key(['se.student_id_raw', 'se.school_year', 'se.school_id', 'se.enrollment_date']) }} as enrollment_sk,
    -- Foreign keys
    {{ hash_pii_secure('se.student_id_raw') }} as student_id_hash,
    se.school_id,
    
    -- Enrollment tracking
    se.school_year,
    se.enrollment_date,
    se.withdrawal_date,
    se.grade_level,
    se.enrollment_status,
    
    -- Derived flags
    CASE 
        WHEN se.withdrawal_date IS NOT NULL AND se.withdrawal_date <= CURRENT_DATE THEN 'WITHDRAWN'
        WHEN se.enrollment_status = 'ACTIVE' THEN 'ACTIVE'
        ELSE 'UNKNOWN'
    END as enrollment_status_derived,
    
    -- Audit
    CAST(NULL AS TIMESTAMP) as created_at,
    CURRENT_TIMESTAMP as dbt_processed_date

FROM {{ ref('stg_aeries__enrollment') }} se

