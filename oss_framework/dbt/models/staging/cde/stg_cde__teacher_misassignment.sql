{{ config(
    materialized='view',
    schema='staging'
) }}

{#
  Staging model for CDE teacher misassignment counts by school.
  Source: cde_raw.cde_teacher_misassignment
  Grain: school × year.
  Build cds_code from C + D + S parts via macro.
  Cast all count columns to INTEGER.
  SarcYear → academic_year.

  Metrics:
    NAAPW: Number of assignments with personnel working out-of-field
    NAAMS: Number of assignments with misassigned staff
    NAAVP: Number of assignments with vacant positions
    NAATT: Number of assignments with total teacher misassignments
  Y1/Y2/Y3: Three-year historical columns.
#}

{% set cde_table = adapter.get_relation(database=target.database, schema='cde_raw', identifier='cde_teacher_misassignment') %}

{% if cde_table is none %}

SELECT
    CAST(NULL AS VARCHAR) as cds_code,
    CAST(NULL AS VARCHAR) as county_code,
    CAST(NULL AS VARCHAR) as district_code,
    CAST(NULL AS VARCHAR) as school_code,
    CAST(NULL AS VARCHAR) as academic_year,
    CAST(NULL AS INTEGER) as naapw_y1,
    CAST(NULL AS INTEGER) as naapw_y2,
    CAST(NULL AS INTEGER) as naapw_y3,
    CAST(NULL AS INTEGER) as naams_y1,
    CAST(NULL AS INTEGER) as naams_y2,
    CAST(NULL AS INTEGER) as naams_y3,
    CAST(NULL AS INTEGER) as naavp_y1,
    CAST(NULL AS INTEGER) as naavp_y2,
    CAST(NULL AS INTEGER) as naavp_y3,
    CAST(NULL AS INTEGER) as naatt_y1,
    CAST(NULL AS INTEGER) as naatt_y2,
    CAST(NULL AS INTEGER) as naatt_y3,
    CAST(NULL AS TIMESTAMP) as dlt_loaded_at,
    CAST(NULL AS VARCHAR) as source_filename,
    CURRENT_TIMESTAMP as dbt_loaded_at
WHERE 1 = 0

{% else %}

WITH source AS (
    SELECT * FROM {{ source('cde_raw', 'cde_teacher_misassignment') }}
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

        -- Misassignment counts (all cast to INTEGER)
        TRY_CAST(naapw_y1 AS INTEGER) as naapw_y1,
        TRY_CAST(naapw_y2 AS INTEGER) as naapw_y2,
        TRY_CAST(naapw_y3 AS INTEGER) as naapw_y3,

        TRY_CAST(naams_y1 AS INTEGER) as naams_y1,
        TRY_CAST(naams_y2 AS INTEGER) as naams_y2,
        TRY_CAST(naams_y3 AS INTEGER) as naams_y3,

        TRY_CAST(naavp_y1 AS INTEGER) as naavp_y1,
        TRY_CAST(naavp_y2 AS INTEGER) as naavp_y2,
        TRY_CAST(naavp_y3 AS INTEGER) as naavp_y3,

        TRY_CAST(naatt_y1 AS INTEGER) as naatt_y1,
        TRY_CAST(naatt_y2 AS INTEGER) as naatt_y2,
        TRY_CAST(naatt_y3 AS INTEGER) as naatt_y3,

        -- Metadata
        _loaded_at as dlt_loaded_at,
        _source_file as source_filename,
        CURRENT_TIMESTAMP as dbt_loaded_at

    FROM source
)

SELECT * FROM renamed

{% endif %}