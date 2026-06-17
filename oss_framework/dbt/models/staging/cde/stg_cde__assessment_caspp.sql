{{ config(
    materialized='view',
    schema='staging'
) }}

{#
  Staging model for CDE CAASPP (SBAC) Assessment data.
  Source style: ZIP / caret-delimited files with spaced column names.
  Original columns: County Code, District Code, School Code, Test Year, Student Group ID, etc.
  Source has a GRADE dimension not present in other assessment models.

  Grain: source is school × year × student_group_id × grade × test_type.
  This model summarizes to school × year × student_group_id × test_type grain
  (aggregate across grades) using:
    - AVG for mean_scale_score and percentage_* columns
    - SUM for student counts (students_enrolled, students_tested, students_with_scores)

  Build cds_code from county/district/school codes via macro.
  Map student_group_id → reporting_category.
  Source: cde_raw.cde_assessment_caspp
#}

{% set cde_table = adapter.get_relation(database=target.database, schema='cde_raw', identifier='cde_assessment_caspp') %}

{% if cde_table is none %}

SELECT
    CAST(NULL AS VARCHAR) as cds_code,
    CAST(NULL AS VARCHAR) as county_code,
    CAST(NULL AS VARCHAR) as district_code,
    CAST(NULL AS VARCHAR) as school_code,
    CAST(NULL AS VARCHAR) as reporting_category,
    CAST(NULL AS VARCHAR) as reporting_category_label,
    CAST(NULL AS VARCHAR) as academic_year,
    CAST(NULL AS VARCHAR) as test_type,
    CAST(NULL AS INTEGER) as total_tested_at_reporting_level,
    CAST(NULL AS INTEGER) as total_tested_with_scores_at_reporting_level,
    CAST(NULL AS INTEGER) as students_enrolled,
    CAST(NULL AS INTEGER) as students_tested,
    CAST(NULL AS INTEGER) as students_with_scores,
    CAST(NULL AS DOUBLE) as mean_scale_score,
    CAST(NULL AS DOUBLE) as pct_standard_exceeded,
    CAST(NULL AS DOUBLE) as pct_standard_met,
    CAST(NULL AS DOUBLE) as pct_standard_met_and_above,
    CAST(NULL AS DOUBLE) as pct_standard_nearly_met,
    CAST(NULL AS DOUBLE) as pct_standard_not_met,
    CAST(NULL AS DOUBLE) as area_1_pct_above_standard,
    CAST(NULL AS DOUBLE) as area_1_pct_near_standard,
    CAST(NULL AS DOUBLE) as area_1_pct_below_standard,
    CAST(NULL AS DOUBLE) as area_2_pct_above_standard,
    CAST(NULL AS DOUBLE) as area_2_pct_near_standard,
    CAST(NULL AS DOUBLE) as area_2_pct_below_standard,
    CAST(NULL AS DOUBLE) as area_3_pct_above_standard,
    CAST(NULL AS DOUBLE) as area_3_pct_near_standard,
    CAST(NULL AS DOUBLE) as area_3_pct_below_standard,
    CAST(NULL AS DOUBLE) as area_4_pct_above_standard,
    CAST(NULL AS DOUBLE) as area_4_pct_near_standard,
    CAST(NULL AS DOUBLE) as area_4_pct_below_standard,
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
    SELECT * FROM {{ source('cde_raw', 'cde_assessment_caspp') }}
),

