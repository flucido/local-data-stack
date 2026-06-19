{#
  Export view: CDE Chronic Absenteeism Indicator (Dashboard)
  Source: cde_raw.cde_chronic_absenteeism_dashboard (Style B download file)
  Grain: cds_code × academic_year × student_group × aggregate_level
  Status = current-year chronic absenteeism rate (%)
  Change = YoY difference in percentage points
  Performance color 1-5 (Red→Blue); 0 = n-size not met / suppressed

  Reference: 2025 Dashboard Technical Guide — Chronic Absenteeism (dbguidechron25.docx)
  Notes:
    - TK-8 indicator only (high schools excluded by CDE)
    - "Reverse goal": lower rate = better; increased rate = declined performance
    - Automatic Orange assigned when data quality issues (certify/dataerror flags)
#}
{{ config(
    materialized='view',
    schema='analytics',
    tags=['rill_export', 'cde_dashboard']
) }}

SELECT
    cds                                                                              AS cds_code,
    schoolname                                                                       AS school_name,
    districtname                                                                     AS district_name,
    countyname                                                                       AS county_name,
    rtype                                                                            AS aggregate_level_code,
    {{ cde_aggregate_level_label('rtype') }}                                         AS aggregate_level,
    studentgroup                                                                     AS student_group_code,
    {{ cde_dashboard_student_group_label('studentgroup') }}                         AS student_group,
    {{ cde_dashboard_student_group_type('studentgroup') }}                          AS student_group_type,
    reportingyear                                                                    AS academic_year,

    -- Status (current year)
    TRY_CAST(currnumer AS INTEGER)                                                   AS curr_numerator,
    TRY_CAST(currdenom AS INTEGER)                                                   AS curr_denominator,
    TRY_CAST(currstatus AS DOUBLE)                                                   AS status_value,
    statuslevel                                                                      AS status_level_code,
    {{ cde_dashboard_status_level_name('statuslevel') }}                            AS status_level,

    -- Change (vs prior year)
    TRY_CAST(priornumer AS INTEGER)                                                  AS prior_numerator,
    TRY_CAST(priordenom AS INTEGER)                                                 AS prior_denominator,
    TRY_CAST(priorstatus AS DOUBLE)                                                 AS prior_status_value,
    TRY_CAST(change AS DOUBLE)                                                      AS change_value,
    change_level                                                                     AS change_level_code,
    {{ cde_dashboard_change_level_name('change_level') }}                           AS change_level,

    -- Performance placement
    color                                                                            AS color_code,
    {{ cde_dashboard_color_name('color') }}                                         AS performance_color,
    box                                                                              AS five_by_five_box,

    -- n-size / accountability flags
    currnsizemet = 'Y'                                                               AS curr_n_size_met,
    priornsizemet = 'Y'                                                              AS prior_n_size_met,
    accountabilitymet = 'Y'                                                          AS accountability_met,
    COALESCE(smalldenom = 'Y', FALSE)                                               AS small_denominator,
    COALESCE(dataerrorflag = 'Y', FALSE)                                             AS data_error_flag,

    -- School type flags
    COALESCE(charter_flag = 'Y', FALSE)                                              AS is_charter,
    COALESCE(dass_flag = 'Y', FALSE)                                                 AS is_dass,
    COALESCE(coe_flag = 'Y', FALSE)                                                 AS is_county_office,

    -- Indicator metadata
    'chronic_absenteeism'                                                           AS indicator,
    indicator                                                                       AS indicator_code,

    _loaded_at                                                                      AS loaded_at
FROM {{ source('cde_raw', 'cde_chronic_absenteeism_dashboard') }}
WHERE rtype IN ('S', 'D')