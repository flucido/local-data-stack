{{ config(
    materialized='view',
    schema='staging'
) }}

{% set cde_table = adapter.get_relation(database=target.database, schema='cde_raw', identifier='cde_homeless_enrollment') %}

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
    CAST(NULL AS VARCHAR) as dashboard_alternative_school_status,
    CAST(NULL AS VARCHAR) as reporting_category,
    CAST(NULL AS VARCHAR) as reporting_category_label,
    CAST(NULL AS VARCHAR) as aggregate_level_label,
    CAST(NULL AS INTEGER) as cumulative_enrollment,
    CAST(NULL AS INTEGER) as homeless_student_enrollment,
    CAST(NULL AS INTEGER) as temporarily_doubled_up,
    CAST(NULL AS INTEGER) as temporary_shelters,
    CAST(NULL AS INTEGER) as hotels_motels,
    CAST(NULL AS INTEGER) as temporarily_unsheltered,
    CAST(NULL AS INTEGER) as missing_unknown,
    CAST(NULL AS DOUBLE) as temporarily_doubled_up_percent,
    CAST(NULL AS DOUBLE) as temporary_shelters_percent,
    CAST(NULL AS DOUBLE) as hotels_motels_percent,
    CAST(NULL AS DOUBLE) as temporarily_unsheltered_percent,
    CAST(NULL AS DOUBLE) as missing_unknown_percent,
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
    SELECT * FROM {{ source('cde_raw', 'cde_homeless_enrollment') }}
),

renamed AS (
    SELECT
        -- Identifiers
        -- COALESCE handles BOM-aliased _academic_year from files loaded before
        -- the _strip_bom fix (hse2324.txt had EF BB BF decoded as ï»¿ in latin1)
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
        charter_school,
        dass as dashboard_alternative_school_status,

        -- Demographic/subgroup
        reporting_category,

        -- Metrics: counts (TRY_CAST handles '*' suppression → NULL)
        TRY_CAST(cumulative_enrollment AS INTEGER) as cumulative_enrollment,
        TRY_CAST(homeless_student_enrollment AS INTEGER) as homeless_student_enrollment,
        TRY_CAST(temporarily_doubled_up AS INTEGER) as temporarily_doubled_up,
        TRY_CAST(temporary_shelters AS INTEGER) as temporary_shelters,
        TRY_CAST(hotels_motels AS INTEGER) as hotels_motels,
        TRY_CAST(temporarily_unsheltered AS INTEGER) as temporarily_unsheltered,
        TRY_CAST(missing_unknown AS INTEGER) as missing_unknown,

        -- Metrics: percents (CDE appends 'x' to percent column names)
        TRY_CAST(temporarily_doubled_up_percentx AS DOUBLE) as temporarily_doubled_up_percent,
        TRY_CAST(temporary_shelters_percentx AS DOUBLE) as temporary_shelters_percent,
        TRY_CAST(hotels_motels_percentx AS DOUBLE) as hotels_motels_percent,
        TRY_CAST(temporarily_unsheltered_percentx AS DOUBLE) as temporarily_unsheltered_percent,
        TRY_CAST(missing_unknown_percentx AS DOUBLE) as missing_unknown_percent,

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
