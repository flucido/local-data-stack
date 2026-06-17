{{ config(
    materialized='view',
    schema='staging'
) }}

{#
  Staging model for CDE Restraint & Seclusion data.
  Source style: Excel files (sheet4).
  Grain: school × year × reporting_category.
  Build cds_code from county/district/school codes via macro.
  Use shared macros for reporting category labels and flags.
  Cast all counts to INTEGER.
  Source: cde_raw.cde_restraint_seclusion
#}

{% set cde_table = adapter.get_relation(database=target.database, schema='cde_raw', identifier='cde_restraint_seclusion') %}

{% if cde_table is none %}

SELECT
    CAST(NULL AS VARCHAR) as cds_code,
    CAST(NULL AS VARCHAR) as county_code,
    CAST(NULL AS VARCHAR) as district_code,
    CAST(NULL AS VARCHAR) as school_code,
    CAST(NULL AS VARCHAR) as county_name,
    CAST(NULL AS VARCHAR) as district_name,
    CAST(NULL AS VARCHAR) as school_name,
    CAST(NULL AS VARCHAR) as academic_year,
    CAST(NULL AS VARCHAR) as aggregate_level,
    CAST(NULL AS VARCHAR) as nps,
    CAST(NULL AS VARCHAR) as reporting_category,
    CAST(NULL AS VARCHAR) as reporting_category_label,
    -- Counts (INTEGER)
    CAST(NULL AS INTEGER) as count_of_mechanical_restraints,
    CAST(NULL AS INTEGER) as unduplicated_count_of_students_mechanical,
    CAST(NULL AS INTEGER) as count_of_physical_restraints,
    CAST(NULL AS INTEGER) as unduplicated_count_of_students_physical,
    CAST(NULL AS INTEGER) as count_of_seclusions,
    -- Classification & metadata
    CAST(NULL AS VARCHAR) as aggregate_level_label,
    CAST(NULL AS BOOLEAN) as is_race_ethnicity_subgroup,
    CAST(NULL AS BOOLEAN) as is_gender_subgroup,
    CAST(NULL AS BOOLEAN) as is_atrisk_subgroup,
    CAST(NULL AS BOOLEAN) as is_grade_level_subgroup,
    CAST(NULL AS TIMESTAMP) as dlt_loaded_at,
    CAST(NULL AS VARCHAR) as source_filename,
    CURRENT_TIMESTAMP as dbt_loaded_at
WHERE 1 = 0

{% else %}

WITH source AS (
    SELECT * FROM {{ source('cde_raw', 'cde_restraint_seclusion') }}
),

renamed AS (
    SELECT
        -- Build the 14-char CDS code from county/district/school parts
        {{ cde_build_cds_code('county_code', 'district_code', 'school_code') }} as cds_code,
        county_code,
        district_code,
        school_code,

        -- Names
        county_name,
        district_name,
        school_name,

        -- Time & level
        academic_year,
        aggregate_level,

        -- Non-public school indicator
        nps,

        -- Demographic / subgroup
        reporting_category,
        {{ cde_reporting_category_label('reporting_category') }} as reporting_category_label,

        -- Counts (cast to INTEGER)
        TRY_CAST(count_of_mechanical_restraints AS INTEGER) as count_of_mechanical_restraints,
        TRY_CAST(unduplicated_count_of_students_mechanical AS INTEGER) as unduplicated_count_of_students_mechanical,
        TRY_CAST(count_of_physical_restraints AS INTEGER) as count_of_physical_restraints,
        TRY_CAST(unduplicated_count_of_students_physical AS INTEGER) as unduplicated_count_of_students_physical,
        TRY_CAST(count_of_seclusions AS INTEGER) as count_of_seclusions,

        -- Metadata
        _loaded_at as dlt_loaded_at,
        _source_file as source_filename

    FROM source
),

final AS (
    SELECT
        *,
        {{ cde_aggregate_level_label('aggregate_level') }} as aggregate_level_label,
        {{ cde_reporting_category_flags('reporting_category') }}
    FROM renamed
)

SELECT * FROM final

{% endif %}