{{ config(
    materialized='view',
    schema='staging'
) }}

{#
  Staging model for CDE SARC enrollment percentages by demographic subgroup.
  Source: cde_raw.cde_enrollment_by_subgroup
  Grain: school × year.
  Build cds_code from C + D + S parts via macro.
  All PER* columns are percentages — cast to DOUBLE.
  SARCYear → academic_year.
#}

{% set cde_table = adapter.get_relation(database=target.database, schema='cde_raw', identifier='cde_enrollment_by_subgroup') %}

{% if cde_table is none %}

SELECT
    CAST(NULL AS VARCHAR) as cds_code,
    CAST(NULL AS VARCHAR) as county_code,
    CAST(NULL AS VARCHAR) as district_code,
    CAST(NULL AS VARCHAR) as school_code,
    CAST(NULL AS VARCHAR) as academic_year,
    CAST(NULL AS DOUBLE) as per_gf,
    CAST(NULL AS DOUBLE) as per_gm,
    CAST(NULL AS DOUBLE) as per_gx,
    CAST(NULL AS DOUBLE) as per_ai,
    CAST(NULL AS DOUBLE) as per_as,
    CAST(NULL AS DOUBLE) as per_aa,
    CAST(NULL AS DOUBLE) as per_fi,
    CAST(NULL AS DOUBLE) as per_hi,
    CAST(NULL AS DOUBLE) as per_pi,
    CAST(NULL AS DOUBLE) as per_multi,
    CAST(NULL AS DOUBLE) as per_wh,
    CAST(NULL AS DOUBLE) as per_el,
    CAST(NULL AS DOUBLE) as per_fy,
    CAST(NULL AS DOUBLE) as per_h,
    CAST(NULL AS DOUBLE) as per_mig,
    CAST(NULL AS DOUBLE) as per_sd,
    CAST(NULL AS DOUBLE) as per_di,
    CAST(NULL AS TIMESTAMP) as dlt_loaded_at,
    CAST(NULL AS VARCHAR) as source_filename,
    CURRENT_TIMESTAMP as dbt_loaded_at
WHERE 1 = 0

{% else %}

WITH source AS (
    SELECT * FROM {{ source('cde_raw', 'cde_enrollment_by_subgroup') }}
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

        -- Subgroup percentages (all cast to DOUBLE)
        TRY_CAST(pergf AS DOUBLE) as per_gf,
        TRY_CAST(pergm AS DOUBLE) as per_gm,
        TRY_CAST(pergx AS DOUBLE) as per_gx,
        TRY_CAST(perai AS DOUBLE) as per_ai,
        TRY_CAST(peras AS DOUBLE) as per_as,
        TRY_CAST(peraa AS DOUBLE) as per_aa,
        TRY_CAST(perfi AS DOUBLE) as per_fi,
        TRY_CAST(perhi AS DOUBLE) as per_hi,
        TRY_CAST(perpi AS DOUBLE) as per_pi,
        TRY_CAST(permulti AS DOUBLE) as per_multi,
        TRY_CAST(perwh AS DOUBLE) as per_wh,
        TRY_CAST(perel AS DOUBLE) as per_el,
        TRY_CAST(perfy AS DOUBLE) as per_fy,
        TRY_CAST(perh AS DOUBLE) as per_h,
        TRY_CAST(permig AS DOUBLE) as per_mig,
        TRY_CAST(persd AS DOUBLE) as per_sd,
        TRY_CAST(perdi AS DOUBLE) as per_di,

        -- Metadata
        _loaded_at as dlt_loaded_at,
        _source_file as source_filename,
        CURRENT_TIMESTAMP as dbt_loaded_at

    FROM source
)

SELECT * FROM renamed

{% endif %}