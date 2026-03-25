
-- models/staging/stg_discipline.sql
-- Staging: Standardize raw_discipline with schema normalization

{{ config(
    schema='staging',
    tags=['staging', 'discipline']
) }}

SELECT DISTINCT  -- Deduplicate exact duplicate rows in source data
    CAST(IncidentID AS VARCHAR) as incident_id,
    CAST(StudentID AS VARCHAR) as student_id_raw,
    CAST(SchoolOfIncidentCode AS VARCHAR) as school_id,
    CAST(AcademicYear AS VARCHAR) as academic_year,
    CAST(IncidentDate AS DATE) as incident_date,
    CAST(LocationCode AS VARCHAR) as location_code,
    CAST(ShortDescription AS VARCHAR) as short_description,
    CAST(Comment AS VARCHAR) as comment,

    CAST(Admin_DispositionCode AS VARCHAR) as disposition_code,
    CAST(Admin_AssignedDays AS INTEGER) as suspension_days,
    CAST(Admin_AssignedHours AS DECIMAL(5,2)) as suspension_hours,
    CAST(Admin_AssignedStartDate AS DATE) as admin_start_date,
    CAST(Admin_AssignedEndDate AS DATE) as admin_end_date,
    CAST(Demerits AS INTEGER) as demerits,

    CASE
        WHEN COALESCE(Admin_AssignedDays, 0) > 3 THEN 'High'
        WHEN COALESCE(Admin_AssignedDays, 0) BETWEEN 1 AND 3 THEN 'Medium'
        WHEN COALESCE(Admin_AssignedDays, 0) = 0 THEN 'Low'
        ELSE 'Unknown'
    END as severity_category,

    CASE
        WHEN COALESCE(Admin_AssignedDays, 0) > 0 THEN true
        ELSE false
    END as is_suspension,

    CURRENT_TIMESTAMP as dbt_load_timestamp,
    '{{ run_started_at }}' as dbt_run_timestamp
FROM {{ source('raw', 'raw_discipline') }}
WHERE CAST(IncidentID AS VARCHAR) != '0'  -- Filter invalid placeholder records
  AND StudentID IS NOT NULL
  AND IncidentID IS NOT NULL
