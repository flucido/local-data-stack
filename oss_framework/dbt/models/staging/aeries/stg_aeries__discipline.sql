-- models/staging/stg_discipline.sql
-- Staging: Standardize raw_discipline with schema normalization

{{ config(
    schema='staging',
    tags=['staging', 'discipline']
) }}

SELECT
    CAST(d.student_id AS VARCHAR) as student_id_raw,
    CAST(d.school_id AS VARCHAR) as school_id,
    CAST(d.incident_id AS VARCHAR) as incident_id,
    CAST(NULLIF(d.incident_date, '') AS DATE) as incident_date,
    CAST(d.incident_type AS VARCHAR) as incident_type,
    CAST(d.severity AS VARCHAR) as severity,
    CAST(d.resolution AS VARCHAR) as resolution,
    CAST(d.suspension_days AS INTEGER) as suspension_days,
    '2024-2025' as academic_year,
    CAST(NULL AS VARCHAR) as disposition_code,
    CAST(NULL AS VARCHAR) as short_description,
    CASE
        WHEN d.severity IN ('Low', 'Medium', 'High') THEN d.severity
        ELSE 'Unknown'
    END as severity_category,
    CURRENT_TIMESTAMP as dbt_load_timestamp,
    '{{ run_started_at }}' as dbt_run_timestamp
FROM {{ source('raw', 'raw_discipline') }} d
