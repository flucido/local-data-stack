{{ config(
    materialized='view',
    schema='staging'
) }}

{#
  Staging model for CDE SARC enrollment counts by grade level.
  Source: cde_raw.cde_enrollment_by_grade
  Grain: school × year.
  Build cds_code from C + D + S parts via macro.
  Cast all grade counts and ENRTOTAL to INTEGER.
  SARCYear → academic_year.
#}

{% set cde_table = adapter.get_relation(database=target.database, schema='cde_raw', identifier='cde_enrollment_by_grade') %}

{% if cde_table is none %}

SELECT
    CAST(NULL AS VARCHAR) as cds_code,
    CAST(NULL AS VARCHAR) as county_code,
    CAST(NULL AS VARCHAR) as district_code,
    CAST(NULL AS VARCHAR) as school_code,
    CAST(NULL AS VARCHAR) as academic_year,
    CAST(NULL AS INTEGER) as kdgn,
    CAST(NULL AS INTEGER) as gr1,
    CAST(NULL AS INTEGER) as gr2,
    CAST(NULL AS INTEGER) as gr3,
    CAST(NULL AS INTEGER) as gr4,
    CAST(NULL AS INTEGER) as gr5,
    CAST(NULL AS INTEGER) as gr6,
    CAST(NULL AS INTEGER) as gr7,
    CAST(NULL AS INTEGER) as gr8,
    CAST(NULL AS INTEGER) as gr9,
    CAST(NULL AS INTEGER) as gr10,
    CAST(NULL AS INTEGER) as gr11,
    CAST(NULL AS INTEGER) as gr12,
    CAST(NULL AS INTEGER) as enr_total,
    CAST(NULL AS TIMESTAMP) as dlt_loaded_at,
    CAST(NULL AS VARCHAR) as source_filename,
    CURRENT_TIMESTAMP as dbt_loaded_at
WHERE 1 = 0

{% else %}

WITH source AS (
    SELECT * FROM {{ source('cde_raw', 'cde_enrollment_by_grade') }}
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

        -- Grade-level enrollment counts
        TRY_CAST(kdgn AS INTEGER) as kdgn,
        TRY_CAST(gr1 AS INTEGER) as gr1,
        TRY_CAST(gr2 AS INTEGER) as gr2,
        TRY_CAST(gr3 AS INTEGER) as gr3,
        TRY_CAST(gr4 AS INTEGER) as gr4,
        TRY_CAST(gr5 AS INTEGER) as gr5,
        TRY_CAST(gr6 AS INTEGER) as gr6,
        TRY_CAST(gr7 AS INTEGER) as gr7,
        TRY_CAST(gr8 AS INTEGER) as gr8,
        TRY_CAST(gr9 AS INTEGER) as gr9,
        TRY_CAST(gr10 AS INTEGER) as gr10,
        TRY_CAST(gr11 AS INTEGER) as gr11,
        TRY_CAST(gr12 AS INTEGER) as gr12,

        -- Total enrollment
        TRY_CAST(enrtotal AS INTEGER) as enr_total,

        -- Metadata
        _loaded_at as dlt_loaded_at,
        _source_file as source_filename,
        CURRENT_TIMESTAMP as dbt_loaded_at

    FROM source
)

SELECT * FROM renamed

{% endif %}
