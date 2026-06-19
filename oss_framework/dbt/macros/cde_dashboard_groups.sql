{#
  Macro: cde_dashboard_student_group_label
  Maps CDE Dashboard Style B student-group codes to human-readable labels.

  Used by the cde_*_dashboard raw tables (chronicdownload, suspdownload,
  eladownload, elpidownload) which use a different code set than the
  Style A reporting_category files (TA, RA, RB, ...).

  Style B codes (per CDE Dashboard downloadable data files):
    Race/ethnicity:
      AA = African American / Black
      AI = American Indian or Alaska Native
      AS = Asian
      FI = Filipino
      HI = Hispanic or Latino
      MR = Two or More Races
      PI = Pacific Islander
      WH = White
    Program subgroups:
      ALL = All Students
      EL  = English Learners
      LTEL = Long-Term English Learners
      SED = Socioeconomically Disadvantaged
      SWD = Students with Disabilities
      HOM = Homeless
      FOS = Foster Youth
    ELA-only additional groups (informational):
      CAA = California Alternate Assessments
      EO  = English Only
      ELO = English Learner (current, ELA-specific)
      RFP = Reclassified Fluent-English Proficient
      SBA = Smarter Balanced Assessments

  Args:
    column_name: column containing the Style B code (default: 'studentgroup')

  Returns:
    CASE expression producing the human-readable label
#}

{% macro cde_dashboard_student_group_label(column_name='studentgroup') %}
    CASE {{ column_name }}
        WHEN 'ALL'  THEN 'All Students'
        WHEN 'AA'   THEN 'African American / Black'
        WHEN 'AI'   THEN 'American Indian or Alaska Native'
        WHEN 'AS'   THEN 'Asian'
        WHEN 'FI'   THEN 'Filipino'
        WHEN 'HI'   THEN 'Hispanic or Latino'
        WHEN 'MR'   THEN 'Two or More Races'
        WHEN 'PI'   THEN 'Pacific Islander'
        WHEN 'WH'   THEN 'White'
        WHEN 'EL'   THEN 'English Learners'
        WHEN 'LTEL' THEN 'Long-Term English Learners'
        WHEN 'SED'  THEN 'Socioeconomically Disadvantaged'
        WHEN 'SWD'  THEN 'Students with Disabilities'
        WHEN 'HOM'  THEN 'Homeless'
        WHEN 'FOS'  THEN 'Foster Youth'
        WHEN 'CAA'  THEN 'California Alternate Assessments'
        WHEN 'EO'   THEN 'English Only'
        WHEN 'ELO'  THEN 'English Learner (Current)'
        WHEN 'RFP'  THEN 'Reclassified Fluent-English Proficient'
        WHEN 'SBA'  THEN 'Smarter Balanced Assessments'
        ELSE {{ column_name }}
    END
{% endmacro %}


{#
  Macro: cde_dashboard_student_group_type
  Classifies a Style B student-group code into one of:
    'all', 'race_ethnicity', 'program', 'ela_additional'

  Args:
    column_name: column containing the Style B code (default: 'studentgroup')
#}

{% macro cde_dashboard_student_group_type(column_name='studentgroup') %}
    CASE {{ column_name }}
        WHEN 'ALL'  THEN 'all'
        WHEN 'AA'   THEN 'race_ethnicity'
        WHEN 'AI'   THEN 'race_ethnicity'
        WHEN 'AS'   THEN 'race_ethnicity'
        WHEN 'FI'   THEN 'race_ethnicity'
        WHEN 'HI'   THEN 'race_ethnicity'
        WHEN 'MR'   THEN 'race_ethnicity'
        WHEN 'PI'   THEN 'race_ethnicity'
        WHEN 'WH'   THEN 'race_ethnicity'
        WHEN 'EL'   THEN 'program'
        WHEN 'LTEL' THEN 'program'
        WHEN 'SED'  THEN 'program'
        WHEN 'SWD'  THEN 'program'
        WHEN 'HOM'  THEN 'program'
        WHEN 'FOS'  THEN 'program'
        WHEN 'CAA'  THEN 'ela_additional'
        WHEN 'EO'   THEN 'ela_additional'
        WHEN 'ELO'  THEN 'ela_additional'
        WHEN 'RFP'  THEN 'ela_additional'
        WHEN 'SBA'  THEN 'ela_additional'
        ELSE 'unknown'
    END
{% endmacro %}


{#
  Macro: cde_dashboard_color_name
  Maps the numeric CDE Dashboard color code (1-5) to the Performance Level name.
    1 = Red, 2 = Orange, 3 = Yellow, 4 = Green, 5 = Blue
    0 and NULL = No Performance Color (n-size not met, suppressed, or no data)

  Args:
    column_name: column containing the color code (default: 'color')
#}

{% macro cde_dashboard_color_name(column_name='color') %}
    CASE {{ column_name }}
        WHEN '1' THEN 'Red'
        WHEN '2' THEN 'Orange'
        WHEN '3' THEN 'Yellow'
        WHEN '4' THEN 'Green'
        WHEN '5' THEN 'Blue'
        ELSE 'No Performance Color'
    END
{% endmacro %}


{#
  Macro: cde_dashboard_status_level_name
  Maps the numeric CDE Dashboard Status level (1-5) to its name.
    1 = Very Low, 2 = Low, 3 = Medium, 4 = High, 5 = Very High
    0 = No Data

  Args:
    column_name: column containing the status level code (default: 'statuslevel')
#}

{% macro cde_dashboard_status_level_name(column_name='statuslevel') %}
    CASE {{ column_name }}
        WHEN '1' THEN 'Very Low'
        WHEN '2' THEN 'Low'
        WHEN '3' THEN 'Medium'
        WHEN '4' THEN 'High'
        WHEN '5' THEN 'Very High'
        ELSE 'No Data'
    END
{% endmacro %}


{#
  Macro: cde_dashboard_change_level_name
  Maps the numeric CDE Dashboard Change level (1-5) to its name.
    1 = Declined Significantly, 2 = Declined, 3 = Maintained,
    4 = Increased, 5 = Increased Significantly
    0 = No Data

  Note: column name differs across the CDE dashboard files — chronic
  absenteeism uses `change_level` (underscored) while suspension, ELA,
  and ELPAC use `changelevel` (no underscore). Caller must pass the
  correct column.

  Args:
    column_name: column containing the change level code
#}

{% macro cde_dashboard_change_level_name(column_name) %}
    CASE {{ column_name }}
        WHEN '1' THEN 'Declined Significantly'
        WHEN '2' THEN 'Declined'
        WHEN '3' THEN 'Maintained'
        WHEN '4' THEN 'Increased'
        WHEN '5' THEN 'Increased Significantly'
        ELSE 'No Data'
    END
{% endmacro %}