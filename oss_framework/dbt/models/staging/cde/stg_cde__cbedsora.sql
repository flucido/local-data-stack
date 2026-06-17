{{ config(
    materialized='view',
    schema='staging'
) }}

{#
  Staging model for CDE CBEDS ORA staff demographics by school.
  Source: cde_raw.cde_cbedsora
  Grain: school × year × row (staff demographic breakdown rows).
  cdscode is already the full 14-char CDS code — no need to build from parts.
  Note: 'a' files have race breakdown (18 cols), 'b' files have totals (10 cols).
  The loader unions them so some race-count columns may be NULL for 'b' rows.
  Description, Level, Section are kept as analytical categoricals.
#}

{% set cde_table = adapter.get_relation(database=target.database, schema='cde_raw', identifier='cde_cbedsora') %}

{% if cde_table is none %}

SELECT
    CAST(NULL AS VARCHAR) as cds_code,
    CAST(NULL AS VARCHAR) as county_name,
    CAST(NULL AS VARCHAR) as district_name,
    CAST(NULL AS VARCHAR) as school_name,
    CAST(NULL AS VARCHAR) as description,
    CAST(NULL AS VARCHAR) as level,
    CAST(NULL AS VARCHAR) as section,
    CAST(NULL AS INTEGER) as row_number,
    CAST(NULL AS INTEGER) as american_indian,
    CAST(NULL AS INTEGER) as asian,
    CAST(NULL AS INTEGER) as pacific_islander,
    CAST(NULL AS INTEGER) as filipino,
    CAST(NULL AS INTEGER) as hispanic,
    CAST(NULL AS INTEGER) as african_american,
    CAST(NULL AS INTEGER) as white,
    CAST(NULL AS INTEGER) as mult_or_no_resp,
    CAST(NULL AS INTEGER) as total,
    CAST(NULL AS VARCHAR) as academic_year,
    CAST(NULL AS TIMESTAMP) as dlt_loaded_at,
    CAST(NULL AS VARCHAR) as source_filename,
    CURRENT_TIMESTAMP as dbt_loaded_at
WHERE 1 = 0

{% else %}

WITH source AS (
    SELECT * FROM {{ source('cde_raw', 'cde_cbedsora') }}
),

renamed AS (
    SELECT
        -- Identifier (cdscode is already the full 14-char CDS code)
        cdscode as cds_code,

        -- Names
        countyname as county_name,
        districtname as district_name,
        schoolname as school_name,

        -- Analytical categoricals
        description,
        level,
        section,

        -- Row identifier
        TRY_CAST(rownumber AS INTEGER) as row_number,

        -- Race/ethnicity counts (may be NULL for 'b' file rows — totals only)
        TRY_CAST(americanindian AS INTEGER) as american_indian,
        TRY_CAST(asian AS INTEGER) as asian,
        TRY_CAST(pacificislander AS INTEGER) as pacific_islander,
        TRY_CAST(filipino AS INTEGER) as filipino,
        TRY_CAST(hispanic AS INTEGER) as hispanic,
        TRY_CAST(africanamerican AS INTEGER) as african_american,
        TRY_CAST(white AS INTEGER) as white,
        TRY_CAST(multornoresp AS INTEGER) as mult_or_no_resp,

        -- Total staff count
        TRY_CAST(total AS INTEGER) as total,

        -- Time
        year as academic_year,

        -- Metadata
        _loaded_at as dlt_loaded_at,
        _source_file as source_filename,
        CURRENT_TIMESTAMP as dbt_loaded_at

    FROM source
)

SELECT * FROM renamed

{% endif %}