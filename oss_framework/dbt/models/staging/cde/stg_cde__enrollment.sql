{{ config(
    materialized='view',
    schema='staging'
) }}

{% set cde_table = adapter.get_relation(database=target.database, schema='cde_raw', identifier='cde_cumulative_enrollment') %}

{% if cde_table is none %}

SELECT
    CAST(NULL AS VARCHAR) as academic_year,
    CAST(NULL AS VARCHAR) as aggregate_level,
    CAST(NULL AS VARCHAR) as cds_code,
    CAST(NULL AS VARCHAR) as county_code,
    CAST(NULL AS VARCHAR) as district_code,
    CAST(NULL AS VARCHAR) as school_code,
    CAST(NULL AS VARCHAR) as county_name,
    CAST(NULL AS VARCHAR) as district_name,
    CAST(NULL AS VARCHAR) as school_name,
    CAST(NULL AS VARCHAR) as charter_school,
    CAST(NULL AS VARCHAR) as reporting_category,
    CAST(NULL AS VARCHAR) as reporting_category_label,
    CAST(NULL AS VARCHAR) as aggregate_level_label,
    CAST(NULL AS INTEGER) as cumulative_enrollment,
    CAST(NULL AS BOOLEAN) as is_suppressed,
    CAST(NULL AS BOOLEAN) as is_small_n,
    CAST(NULL AS BOOLEAN) as is_race_ethnicity_subgroup,
    CAST(NULL AS BOOLEAN) as is_gender_subgroup,
    CAST(NULL AS BOOLEAN) as is_atrisk_subgroup,
    CAST(NULL AS BOOLEAN) as is_grade_level_subgroup,
    CAST(NULL AS TIMESTAMP) as _loaded_at,
    CAST(NULL AS VARCHAR) as _source_file,
    CURRENT_TIMESTAMP as dbt_loaded_at
WHERE 1 = 0

{% else %}

WITH source AS (
    SELECT * FROM {{ source('cde_raw', 'cde_cumulative_enrollment') }}
),

renamed AS (
    SELECT
        -- Identifiers (dlt snake_case normalized from CDE Style A joined names)
        -- COALESCE handles BOM-aliased _academic_year from files loaded before
        -- the _strip_bom fix (cenroll2425-v2.txt had EF BB BF decoded as ï»¿ in latin1)
        COALESCE(academic_year, _academic_year) as academic_year,
        aggregate_level,
        {{ cde_build_cds_code('county_code', 'district_code', 'school_code') }} as cds_code,
        county_code,
        district_code,
        school_code,

        -- Names
        county_name,
        district_name,
        school_name,

        -- School characteristics
        charter as charter_school,

        -- Demographic/subgroup
        reporting_category,

        -- Metrics (TRY_CAST handles '*' suppression → NULL)
        TRY_CAST(cumulative_enrollment AS INTEGER) as cumulative_enrollment,

        -- Suppression flags (check enrollment column for '*' and < 11)
        {{ cde_suppression_flags(['cumulative_enrollment']) }},

        -- Metadata
        _loaded_at,
        _source_file,
        CURRENT_TIMESTAMP as dbt_loaded_at

    FROM source
),

final AS (
    SELECT
        *,
        {{ cde_reporting_category_label('reporting_category') }} as reporting_category_label,
        {{ cde_aggregate_level_label('aggregate_level') }} as aggregate_level_label,
        {{ cde_reporting_category_flags('reporting_category') }}
    FROM renamed
)

SELECT * FROM final

{% endif %}
