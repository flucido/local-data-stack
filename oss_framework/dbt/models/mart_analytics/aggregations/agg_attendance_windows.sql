{{ config(
    materialized='table',
    schema='analytics',
    unique_id='agg_attendance_windows'
) }}

-- Computes rolling attendance windows (30d, 60d, 90d, term) from DAILY
-- attendance data. Previously this used annual summaries as a proxy for all
-- windows, which meant attendance_rate_30d == attendance_rate_90d for every
-- student.  Now we query raw daily attendance so each window reflects actual
-- attendance over that time span.
--
-- Windows are anchored on the last school day of EACH academic year (not a
-- single global MAX(date)), so historical years get non-empty 30d/90d/term
-- windows instead of silently reporting 0% attendance / 100% no discipline.

WITH window_defs AS (
              SELECT '30d'   AS window_type,  30 AS window_days
    UNION ALL SELECT '60d',   60
    UNION ALL SELECT '90d',   90
    UNION ALL SELECT 'term', 365   -- effectively "all data" since school year < 365d
),

daily AS (
    SELECT
        {{ hash_pii_secure('ra.student_id') }} AS student_key,
        CASE
            WHEN TRY_CAST(ra.attendance_date AS DATE) IS NOT NULL THEN
                CASE
                    WHEN MONTH(TRY_CAST(ra.attendance_date AS DATE)) >= 7
                        THEN CAST(YEAR(TRY_CAST(ra.attendance_date AS DATE)) AS VARCHAR) || '-' || CAST(YEAR(TRY_CAST(ra.attendance_date AS DATE)) + 1 AS VARCHAR)
                    ELSE CAST(YEAR(TRY_CAST(ra.attendance_date AS DATE)) - 1 AS VARCHAR) || '-' || CAST(YEAR(TRY_CAST(ra.attendance_date AS DATE)) AS VARCHAR)
                END
            ELSE '2024-2025'
        END AS academic_year,
        CAST(ra.attendance_date AS DATE) AS attendance_date,
        CAST(ra.present_flag   AS BOOLEAN) AS present_flag,
        CAST(ra.absent_flag    AS BOOLEAN) AS absent_flag,
        CAST(ra.excused_flag   AS BOOLEAN) AS excused_flag,
        CAST(ra.unexcused_flag AS BOOLEAN) AS unexcused_flag,
        CAST(ra.tardy_flag     AS BOOLEAN) AS tardy_flag
    FROM {{ source('raw', 'raw_attendance') }} ra
    -- Filter to weekdays (same rule as stg_aeries__attendance)
    WHERE DAYOFWEEK(CAST(ra.attendance_date AS DATE)) NOT IN (0, 6)
),

discipline_by_student AS (
    SELECT
        fd.student_id_hash AS student_key,
        fd.academic_year,
        fd.incident_date,
        COUNT(*) AS incident_cnt
    FROM {{ ref('fact_discipline') }} fd
    GROUP BY fd.student_id_hash, fd.academic_year, fd.incident_date
),

-- Anchor each academic year on its own last school day so historical years
-- keep meaningful rolling windows.
year_end AS (
    SELECT
        academic_year,
        MAX(attendance_date) AS latest_date
    FROM daily
    GROUP BY academic_year
),

