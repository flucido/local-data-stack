{#
  Export view: CDE English Learner Progress Indicator (ELPI)
  Source: cde_raw.cde_elpac_dashboard (Style B download file)
  Grain: cds_code × academic_year × student_group × aggregate_level
  Status = current-year ELPI status rate (% of ELs making progress)
  Change = YoY difference in percentage points
  Performance color 1-5 (Red→Blue); 0 = n-size not met / suppressed

  Reference: 2025 Dashboard Technical Guide — ELPI (dbguideelp25.docx)
  Notes:
    - Grade 1-12 indicator; only EL and LTEL student groups reported
    - Status rate = (progressed + maintained PL4 + alternate-ELPI qualifiers) / (test takers + 95% participation adjustment)
    - Reverse-goal does NOT apply — higher rate = better
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

    -- Status (current year) — ELPI status rate (%)
    TRY_CAST(currnumer AS INTEGER)                                                   AS curr_numerator,
    TRY_CAST(currdenom AS INTEGER)                                                   AS curr_denominator,
    TRY_CAST(currstatus AS DOUBLE)                                                  AS status_value,
    statuslevel                                                                      AS status_level_code,
    {{ cde_dashboard_status_level_name('statuslevel') }}                            AS status_level,

    -- ELPI progress components (current year)
    TRY_CAST(currprogressed AS INTEGER)                                              AS curr_progressed,
    TRY_CAST(currmaintain_pl4 AS INTEGER)                                           AS curr_maintain_pl4,
    TRY_CAST(currmaintain_oth AS INTEGER)                                            AS curr_maintain_other,
    TRY_CAST(currdeclined AS INTEGER)                                                AS curr_declined,
    TRY_CAST(curr95 AS INTEGER)                                                      AS curr_95pct_adjustment,

    -- Alternate ELPAC components (current year)
    TRY_CAST(currprogressed_alternate AS INTEGER)                                    AS curr_progressed_alternate,
    TRY_CAST(currmaintain_pl3_alternate AS INTEGER)                                   AS curr_maintain_pl3_alternate,
    TRY_CAST(currnotprognotmain_alternate AS INTEGER)                                 AS curr_notprog_notmain_alternate,

    -- Change (vs prior year)
    TRY_CAST(priornumer AS INTEGER)                                                  AS prior_numerator,
    TRY_CAST(priordenom AS INTEGER)                                                 AS prior_denominator,
    TRY_CAST(priorstatus AS DOUBLE)                                                 AS prior_status_value,
    TRY_CAST(change AS DOUBLE)                                                      AS change_value,
    changelevel                                                                      AS change_level_code,
    {{ cde_dashboard_change_level_name('changelevel') }}                            AS change_level,

    -- ELPI progress components (prior year)
    TRY_CAST(priorprogressed AS INTEGER)                                             AS prior_progressed,
    TRY_CAST(priormaintain_pl4 AS INTEGER)                                          AS prior_maintain_pl4,
    TRY_CAST(priormaintain_oth AS INTEGER)                                          AS prior_maintain_other,
    TRY_CAST(priordeclined AS INTEGER)                                               AS prior_declined,
    TRY_CAST(prior95 AS INTEGER)                                                     AS prior_95pct_adjustment,
    TRY_CAST(priorprogressed_alternate AS INTEGER)                                  AS prior_progressed_alternate,
    TRY_CAST(priormaintain_pl3_alternate AS INTEGER)                                 AS prior_maintain_pl3_alternate,
    TRY_CAST(priornotprognotmain_alternate AS INTEGER)                               AS prior_notprog_notmain_alternate,

    -- Performance placement
    color                                                                            AS color_code,
    {{ cde_dashboard_color_name('color') }}                                         AS performance_color,
    box                                                                              AS five_by_five_box,

    -- n-size / accountability flags
    currnsizemet = 'Y'                                                               AS curr_n_size_met,
    priornsizemet = 'Y'                                                              AS prior_n_size_met,
    accountabilitymet = 'Y'                                                           AS accountability_met,
    COALESCE(flag95pct = 'Y', FALSE)                                                 AS participation_rate_penalty,

    -- School type flags
    COALESCE(charter_flag = 'Y', FALSE)                                              AS is_charter,
    COALESCE(dass_flag = 'Y', FALSE)                                                AS is_dass,
    COALESCE(coe_flag = 'Y', FALSE)                                                 AS is_county_office,

    -- Indicator metadata
    'elpac'                                                                          AS indicator,
    indicator                                                                        AS indicator_code,

    _loaded_at                                                                       AS loaded_at
FROM {{ source('cde_raw', 'cde_elpac_dashboard') }}
WHERE rtype IN ('S', 'D')
