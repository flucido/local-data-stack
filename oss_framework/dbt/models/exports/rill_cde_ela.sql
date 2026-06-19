{#
  Export view: CDE Academic Indicator — English Language Arts (Dashboard)
  Source: cde_raw.cde_ela_dashboard (Style B download file)
  Grain: cds_code × academic_year × student_group × aggregate_level
  Status = current-year average Distance from Standard (DFS)
    Negative = below standard; positive = above standard
  Change = YoY difference in DFS points
  Performance color 1-5 (Red→Blue); 0 = n-size not met / suppressed

  Reference: 2025 Dashboard Technical Guide — Academic (dbguideacad25.docx)
  Notes:
    - Cut scores differ for grades 3-8 (elem/mid/TK-12/ elem district) vs grade 11 (high school/high district)
    - Participation rate penalty: when 95% target unmet, LOSS scores added (num_prloss)
    - ELA-specific student groups: CAA, EO, ELO, RFP, SBA (informational only, no colors)
    - Note column: changelevel (no underscore) in this table
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

    -- Status (current year) — Distance from Standard
    TRY_CAST(currdenom AS INTEGER)                                                   AS curr_denominator,
    TRY_CAST(currstatus AS DOUBLE)                                                   AS status_value,
    statuslevel                                                                      AS status_level_code,
    {{ cde_dashboard_status_level_name('statuslevel') }}                            AS status_level,
    TRY_CAST(currdenom_without_prloss AS INTEGER)                                    AS curr_denominator_without_prloss,
    TRY_CAST(currstatus_without_prloss AS DOUBLE)                                    AS status_value_without_prloss,
    TRY_CAST(num_prloss AS INTEGER)                                                  AS num_prloss,

    -- Change (vs prior year)
    TRY_CAST(priordenom AS INTEGER)                                                  AS prior_denominator,
    TRY_CAST(priorstatus AS DOUBLE)                                                 AS prior_status_value,
    TRY_CAST(change AS DOUBLE)                                                      AS change_value,
    changelevel                                                                      AS change_level_code,
    {{ cde_dashboard_change_level_name('changelevel') }}                            AS change_level,

    -- Performance placement
    color                                                                            AS color_code,
    {{ cde_dashboard_color_name('color') }}                                         AS performance_color,
    box                                                                              AS five_by_five_box,

    -- Participation rate (current + prior)
    TRY_CAST(currprate_enrolled AS INTEGER)                                          AS curr_prate_enrolled,
    TRY_CAST(currprate_tested AS INTEGER)                                            AS curr_prate_tested,
    TRY_CAST(currprate AS DOUBLE)                                                    AS curr_participation_rate,
    TRY_CAST(priorprate_enrolled AS INTEGER)                                         AS prior_prate_enrolled,
    TRY_CAST(priorprate_tested AS INTEGER)                                           AS prior_prate_tested,
    TRY_CAST(priorprate AS DOUBLE)                                                   AS prior_participation_rate,

    -- n-size / accountability flags
    currnsizemet = 'Y'                                                               AS curr_n_size_met,
    priornsizemet = 'Y'                                                              AS prior_n_size_met,
    accountabilitymet = 'Y'                                                           AS accountability_met,

    -- School type flags
    COALESCE(charter_flag = 'Y', FALSE)                                               AS is_charter,
    COALESCE(dass_flag = 'Y', FALSE)                                                 AS is_dass,
    COALESCE(coe_flag = 'Y', FALSE)                                                  AS is_county_office,
    hscutpoints                                                                      AS hs_cutpoints,
    pairshare_method                                                                 AS pairshare_method,

    -- Indicator metadata
    'ela'                                                                            AS indicator,
    indicator                                                                        AS indicator_code,

    _loaded_at                                                                        AS loaded_at
FROM {{ source('cde_raw', 'cde_ela_dashboard') }}
WHERE rtype IN ('S', 'D')
