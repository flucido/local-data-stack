{{ config(
    materialized='view',
    schema='staging'
) }}

{#
  Staging model for CDE class assignment data by school.
  Source: cde_raw.cde_class_assignment
  Grain: school × year.
  Build cds_code from C + D + S parts via macro.
  Cast all count columns to INTEGER.
  SarcYear → academic_year.

  Metrics:
    PIMEL: Percent/Number of instructors misassigned in EL (English Learner) classes
    PINC: Percent/Number of instructors not credentialed
  Y1/Y2/Y3: Three-year historical columns.
#}

{% set cde_table = adapter.get_relation(database=target.database, schema='cde_raw', identifier='cde_class_assignment') %}

{% if cde_table is none %}

SELECT
    CAST(NULL AS VARCHAR) as cds_code,
    CAST(NULL AS VARCHAR) as county_code,
    CAST(NULL AS VARCHAR) as district_code,
    CAST(NULL AS VARCHAR) as school_code,
    CAST(NULL AS VARCHAR) as academic_year,
    CAST(NULL AS INTEGER) as pimel_y1,
    CAST(NULL AS INTEGER) as pimel_y2,
    CAST(NULL AS INTEGER) as pimel_y3,
    CAST(NULL AS INTEGER) as pinc_y1,
    CAST(NULL AS INTEGER) as pinc_y2,
    CAST(NULL AS INTEGER) as pinc_y3,
    CAST(NULL AS TIMESTAMP) as dlt_loaded_at,
    CAST(NULL AS VARCHAR) as source_filename,
    CURRENT_TIMESTAMP as dbt_loaded_at
WHERE 1 = 0

{% else %}

WITH source AS (
    SELECT * FROM {{ source('cde_raw', 'cde_class_assignment') }}
),

renamed AS (
    SELECT
        -- Build the 14-char CDS code from C/D/S parts
        {{ cde_build_cds_code('c', 'd', 's') }} as cds_code,
        c as county_code,
        d as district_code,
        s as school_code,

        -- Time
        sarcyear as academic_year,

        -- Class assignment counts (all cast to INTEGER)
        TRY_CAST(pimel_y1 AS INTEGER) as pimel_y1,
        TRY_CAST(pimel_y2 AS INTEGER) as pimel_y2,
        TRY_CAST(pimel_y3 AS INTEGER) as pimel_y3,

        TRY_CAST(pinc_y1 AS INTEGER) as pinc_y1,
        TRY_CAST(pinc_y2 AS INTEGER) as pinc_y2,
        TRY_CAST(pinc_y3 AS INTEGER) as pinc_y3,

        -- Metadata
        _loaded_at as dlt_loaded_at,
        _source_file as source_filename,
        CURRENT_TIMESTAMP as dbt_loaded_at

    FROM source
)

SELECT * FROM renamed

{% endif %}