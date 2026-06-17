{{ config(
    materialized='view',
    schema='staging'
) }}

{#
  Staging model for CDE ELA Assessment Dashboard data.
  Source style: Style B — lowercase columns, pre-concatenated 14-char 'cds' code.
  Grain: school × year × student_group.
  Source: cde_raw.cde_assessment_ela
#}

{% set cde_table = adapter.get_relation(database=target.database, schema='cde_raw', identifier='cde_assessment_ela') %}

{% if cde_table is none %}

SELECT
    CAST(NULL AS VARCHAR) as cds_code,
    CAST(NULL AS VARCHAR) as aggregate_level,
    CAST(NULL AS VARCHAR) as school_name,
    CAST(NULL AS VARCHAR) as district_name,
    CAST(NULL AS VARCHAR) as county_name,
    CAST(NULL AS VARCHAR) as charter_flag,
    CAST(NULL AS VARCHAR) as coe_flag,
    CAST(NULL AS VARCHAR) as dass_flag,
    CAST(NULL AS VARCHAR) as reporting_category,
    CAST(NULL AS VARCHAR) as reporting_category_label,
    CAST(NULL AS INTEGER) as curr_denom,
    CAST(NULL AS DOUBLE) as curr_status,
    CAST(NULL AS VARCHAR) as status_level,
    CAST(NULL AS VARCHAR) as academic_year,
    CAST(NULL AS VARCHAR) as aggregate_level_label,
    CAST(NULL AS BOOLEAN) as is_race_ethnicity_subgroup,
    CAST(NULL AS BOOLEAN) as is_gender_subgroup,
    CAST(NULL AS BOOLEAN) as is_atrisk_subgroup,
    CAST(NULL AS BOOLEAN) as is_grade_level_subgroup,
    CAST(NULL AS BOOLEAN) as is_suppressed,
    CAST(NULL AS BOOLEAN) as is_small_n,
    CAST(NULL AS TIMESTAMP) as dlt_loaded_at,
    CAST(NULL AS VARCHAR) as source_filename,
    CURRENT_TIMESTAMP as dbt_loaded_at
WHERE 1 = 0

{% else %}

WITH source AS (
    SELECT * FROM {{ source('cde_raw', 'cde_assessment_ela') }}
),

renamed AS (
    SELECT
        -- Identifiers (Style B: 'cds' is already the 14-char code)
        cds as cds_code,
        rtype as aggregate_level,
        schoolname as school_name,
        districtname as district_name,
        countyname as county_name,

        -- School characteristics flags
        charter_flag,
        coe_flag,
        dass_flag,

        -- Demographic / subgroup
        studentgroup as reporting_category,
        {{ cde_reporting_category_label('studentgroup') }} as reporting_category_label,

        -- Metrics
        TRY_CAST(currdenom AS INTEGER) as curr_denom,
        TRY_CAST(currstatus AS DOUBLE) as curr_status,
        statuslevel as status_level,
        reportingyear as academic_year,

        -- Data quality flags
        CASE
            WHEN currdenom = '*' THEN TRUE
            WHEN currstatus = '*' THEN TRUE
            ELSE FALSE
        END as is_suppressed,

        CASE
            WHEN TRY_CAST(currdenom AS INTEGER) < 11 THEN TRUE
            ELSE FALSE
        END as is_small_n,

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
