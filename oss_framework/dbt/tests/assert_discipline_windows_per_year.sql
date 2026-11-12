-- Singular test: per-year window anchoring regression guard.
-- Every academic year present in fact_discipline must have rows in
-- agg_discipline_windows. With per-year anchoring, each year is anchored on
-- its own last incident date, so any year that silently drops out (e.g. a
-- regression back to a single global MAX(date) anchor) fails here.
WITH discipline_years AS (
    SELECT DISTINCT academic_year
    FROM {{ ref('fact_discipline') }}
    WHERE academic_year IS NOT NULL
),

window_years AS (
    SELECT DISTINCT academic_year
    FROM {{ ref('agg_discipline_windows') }}
)

SELECT
    d.academic_year,
    'agg_discipline_windows is missing academic year: ' || d.academic_year AS failure_message
FROM discipline_years d
LEFT JOIN window_years w ON d.academic_year = w.academic_year
WHERE w.academic_year IS NULL