renamed AS (
    SELECT
        -- Build the 14-char CDS code from county/district/school parts
        {{ cde_build_cds_code('county_code', 'district_code', 'school_code') }} as cds_code,
        county_code,
        district_code,
        school_code,

        -- Demographic / subgroup
        student_group_id as reporting_category,
        {{ cde_reporting_category_label('student_group_id') }} as reporting_category_label,

        -- Time & test identifiers
        test_year,
        test_type,

        -- Grade (kept from source — the source has a grade dimension;
        -- we carry it through to the summarization step where it is aggregated out)
        grade,

        -- Student counts (will be SUMmed across grades)
        TRY_CAST(total_tested_at_reporting_level AS INTEGER) as total_tested_at_reporting_level,
        TRY_CAST(total_tested_with_scores_at_reporting_level AS INTEGER) as total_tested_with_scores_at_reporting_level,
        TRY_CAST(students_enrolled AS INTEGER) as students_enrolled,
        TRY_CAST(students_tested AS INTEGER) as students_tested,
        TRY_CAST(students_with_scores AS INTEGER) as students_with_scores,

        -- Score & percentage metrics (will be AVG'd across grades)
        TRY_CAST(mean_scale_score AS DOUBLE) as mean_scale_score,
        TRY_CAST(percentage_standard_exceeded AS DOUBLE) as pct_standard_exceeded,
        TRY_CAST(percentage_standard_met AS DOUBLE) as pct_standard_met,
        TRY_CAST(percentage_standard_met_and_above AS DOUBLE) as pct_standard_met_and_above,
        TRY_CAST(percentage_standard_nearly_met AS DOUBLE) as pct_standard_nearly_met,
        TRY_CAST(percentage_standard_not_met AS DOUBLE) as pct_standard_not_met,

        -- Area-level percentages (AVG across grades)
        TRY_CAST(area_1_percentage_above_standard AS DOUBLE) as area_1_pct_above_standard,
        TRY_CAST(area_1_percentage_near_standard AS DOUBLE) as area_1_pct_near_standard,
        TRY_CAST(area_1_percentage_below_standard AS DOUBLE) as area_1_pct_below_standard,
        TRY_CAST(area_2_percentage_above_standard AS DOUBLE) as area_2_pct_above_standard,
        TRY_CAST(area_2_percentage_near_standard AS DOUBLE) as area_2_pct_near_standard,
        TRY_CAST(area_2_percentage_below_standard AS DOUBLE) as area_2_pct_below_standard,
        TRY_CAST(area_3_percentage_above_standard AS DOUBLE) as area_3_pct_above_standard,
        TRY_CAST(area_3_percentage_near_standard AS DOUBLE) as area_3_pct_near_standard,
        TRY_CAST(area_3_percentage_below_standard AS DOUBLE) as area_3_pct_below_standard,
        TRY_CAST(area_4_percentage_above_standard AS DOUBLE) as area_4_pct_above_standard,
        TRY_CAST(area_4_percentage_near_standard AS DOUBLE) as area_4_pct_near_standard,
        TRY_CAST(area_4_percentage_below_standard AS DOUBLE) as area_4_pct_below_standard,

        -- Metadata
        _loaded_at as dlt_loaded_at,
        _source_file as source_filename

    FROM source
),

-- Summarize to school × year × student_group_id × test_type grain
-- (aggregate across grades)
summarized AS (
    SELECT
        cds_code,
        county_code,
        district_code,
        school_code,
        reporting_category,
        reporting_category_label,
        test_year,
        test_type,

        -- Student counts: SUM across grades
        SUM(total_tested_at_reporting_level) as total_tested_at_reporting_level,
        SUM(total_tested_with_scores_at_reporting_level) as total_tested_with_scores_at_reporting_level,
        SUM(students_enrolled) as students_enrolled,
        SUM(students_tested) as students_tested,
        SUM(students_with_scores) as students_with_scores,

        -- Score & percentage metrics: AVG across grades
        AVG(mean_scale_score) as mean_scale_score,
        AVG(pct_standard_exceeded) as pct_standard_exceeded,
        AVG(pct_standard_met) as pct_standard_met,
        AVG(pct_standard_met_and_above) as pct_standard_met_and_above,
        AVG(pct_standard_nearly_met) as pct_standard_nearly_met,
        AVG(pct_standard_not_met) as pct_standard_not_met,

        -- Area-level percentages: AVG across grades
        AVG(area_1_pct_above_standard) as area_1_pct_above_standard,
        AVG(area_1_pct_near_standard) as area_1_pct_near_standard,
        AVG(area_1_pct_below_standard) as area_1_pct_below_standard,
        AVG(area_2_pct_above_standard) as area_2_pct_above_standard,
        AVG(area_2_pct_near_standard) as area_2_pct_near_standard,
        AVG(area_2_pct_below_standard) as area_2_pct_below_standard,
        AVG(area_3_pct_above_standard) as area_3_pct_above_standard,
        AVG(area_3_pct_near_standard) as area_3_pct_near_standard,
        AVG(area_3_pct_below_standard) as area_3_pct_below_standard,
        AVG(area_4_pct_above_standard) as area_4_pct_above_standard,
        AVG(area_4_pct_near_standard) as area_4_pct_near_standard,
        AVG(area_4_pct_below_standard) as area_4_pct_below_standard,

        -- Metadata (take from any row in the group)
        MIN(dlt_loaded_at) as dlt_loaded_at,
        MIN(source_filename) as source_filename

    FROM renamed
    GROUP BY
        cds_code,
        county_code,
        district_code,
        school_code,
        reporting_category,
        reporting_category_label,
        test_year,
        test_type
),

final AS (
    SELECT
        *,
        test_year as academic_year,
        CURRENT_TIMESTAMP as dbt_loaded_at,
        {{ cde_reporting_category_flags('reporting_category') }}
    FROM summarized
)

SELECT * FROM final

{% endif %}
