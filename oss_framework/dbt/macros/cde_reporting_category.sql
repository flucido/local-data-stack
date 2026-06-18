{#
  Macro: cde_reporting_category_label
  Maps CDE reporting category codes to human-readable labels.
  Shared across all CDE staging models and the OBT mart.

  Authoritative source: CDE File Structure for Chronic Absenteeism Data
  (https://www.cde.ca.gov/ds/ad/fsabd.asp) and 2024 Dashboard record layout
  (https://www.cde.ca.gov/ta/ac/cm/chronic24.asp).

  Style A codes (used in chronic absenteeism, suspension, expulsion,
  homeless enrollment, absenteeism reason, cumulative enrollment files):

  Race/ethnicity:
    RB = African American
    RI = American Indian or Alaska Native
    RA = Asian
    RF = Filipino
    RH = Hispanic or Latino
    RD = Did not Report
    RP = Pacific Islander
    RT = Two or More Races
    RW = White

  Gender:
    GM = Male
    GF = Female
    GX = Non-Binary Gender (Beginning 2019–20)
    GZ = Missing Gender

  Program subgroups (at-risk):
    SE = English Learners
    SD = Students with Disabilities
    SS = Socioeconomically Disadvantaged
    SM = Migrant
    SF = Foster
    SH = Homeless

  Grade spans:
    GRKN = Kindergarten (GRK prior to 2020–21)
    GR13 = Grades 1–3
    GR46 = Grades 4–6
    GR78 = Grades 7–8
    GRK8 = Grades K–8
    GR912 = Grades 9–12
    GRTK8 = TK-8 (Dashboard accountability variant)
    GRTKKN = TK/Kindergarten (Dashboard accountability variant)

  Total:
    TA = Total (All Students)

  Note: Style B Dashboard files (chronicdownload, suspdownload, eladownload)
  use a DIFFERENT code set (ALL, AA, AI, AS, FI, HI, PI, WH, MR, EL, SED,
  SWD, FOS, HOM, LTEL). Those are NOT handled by this macro — Style B
  files have their own staging models (stg_cde__*_dashboard).

  Args:
    column_name: The column containing the code (default: 'reporting_category')

  Returns:
    CASE expression producing the label

  Example:
    SELECT {{ cde_reporting_category_label('reporting_category') }} as reporting_category_label
#}

{% macro cde_reporting_category_label(column_name='reporting_category') %}
    CASE {{ column_name }}
        WHEN 'TA' THEN 'Total (All Students)'
        WHEN 'RA' THEN 'Asian'
        WHEN 'RB' THEN 'African American'
        WHEN 'RD' THEN 'Did not Report'
        WHEN 'RF' THEN 'Filipino'
        WHEN 'RH' THEN 'Hispanic or Latino'
        WHEN 'RI' THEN 'American Indian or Alaska Native'
        WHEN 'RP' THEN 'Pacific Islander'
        WHEN 'RT' THEN 'Two or More Races'
        WHEN 'RW' THEN 'White'
        WHEN 'GM' THEN 'Male'
        WHEN 'GF' THEN 'Female'
        WHEN 'GX' THEN 'Non-Binary Gender'
        WHEN 'GZ' THEN 'Missing Gender'
        WHEN 'SE' THEN 'English Learners'
        WHEN 'SD' THEN 'Students with Disabilities'
        WHEN 'SS' THEN 'Socioeconomically Disadvantaged'
        WHEN 'SM' THEN 'Migrant'
        WHEN 'SF' THEN 'Foster'
        WHEN 'SH' THEN 'Homeless'
        WHEN 'GRKN' THEN 'Kindergarten'
        WHEN 'GR13' THEN 'Grades 1-3'
        WHEN 'GR46' THEN 'Grades 4-6'
        WHEN 'GR78' THEN 'Grades 7-8'
        WHEN 'GRK8' THEN 'Grades K-8'
        WHEN 'GR912' THEN 'Grades 9-12'
        WHEN 'GRTK8' THEN 'TK-8'
        WHEN 'GRTKKN' THEN 'TK/Kindergarten'
        ELSE {{ column_name }}
    END
{% endmacro %}


{#
  Macro: cde_reporting_category_flags
  Produces boolean flag columns for subgroup classification.

  Classification is based on CDE Style A codes (the codes that appear in the
  reporting_category column of chronic absenteeism, suspension, expulsion,
  homeless enrollment, and absenteeism reason files). Style B Dashboard
  codes (ALL, AA, SED, SWD, etc.) are NOT classified here — they live in
  separate staging models.

  Args:
    column_name: The column containing the code (default: 'reporting_category')

  Returns four boolean expressions as a comma-separated list:
    is_race_ethnicity_subgroup  — R* codes (RA, RB, RD, RF, RH, RI, RP, RT, RW)
    is_gender_subgroup          — G* codes (GM, GF, GX, GZ)
    is_atrisk_subgroup           — program subgroups (SE, SD, SS, SM, SF, SH)
    is_grade_level_subgroup      — GR* codes (GRKN, GR13, GR46, GR78, GRK8, GR912, GRTK8, GRTKKN)

  Example:
    SELECT
      {{ cde_reporting_category_flags('reporting_category') }}
    FROM source
#}

{% macro cde_reporting_category_flags(column_name='reporting_category') %}
        CASE WHEN {{ column_name }} LIKE 'R%' THEN TRUE ELSE FALSE END as is_race_ethnicity_subgroup,
        CASE WHEN {{ column_name }} IN ('GM', 'GF', 'GX', 'GZ') THEN TRUE ELSE FALSE END as is_gender_subgroup,
        CASE WHEN {{ column_name }} IN ('SE', 'SD', 'SS', 'SM', 'SF', 'SH') THEN TRUE ELSE FALSE END as is_atrisk_subgroup,
        CASE WHEN {{ column_name }} LIKE 'GR%' THEN TRUE ELSE FALSE END as is_grade_level_subgroup
{% endmacro %}


{#
  Macro: cde_aggregate_level_label
  Maps aggregate level codes to human-readable labels.

  Args:
    column_name: The column containing the code (default: 'aggregate_level')
#}

{% macro cde_aggregate_level_label(column_name='aggregate_level') %}
    CASE {{ column_name }}
        WHEN 'T' THEN 'State'
        WHEN 'C' THEN 'County'
        WHEN 'D' THEN 'District'
        WHEN 'S' THEN 'School'
        ELSE {{ column_name }}
    END
{% endmacro %}


{#
  Macro: cde_build_cds_code
  Constructs the 14-character CDS code from county/district/school code parts.
  Used by Style A and Style C files where codes are in separate columns.

  Args:
    county_col: column name for county code (2 digits)
    district_col: column name for district code (5 digits)
    school_col: column name for school code (7 digits)
#}

{% macro cde_build_cds_code(county_col='county_code', district_col='district_code', school_col='school_code') %}
    CONCAT(
        LPAD(COALESCE({{ county_col }}, ''), 2, '0'),
        LPAD(COALESCE({{ district_col }}, ''), 5, '0'),
        LPAD(COALESCE({{ school_col }}, ''), 7, '0')
    )
{% endmacro %}


{#
  Macro: cde_suppression_flags
  Generates data quality flags for suppressed and small-n values.
  CDE suppresses cells with fewer than 11 students (shown as '*').

  Args:
    cols: list of column names to check for suppression ('*' marker)
#}

{% macro cde_suppression_flags(cols) %}
    CASE
        {% for col in cols %}
        WHEN {{ col }} = '*' THEN TRUE
        {% endfor %}
        ELSE FALSE
    END as is_suppressed,

    CASE
        {% for col in cols %}
        WHEN TRY_CAST({{ col }} AS INTEGER) < 11 THEN TRUE
        {% endfor %}
        ELSE FALSE
    END as is_small_n
{% endmacro %}