window_metrics AS (
    SELECT
        d.student_key,
        d.academic_year,
        wd.window_type,
        COUNT(*)                                                   AS total_school_days,
        SUM(CASE WHEN d.present_flag   THEN 1 ELSE 0 END)          AS present_days,
        SUM(CASE WHEN d.absent_flag    THEN 1 ELSE 0 END)          AS absent_days,
        SUM(CASE WHEN d.excused_flag   THEN 1 ELSE 0 END)          AS excused_absences,
        SUM(CASE WHEN d.unexcused_flag THEN 1 ELSE 0 END)          AS unexcused_absences,
        SUM(CASE WHEN d.tardy_flag     THEN 1 ELSE 0 END)          AS tardy_incidents,
        ROUND(
            100.0 * SUM(CASE WHEN d.present_flag THEN 1 ELSE 0 END)
            / NULLIF(COUNT(*), 0),
            2
        )                                                          AS attendance_rate,
        ROUND(
            100.0 * SUM(CASE WHEN d.unexcused_flag THEN 1 ELSE 0 END)
            / NULLIF(COUNT(*), 0),
            2
        )                                                          AS unexcused_absence_rate,
        ROUND(
            100.0 * SUM(CASE WHEN d.tardy_flag THEN 1 ELSE 0 END)
            / NULLIF(COUNT(*), 0),
            2
        )                                                          AS tardy_rate
    FROM daily d
    CROSS JOIN window_defs wd
    JOIN year_end l
        ON  d.academic_year = l.academic_year
        AND d.attendance_date >= l.latest_date - wd.window_days
    GROUP BY d.student_key, d.academic_year, wd.window_type
),

trend AS (
    SELECT
        m30.student_key,
        m30.academic_year,
        CASE
            WHEN m30.attendance_rate < m90.attendance_rate - 2 THEN 'declining'
            WHEN m30.attendance_rate > m90.attendance_rate + 2 THEN 'improving'
            ELSE 'stable'
        END AS pattern_direction
    FROM window_metrics m30
    JOIN window_metrics m90
        ON  m30.student_key = m90.student_key
        AND m30.academic_year = m90.academic_year
        AND m30.window_type = '30d'
        AND m90.window_type = '90d'
),

window_discipline AS (
    SELECT
        ds.student_key,
        ds.academic_year,
        wd.window_type,
        SUM(ds.incident_cnt) AS discipline_incidents
    FROM discipline_by_student ds
    CROSS JOIN window_defs wd
    JOIN year_end l
        ON  ds.academic_year = l.academic_year
        AND ds.incident_date >= l.latest_date - wd.window_days
    GROUP BY ds.student_key, ds.academic_year, wd.window_type
)

SELECT
    wm.student_key,
    wm.academic_year,
    l.latest_date - wd.window_days AS window_start_date,
    wm.window_type,

    wm.total_school_days,
    wm.present_days,
    wm.absent_days,
    wm.excused_absences,
    wm.unexcused_absences,
    wm.tardy_incidents,

    wm.attendance_rate,
    ROUND(100.0 - wm.attendance_rate, 2) AS absence_rate,
    wm.unexcused_absence_rate,
    wm.tardy_rate,

    CASE
        WHEN (100.0 - wm.attendance_rate) >= 10.0 THEN 1
        ELSE 0
    END AS chronic_absence_flag,

    COALESCE(wdsc.discipline_incidents, 0) AS discipline_incidents_in_window,

    -- Correlation score: meaningful only when both absences and discipline exist.
    -- Scaled 0–100: absence_rate_factor × discipline_factor.
    ROUND(
        LEAST(
            COALESCE(
                (100.0 - wm.attendance_rate) / 10.0 * 1.0, 0
            ) * COALESCE(wdsc.discipline_incidents * 10.0, 0),
            100.0
        ),
        0
    ) AS absence_discipline_correlation_score,

    COALESCE(t.pattern_direction, 'stable') AS pattern_direction,

    CURRENT_TIMESTAMP AS _loaded_at

FROM window_metrics wm
JOIN year_end l
    ON wm.academic_year = l.academic_year
JOIN window_defs wd ON wm.window_type = wd.window_type
LEFT JOIN trend t
    ON  wm.student_key   = t.student_key
    AND wm.academic_year = t.academic_year
LEFT JOIN window_discipline wdsc
    ON  wm.student_key   = wdsc.student_key
    AND wm.academic_year = wdsc.academic_year
    AND wm.window_type   = wdsc.window_type

ORDER BY wm.student_key, wm.academic_year, wm.window_type
