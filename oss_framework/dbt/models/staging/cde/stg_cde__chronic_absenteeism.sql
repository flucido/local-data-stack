{{ config(
    materialized='view',
    schema='staging'
) }}

{% set cde_table = adapter.get_relation(database=target.database, schema='cde_raw', identifier='cde_chronic_absenteeism') %}

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
    CAST(NULL AS INTEGER) as eligible_enrollment,
    CAST(NULL AS INTEGER) as chronic_absent_count,
    CAST(NULL AS DOUBLE) as chronic_absent_rate_pct,
    CAST(NULL AS BOOLEAN) as is_suppressed,
    CAST(NULL AS BOOLEAN) as is_small_n,
    CAST(NULL AS TIMESTAMP) as dlt_loaded_at,
    CAST(NULL AS VARCHAR) as source_filename,
    CAST(NULL AS VARCHAR) as dlt_load_id,
    CURRENT_TIMESTAMP as dbt_loaded_at,
    CAST(NULL AS VARCHAR) as aggregate_level_label,
    CAST(NULL AS VARCHAR) as grade_level_group,
    CAST(NULL AS BOOLEAN) as is_race_ethnicity_subgroup,
    CAST(NULL AS BOOLEAN) as is_gender_subgroup,
    CAST(NULL AS BOOLEAN) as is_atrisk_subgroup
WHERE 1 = 0

{% else %}

WITH source AS (
    SELECT * FROM {{ source('cde_raw', 'cde_chronic_absenteeism') }}
),

renamed AS (
    SELECT
        -- Identifiers
        academic_year,
        aggregate_level,
        CONCAT(
            LPAD(COALESCE(county_code, ''), 2, '0'),
            LPAD(COALESCE(district_code, ''), 5, '0'),
            LPAD(COALESCE(school_code, ''), 7, '0')
        ) as cds_code,
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

        -- Demographic/Subgroup (use shared macro for label)
        reporting_category,
        {{ cde_reporting_category_label('reporting_category') }} as reporting_category_label,

        -- Metrics (cast to appropriate types, handling suppressed values)
        TRY_CAST(chronic_absenteeism_eligible_cumulative_enrollment AS INTEGER) as eligible_enrollment,
        TRY_CAST(chronic_absenteeism_count AS INTEGER) as chronic_absent_count,
        TRY_CAST(chronic_absenteeism_rate AS DOUBLE) as chronic_absent_rate_pct,

        -- Flags for data quality
        CASE
            WHEN chronic_absenteeism_eligible_cumulative_enrollment = '*' THEN TRUE
            WHEN chronic_absenteeism_count = '*' THEN TRUE
            WHEN chronic_absenteeism_rate = '*' THEN TRUE
            ELSE FALSE
        END as is_suppressed,

        CASE
            WHEN TRY_CAST(chronic_absenteeism_eligible_cumulative_enrollment AS INTEGER) < 11 THEN TRUE
            ELSE FALSE
        END as is_small_n,

        -- Metadata
        _loaded_at as dlt_loaded_at,
        _source_file as source_filename,
        _dlt_load_id as dlt_load_id,
        CURRENT_TIMESTAMP as dbt_loaded_at

    FROM source
),

final AS (
    SELECT
        *,
        {{ cde_aggregate_level_label('aggregate_level') }} as aggregate_level_label,
        {{ cde_reporting_category_flags('reporting_category') }},
        -- Grade level group label (derived from reporting_category GR* codes)
        CASE
            WHEN reporting_category IN ('GRTKKN', 'GRKN') THEN 'TK/Kindergarten'
            WHEN reporting_category = 'GR13' THEN 'Grades 1-3'
            WHEN reporting_category = 'GR46' THEN 'Grades 4-6'
            WHEN reporting_category = 'GR78' THEN 'Grades 7-8'
            WHEN reporting_category = 'GR912' THEN 'Grades 9-12'
            WHEN reporting_category IN ('GRTK8', 'GRK8') THEN 'TK-8'
            ELSE NULL
        END as grade_level_group
    FROM renamed
)

SELECT * FROM final

{% endif %}
