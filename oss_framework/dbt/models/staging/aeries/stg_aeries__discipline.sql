-- models/staging/aeries/stg_aeries__discipline.sql
-- Staging: Standardize raw_discipline with schema normalization

{{ config(
    schema='staging',
    tags=['staging', 'discipline']
) }}

{% set raw_cols = (adapter.get_columns_in_relation(source('raw', 'raw_discipline')) | map(attribute='name') | map('lower') | list) if execute else [] %}

SELECT
    CAST(d.student_id AS VARCHAR) as student_id_raw,
    CAST(d.school_id AS VARCHAR) as school_id,
    CAST(d.incident_id AS VARCHAR) as incident_id,
    TRY_CAST(NULLIF(CAST(d.incident_date AS VARCHAR), '') AS DATE) as incident_date,
    CAST(d.incident_type AS VARCHAR) as incident_type,
    CAST(d.severity AS VARCHAR) as severity,
    CAST(d.resolution AS VARCHAR) as resolution,
    CAST(d.suspension_days AS INTEGER) as suspension_days,
    COALESCE(
        {% if 'academic_year' in raw_cols %}NULLIF(CAST(d.academic_year AS VARCHAR), ''),{% endif %}
        {% if 'school_year' in raw_cols %}NULLIF(CAST(d.school_year AS VARCHAR), ''),{% endif %}
        CASE
            WHEN TRY_CAST(NULLIF(CAST(d.incident_date AS VARCHAR), '') AS DATE) IS NOT NULL THEN
                CASE
                    WHEN MONTH(TRY_CAST(NULLIF(CAST(d.incident_date AS VARCHAR), '') AS DATE)) >= 7
                        THEN CAST(YEAR(TRY_CAST(NULLIF(CAST(d.incident_date AS VARCHAR), '') AS DATE)) AS VARCHAR) || '-' || CAST(YEAR(TRY_CAST(NULLIF(CAST(d.incident_date AS VARCHAR), '') AS DATE)) + 1 AS VARCHAR)
                    ELSE CAST(YEAR(TRY_CAST(NULLIF(CAST(d.incident_date AS VARCHAR), '') AS DATE)) - 1 AS VARCHAR) || '-' || CAST(YEAR(TRY_CAST(NULLIF(CAST(d.incident_date AS VARCHAR), '') AS DATE)) AS VARCHAR)
                END
            ELSE NULL
        END,
        '2024-2025'
    ) as academic_year,
    {% if 'disposition_code' in raw_cols %}CAST(d.disposition_code AS VARCHAR){% else %}CAST(NULL AS VARCHAR){% endif %} as disposition_code,
    {% if 'short_description' in raw_cols %}CAST(d.short_description AS VARCHAR){% else %}CAST(NULL AS VARCHAR){% endif %} as short_description,
    CASE
        WHEN d.severity IN ('Low', 'Medium', 'High') THEN d.severity
        ELSE 'Unknown'
    END as severity_category,
    CURRENT_TIMESTAMP as dbt_load_timestamp,
    '{{ run_started_at }}' as dbt_run_timestamp
FROM {{ source('raw', 'raw_discipline') }} d
