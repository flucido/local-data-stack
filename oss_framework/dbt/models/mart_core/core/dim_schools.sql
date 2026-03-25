
-- models/mart_core/core/dim_schools.sql
-- Dimension: School reference data with CDE mappings

{{ config(
    materialized='table',
    schema='core',
    unique_key='school_id',
    tags=['core', 'dimensions', 'schools']
) }}

WITH base_schools AS (
    SELECT DISTINCT
        school_id,
        'SCHOOL_' || school_id as school_name
    FROM {{ ref('stg_aeries__students') }}
    
    UNION
    
    SELECT DISTINCT
        school_id,
        'SCHOOL_' || school_id as school_name
    FROM {{ ref('stg_aeries__attendance') }}
)

SELECT
    s.school_id,
    s.school_name,
    m.cds_code,
    m.cde_school_name,
    m.cde_district_name,
    m.cde_city,
    m.cde_county,
    m.latitude,
    m.longitude,
    m.match_method,
    m.match_confidence,
    m.is_mapped,
    CURRENT_TIMESTAMP as dbt_processed_date

FROM base_schools s
LEFT JOIN {{ ref('dim_school_cds_mapping') }} m
    ON s.school_id = m.school_id

