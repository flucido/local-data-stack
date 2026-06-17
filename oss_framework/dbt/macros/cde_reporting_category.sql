{#
  Macro: cde_reporting_category_label
  Maps CDE reporting category codes to human-readable labels.
  Shared across all CDE staging models and the OBT mart.

  These codes are standard across CDE downloadable data files:
  - TA: Total (All Students)
  - R*: Race/ethnicity categories
  - G*: Gender categories
  - SE/EL/SWD/HOM/FOS/MIL: At-risk subgroups
  - GR*: Grade-level ranges

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
        WHEN 'RB' THEN 'Black/African American'
        WHEN 'RD' THEN 'Filipino (legacy)'
        WHEN 'RF' THEN 'Filipino'
        WHEN 'RH' THEN 'Hispanic/Latino'
        WHEN 'RI' THEN 'American Indian/Alaska Native'
        WHEN 'RP' THEN 'Native Hawaiian/Pacific Islander'
        WHEN 'RT' THEN 'Two or More Races'
        WHEN 'RW' THEN 'White'
        WHEN 'GM' THEN 'Male'
        WHEN 'GF' THEN 'Female'
        WHEN 'GX' THEN 'Non-binary'
        WHEN 'SE' THEN 'Socioeconomically Disadvantaged'
        WHEN 'SD' THEN 'Socioeconomically Disadvantaged (alt)'
        WHEN 'EL' THEN 'English Learners'
        WHEN 'RFEP' THEN 'Reclassified Fluent English Proficient'
        WHEN 'IFEP' THEN 'Initial Fluent English Proficient'
        WHEN 'SWD' THEN 'Students with Disabilities'
        WHEN 'HOM' THEN 'Homeless'
        WHEN 'FOS' THEN 'Foster Youth'
        WHEN 'MIL' THEN 'Military Connected'
        WHEN 'GRTKKN' THEN 'TK/Kindergarten'
        WHEN 'GR13' THEN 'Grades 1-3'
        WHEN 'GR46' THEN 'Grades 4-6'
        WHEN 'GR78' THEN 'Grades 7-8'
        WHEN 'GR912' THEN 'Grades 9-12'
        WHEN 'GRTK8' THEN 'TK-8'
        ELSE {{ column_name }}
    END
{% endmacro %}


{#
  Macro: cde_reporting_category_flags
  Produces boolean flag columns for subgroup classification.

  Args:
    column_name: The column containing the code (default: 'reporting_category')

  Returns three boolean expressions (race, gender, at-risk) as a comma-separated list.
  Use in SELECT to generate three columns:

  Example:
    SELECT
      {{ cde_reporting_category_flags('reporting_category') }}
    FROM source
  (produces: is_race_ethnicity_subgroup, is_gender_subgroup, is_atrisk_subgroup)
#}

{% macro cde_reporting_category_flags(column_name='reporting_category') %}
        CASE WHEN {{ column_name }} LIKE 'R%' THEN TRUE ELSE FALSE END as is_race_ethnicity_subgroup,
        CASE WHEN {{ column_name }} IN ('GF', 'GM', 'GX') THEN TRUE ELSE FALSE END as is_gender_subgroup,
        CASE WHEN {{ column_name }} IN ('SE', 'EL', 'RFEP', 'IFEP', 'SWD', 'HOM', 'FOS', 'MIL') THEN TRUE ELSE FALSE END as is_atrisk_subgroup,
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