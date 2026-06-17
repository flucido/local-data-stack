{{ config(
    materialized='view',
    schema='staging'
) }}

{% set cde_table = adapter.get_relation(database=target.database, schema='cde_raw', identifier='cde_suspension') %}

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
    CAST(NULL AS INTEGER) as total_suspensions,
    CAST(NULL AS INTEGER) as unduplicated_count_of_students_suspended_total,
    CAST(NULL AS INTEGER) as unduplicated_count_of_students_suspended_defiance_only,
    CAST(NULL AS DOUBLE) as suspension_rate_total,
    CAST(NULL AS INTEGER) as suspension_count_violent_incident_injury,
    CAST(NULL AS INTEGER) as suspension_count_violent_incident_no_injury,
    CAST(NULL AS INTEGER) as suspension_count_weapons_possession,
    CAST(NULL AS INTEGER) as suspension_count_illicit_drug_related,
    CAST(NULL AS INTEGER) as suspension_count_defiance_only,
    CAST(NULL AS INTEGER) as suspension_count_other_reasons,
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
    SELECT * FROM {{ source('cde_raw', 'cde_suspension') }}
),

renamed AS (
    SELECT
        -- Identifiers (dlt snake_case normalized from CDE Style A joined names)
        academic_year,
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
        charter_yn as charter_school,

        -- Demographic/subgroup
        reporting_category,

        -- Metrics (TRY_CAST handles '*' suppression → NULL; x-suffix columns are CDE convention)
        TRY_CAST(cumulative_enrollment AS INTEGER) as cumulative_enrollment,
        TRY_CAST(total_suspensions AS INTEGER) as total_suspensions,
        TRY_CAST(unduplicated_count_of_students_suspended_totalx AS INTEGER) as unduplicated_count_of_students_suspended_total,
        TRY_CAST(unduplicated_count_of_students_suspended_defiance_onlyx AS INTEGER) as unduplicated_count_of_students_suspended_defiance_only,
        TRY_CAST(suspension_rate_totalx AS DOUBLE) as suspension_rate_total,
        TRY_CAST(suspension_count_violent_incident_injuryx AS INTEGER) as suspension_count_violent_incident_injury,
        TRY_CAST(suspension_count_violent_incident_no_injuryx AS INTEGER) as suspension_count_violent_incident_no_injury,
        TRY_CAST(suspension_count_weapons_possession AS INTEGER) as suspension_count_weapons_possession,
        TRY_CAST(suspension_count_illicit_drug_related AS INTEGER) as suspension_count_illicit_drug_related,
        TRY_CAST(suspension_count_defiance_only AS INTEGER) as suspension_count_defiance_only,
        TRY_CAST(suspension_count_other_reasons AS INTEGER) as suspension_count_other_reasons,

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
