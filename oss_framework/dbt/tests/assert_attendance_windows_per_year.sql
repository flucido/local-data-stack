-- Singular test: per-year window anchoring regression guard.
-- Every academic year present in weekday-filtered daily attendance must have
-- rows in agg_attendance_windows. With per-year anchoring, each year is
-- anchored on its own last school day, so any year that silently drops out
-- (e.g. a regression back to a single global MAX(date) anchor) fails here.
WITH daily_years AS (
    SELECT DISTINCT
        CASE
            WHEN MONTH(TRY_CAST(ra.attendance_date AS DATE)) >= 7
                THEN CAST(YEAR(TRY_CAST(ra.attendance_date AS DATE)) AS VARCHAR) || '-' || CAST(YEAR(TRY_CAST(ra.attendance_date AS DATE)) + 1 AS VARCHAR)
            ELSE CAST(YEAR(TRY_CAST(ra.attendance_date AS DATE)) - 1 AS VARCHAR) || '-' || CAST(YEAR(TRY_CAST(ra.attendance_date AS DATE)) AS VARCHAR)
        END AS academic_year
    FROM {{ source('raw', 'raw_attendance') }} ra
    WHERE TRY_CAST(ra.attendance_date AS DATE) IS NOT NULL
      AND DAYOFWEEK(TRY_CAST(ra.attendance_date AS DATE)) NOT IN (0, 6)
),

window_years AS (
    SELECT DISTINCT academic_year
    FROM {{ ref('agg_attendance_windows') }}
)

SELECT
    d.academic_year,
    'agg_attendance_windows is missing academic year: ' || d.academic_year AS failure_message
FROM daily_years d
LEFT JOIN window_years w ON d.academic_year = w.academic_year
WHERE w.academic_year IS NULL
