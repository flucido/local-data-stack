
-- models/mart_core/core/fact_discipline.sql
-- Fact: Student discipline incident records

{{ config(
    materialized='table',
    schema='core',
    unique_key='incident_id',
    tags=['core', 'facts', 'discipline']
) }}

SELECT
    -- Foreign keys
    {{ hash_pii_secure('sd.student_id_raw') }} as student_id_hash,
    sd.school_id,
    sd.incident_id,
    sd.academic_year,
    
    -- Incident tracking
    sd.incident_date,
    sd.short_description as incident_type,
    sd.severity_category as severity,
    sd.disposition_code as resolution,
    
    -- Consequence
    sd.suspension_days,
    
    -- Derived flags
    CASE 
        WHEN sd.suspension_days > 0 THEN 1
        ELSE 0
    END as suspension_flag,
    
    CASE 
        WHEN sd.severity_category IN ('High', 'Medium') THEN 1
        ELSE 0
    END as serious_incident_flag,
    
    -- Audit
    CAST(NULL AS TIMESTAMP) as created_at,
    CURRENT_TIMESTAMP as dbt_processed_date

FROM {{ ref('stg_aeries__discipline') }} sd

