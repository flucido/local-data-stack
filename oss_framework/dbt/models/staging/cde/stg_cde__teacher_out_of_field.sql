{{ config(
    materialized='view',
    schema='staging'
) }}

{#
  Staging model for CDE teacher out-of-field counts by school.
  Source: cde_raw.cde_teacher_out_of_field
  Grain: school × year.
  Build cds_code from C + D + S parts via macro.
  Cast all count columns to INTEGER.
  SARCYear → academic_year.

  Metrics:
    NICTA: Number of inappropriate credential teacher assignments
    NILAO: Number of instructors lacking appropriate credentials (other)
    NIOOF: Number of instructors out-of-field
  Y1/Y2/Y3: Three-year historical columns.
#}

{% set cde_table = adapter.get_relation(database=target.database, schema='cde_raw', identifier='cde_teacher_out_of_field') %}

{% if cde_table is none %}

SELECT
    CAST(NULL AS VARCHAR) as cds_code,
    CAST(NULL AS VARCHAR) as county_code,
    CAST(NULL AS VARCHAR) as district_code,
    CAST(NULL AS VARCHAR) as school_code,
    CAST(NULL AS VARCHAR) as academic_year,
    CAST(NULL AS INTEGER) as nicta_y1,
    CAST(NULL AS INTEGER) as nicta_y2,
    CAST(NULL AS INTEGER) as nicta_y3,
    CAST(NULL AS INTEGER) as nilao_y1,
    CAST(NULL AS INTEGER) as nilao_y2,
    CAST(NULL AS INTEGER) as nilao_y3,
    CAST(NULL AS INTEGER) as nioof_y1,
    CAST(NULL AS INTEGER) as nioof_y2,
    CAST(NULL AS INTEGER) as nioof_y3,
    CAST(NULL AS TIMESTAMP) as dlt_loaded_at,
    CAST(NULL AS VARCHAR) as source_filename,
    CURRENT_TIMESTAMP as dbt_loaded_at
WHERE 1 = 0

{% else %}

WITH source AS (
    SELECT * FROM {{ source('cde_raw', 'cde_teacher_out_of_field') }}
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

        -- Out-of-field counts (all cast to INTEGER)
        TRY_CAST(nicta_y1 AS INTEGER) as nicta_y1,
        TRY_CAST(nicta_y2 AS INTEGER) as nicta_y2,
        TRY_CAST(nicta_y3 AS INTEGER) as nicta_y3,

        TRY_CAST(nilao_y1 AS INTEGER) as nilao_y1,
        TRY_CAST(nilao_y2 AS INTEGER) as nilao_y2,
        TRY_CAST(nilao_y3 AS INTEGER) as nilao_y3,

        TRY_CAST(nioof_y1 AS INTEGER) as nioof_y1,
        TRY_CAST(nioof_y2 AS INTEGER) as nioof_y2,
        TRY_CAST(nioof_y3 AS INTEGER) as nioof_y3,

        -- Metadata
        _loaded_at as dlt_loaded_at,
        _source_file as source_filename,
        CURRENT_TIMESTAMP as dbt_loaded_at

    FROM source
)

SELECT * FROM renamed

{% endif %}