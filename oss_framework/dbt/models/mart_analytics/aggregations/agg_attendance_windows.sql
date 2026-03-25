{{ config(
    materialized='table',
    schema='analytics',
    unique_id='agg_attendance_windows'
) }}

-- NOTE: fact_attendance provides annual-grain summaries (one row per student
-- per academic year) with aggregate counts (days_enrolled, days_present, etc.).
-- The Aeries SIS API returns annual attendance summaries, not daily records.
-- All window types below use the annual data as the best available proxy.
-- When daily attendance data becomes available, this model should be updated
-- to compute true rolling windows.

WITH attendance_base AS (
    SELECT
        fa.student_id_hash AS student_key,
        fa.academic_year,
        fa.school_id,
        COALESCE(fa.days_enrolled, 0) AS days_enrolled,
        COALESCE(fa.days_present, 0) AS days_present,
        COALESCE(fa.days_absent, 0) AS days_absent,
        COALESCE(fa.days_excused, 0) AS days_excused,
        COALESCE(fa.days_unexcused, 0) AS days_unexcused,
        COALESCE(fa.days_tardy, 0) AS days_tardy,
        -- attendance_rate from staging is a 0-1 ratio; convert to 0-100 percentage
        ROUND(COALESCE(fa.attendance_rate, 0) * 100.0, 2) AS attendance_rate_pct
    FROM {{ ref('fact_attendance') }} fa
    WHERE fa.days_enrolled > 0
),

discipline_counts AS (
    SELECT
        fd.student_id_hash AS student_key,
        COUNT(*) AS total_incidents
    FROM {{ ref('fact_discipline') }} fd
    GROUP BY fd.student_id_hash
),

-- All window types use the annual data as proxy since daily data is not available.
-- The annual totals are the most accurate representation we have.
annual_window AS (
    SELECT
        ab.student_key,
        ab.days_enrolled AS total_school_days,
        ab.days_present AS present_days,
        ab.days_absent AS absent_days,
        ab.days_excused AS excused_absences,
        ab.days_unexcused AS unexcused_absences,
        ab.days_tardy AS tardy_incidents,
        ab.attendance_rate_pct AS attendance_rate,
        ROUND(
            100.0 * ab.days_unexcused / NULLIF(ab.days_enrolled, 0),
            2
        ) AS unexcused_absence_rate,
        ROUND(
            100.0 * ab.days_tardy / NULLIF(ab.days_enrolled, 0),
            2
        ) AS tardy_rate,
        COALESCE(dc.total_incidents, 0) AS discipline_incidents_in_window,
        0 AS absence_discipline_correlation_score,
        'stable' AS pattern_direction
    FROM attendance_base ab
    LEFT JOIN discipline_counts dc ON ab.student_key = dc.student_key
)

SELECT
    student_key,
    CURRENT_DATE - 30 AS window_start_date,
    wt.window_type,
    aw.total_school_days,
    aw.present_days,
    aw.absent_days,
    aw.excused_absences,
    aw.unexcused_absences,
    aw.tardy_incidents,
    aw.attendance_rate,
    ROUND(100.0 - aw.attendance_rate, 2) AS absence_rate,
    aw.unexcused_absence_rate,
    aw.tardy_rate,
    CASE WHEN (100.0 - aw.attendance_rate) >= 10.0 THEN 1 ELSE 0 END AS chronic_absence_flag,
    aw.discipline_incidents_in_window,
    aw.absence_discipline_correlation_score,
    COALESCE(aw.pattern_direction, 'stable') AS pattern_direction,
    CURRENT_TIMESTAMP AS _loaded_at
FROM annual_window aw
CROSS JOIN (
    SELECT '30d' AS window_type
    UNION ALL SELECT '60d'
    UNION ALL SELECT '90d'
    UNION ALL SELECT 'term'
) wt
ORDER BY student_key, window_type
