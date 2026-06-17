{{ config(
    materialized='view',
    schema='staging'
) }}

{#
  Staging model for CDE Free/Reduced Price Meals (FRPM) data.
  Source style: Excel files loaded via openpyxl.
  Grain: school × year (NO reporting_category — this is school-level aggregate data).
  No reporting_category column exists in source — default to 'TA' (Total All Students).
  Build cds_code from county/district/school codes via macro.
  Source: cde_raw.cde_frpm
#}

{% set cde_table = adapter.get_relation(database=target.database, schema='cde_raw', identifier='cde_frpm') %}

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
    -- School characteristics
    CAST(NULL AS VARCHAR) as district_type,
    CAST(NULL AS VARCHAR) as school_type,
    CAST(NULL AS VARCHAR) as educational_option_type,
    CAST(NULL AS VARCHAR) as nslp_provision_status,
    CAST(NULL AS VARCHAR) as charter_school,
    CAST(NULL AS VARCHAR) as charter_number,
    CAST(NULL AS VARCHAR) as charter_funding_type,
    CAST(NULL AS VARCHAR) as irc,
    CAST(NULL AS VARCHAR) as low_grade,
    CAST(NULL AS VARCHAR) as high_grade,
    -- K-12 metrics
    CAST(NULL AS INTEGER) as enrollment_k12,
    CAST(NULL AS INTEGER) as free_meal_count_k12,
    CAST(NULL AS DOUBLE) as percent_eligible_free_k12,
    CAST(NULL AS INTEGER) as frpm_count_k12,
    CAST(NULL AS DOUBLE) as percent_eligible_frpm_k12,
    -- Ages 5-17 metrics
    CAST(NULL AS INTEGER) as enrollment_ages_5_17,
    CAST(NULL AS INTEGER) as free_meal_count_ages_5_17,
    CAST(NULL AS DOUBLE) as percent_eligible_free_ages_5_17,
    CAST(NULL AS INTEGER) as frpm_count_ages_5_17,
    CAST(NULL AS DOUBLE) as percent_eligible_frpm_ages_5_17,
    -- Other
    CAST(NULL AS VARCHAR) as calpads_certification_status,
    -- Reporting category (default TA — no subgroup dimension in source)
    CAST(NULL AS VARCHAR) as reporting_category,
    CAST(NULL AS VARCHAR) as reporting_category_label,
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
    SELECT * FROM {{ source('cde_raw', 'cde_frpm') }}
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

        -- Time
        academic_year,

        -- School characteristics
        district_type,
        school_type,
        educational_option_type,
        nslp_provision_status,
        charter_school,
        charter_number,
        charter_funding_type,
        irc,
        low_grade,
        high_grade,

        -- K-12 metrics (enrollment/meal counts → INTEGER, percentages → DOUBLE)
        TRY_CAST(enrollment_k12 AS INTEGER) as enrollment_k12,
        TRY_CAST(free_meal_count_k12 AS INTEGER) as free_meal_count_k12,
        TRY_CAST(percent_eligible_free_k12 AS DOUBLE) as percent_eligible_free_k12,
        TRY_CAST(frpm_count_k12 AS INTEGER) as frpm_count_k12,
        TRY_CAST(percent_eligible_frpm_k12 AS DOUBLE) as percent_eligible_frpm_k12,

        -- Ages 5-17 metrics
        TRY_CAST(enrollment_ages_5_17 AS INTEGER) as enrollment_ages_5_17,
        TRY_CAST(free_meal_count_ages_5_17 AS INTEGER) as free_meal_count_ages_5_17,
        TRY_CAST(percent_eligible_free_ages_5_17 AS DOUBLE) as percent_eligible_free_ages_5_17,
        TRY_CAST(frpm_count_ages_5_17 AS INTEGER) as frpm_count_ages_5_17,
        TRY_CAST(percent_eligible_frpm_ages_5_17 AS DOUBLE) as percent_eligible_frpm_ages_5_17,

        -- Certification
        calpads_certification_status,

        -- Metadata
        _loaded_at as dlt_loaded_at,
        _source_file as source_filename

    FROM source
),

final AS (
    SELECT
        *,
        -- FRPM has no reporting_category column — default to 'TA' (Total All Students)
        'TA' as reporting_category,
        {{ cde_reporting_category_label("'TA'") }} as reporting_category_label,
        CURRENT_TIMESTAMP as dbt_loaded_at,
        {{ cde_reporting_category_flags("'TA'") }}
    FROM renamed
)

SELECT * FROM final

{% endif %}
