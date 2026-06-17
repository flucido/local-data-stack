{{ config(
    materialized='view',
    schema='staging'
) }}

{% set cde_table = adapter.get_relation(database=target.database, schema='cde_raw', identifier='cde_absenteeism_reason') %}

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
    CAST(NULL AS INTEGER) as eligible_cumulative_enrollment,
    CAST(NULL AS INTEGER) as count_of_students_with_one_or_more_absences,
    CAST(NULL AS DOUBLE) as average_days_absent,
    CAST(NULL AS INTEGER) as total_days_absent,
    CAST(NULL AS DOUBLE) as excused_absences_percent,
    CAST(NULL AS DOUBLE) as unexcused_absences_percent,
    CAST(NULL AS DOUBLE) as out_of_school_suspension_absences_percent,
    CAST(NULL AS DOUBLE) as incomplete_independent_study_absences_percent,
    CAST(NULL AS INTEGER) as excused_absences_count,
    CAST(NULL AS INTEGER) as unexcused_absences_count,
    CAST(NULL AS INTEGER) as out_of_school_suspension_absences_count,
    CAST(NULL AS INTEGER) as incomplete_independent_study_absences_count,
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
    SELECT * FROM {{ source('cde_raw', 'cde_absenteeism_reason') }}
),

renamed AS (
    SELECT
        -- Identifiers
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
        charter_school,
        dass as dashboard_alternative_school_status,

        -- Demographic/subgroup
        reporting_category,

        -- Metrics (TRY_CAST handles '*' suppression → NULL)
        TRY_CAST(eligible_cumulative_enrollment AS INTEGER) as eligible_cumulative_enrollment,
        TRY_CAST(count_of_students_with_one_or_more_absences AS INTEGER) as count_of_students_with_one_or_more_absences,
        TRY_CAST(average_days_absent AS DOUBLE) as average_days_absent,
        TRY_CAST(total_days_absent AS INTEGER) as total_days_absent,
        TRY_CAST(excused_absences_percent AS DOUBLE) as excused_absences_percent,
        TRY_CAST(unexcused_absences_percent AS DOUBLE) as unexcused_absences_percent,
        TRY_CAST(out_of_school_suspension_absences_percent AS DOUBLE) as out_of_school_suspension_absences_percent,
        TRY_CAST(incomplete_independent_study_absences_percent AS DOUBLE) as incomplete_independent_study_absences_percent,
        TRY_CAST(excused_absences_count AS INTEGER) as excused_absences_count,
        TRY_CAST(unexcused_absences_count AS INTEGER) as unexcused_absences_count,
        TRY_CAST(out_of_school_suspension_absences_count AS INTEGER) as out_of_school_suspension_absences_count,
        TRY_CAST(incomplete_independent_study_absences_count AS INTEGER) as incomplete_independent_study_absences_count,

        -- Suppression flags (check enrollment column for '*' and < 11)
        {{ cde_suppression_flags(['eligible_cumulative_enrollment']) }},

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