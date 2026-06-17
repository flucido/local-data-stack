{{ config(
    materialized='view',
    schema='staging'
) }}

{#
  Staging model for CDE ELPAC Assessment Dashboard data.
  Source style: Style B — lowercase columns, pre-concatenated 14-char 'cds' code.
  Grain: school × year × student_group.
  Same pattern as ELA but with ELPAC-specific progression columns:
    currprogressed, pctcurrprogressed, currmaintainpl4, pctcurrmaintainpl4,
    currmaintainoth, pctcurrmaintainoth, currdeclined, pctcurrdeclined, currnumer.
  Map studentgroup → reporting_category, rtype → aggregate_level.
  cds is already the 14-char code.
  Cast currnumer/currdenom to INTEGER, currstatus to DOUBLE.
  Source: cde_raw.cde_assessment_elpac
#}

{% set cde_table = adapter.get_relation(database=target.database, schema='cde_raw', identifier='cde_assessment_elpac') %}

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
    CAST(NULL AS INTEGER) as curr_numer,
    CAST(NULL AS INTEGER) as curr_denom,
    CAST(NULL AS DOUBLE) as curr_status,
    CAST(NULL AS VARCHAR) as status_level,
    CAST(NULL AS VARCHAR) as academic_year,
    -- ELPAC-specific progression metrics
    CAST(NULL AS INTEGER) as curr_progressed,
    CAST(NULL AS DOUBLE) as pct_curr_progressed,
    CAST(NULL AS INTEGER) as curr_maintain_pl4,
    CAST(NULL AS DOUBLE) as pct_curr_maintain_pl4,
    CAST(NULL AS INTEGER) as curr_maintain_oth,
    CAST(NULL AS DOUBLE) as pct_curr_maintain_oth,
    CAST(NULL AS INTEGER) as curr_declined,
    CAST(NULL AS DOUBLE) as pct_curr_declined,
    -- Classification & metadata
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
    SELECT * FROM {{ source('cde_raw', 'cde_assessment_elpac') }}
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

        -- Core metrics
        TRY_CAST(currnumer AS INTEGER) as curr_numer,
        TRY_CAST(currdenom AS INTEGER) as curr_denom,
        TRY_CAST(currstatus AS DOUBLE) as curr_status,
        statuslevel as status_level,
        reportingyear as academic_year,

        -- ELPAC-specific progression metrics
        TRY_CAST(currprogressed AS INTEGER) as curr_progressed,
        TRY_CAST(pctcurrprogressed AS DOUBLE) as pct_curr_progressed,
        TRY_CAST(currmaintainpl4 AS INTEGER) as curr_maintain_pl4,
        TRY_CAST(pctcurrmaintainpl4 AS DOUBLE) as pct_curr_maintain_pl4,
        TRY_CAST(currmaintainoth AS INTEGER) as curr_maintain_oth,
        TRY_CAST(pctcurrmaintainoth AS DOUBLE) as pct_curr_maintain_oth,
        TRY_CAST(currdeclined AS INTEGER) as curr_declined,
        TRY_CAST(pctcurrdeclined AS DOUBLE) as pct_curr_declined,

        -- Data quality flags
        CASE
            WHEN currdenom = '*' THEN TRUE
            WHEN currstatus = '*' THEN TRUE
            WHEN currnumer = '*' THEN TRUE
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
