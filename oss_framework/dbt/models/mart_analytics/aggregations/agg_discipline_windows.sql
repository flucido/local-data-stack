{{ config(
    materialized='table',
    schema='analytics',
    unique_id='agg_discipline_windows'
) }}

WITH discipline_base AS (
    SELECT
        student_id_hash AS student_key,
        academic_year,
        DATE(incident_date) AS incident_date
    FROM {{ ref('fact_discipline') }}
),

-- Anchor each academic year on its own last incident date so historical
-- years get meaningful windows instead of anchoring on a single global max.
year_end AS (
    SELECT
        academic_year,
        MAX(DATE(incident_date)) AS max_incident_date
    FROM discipline_base
    GROUP BY academic_year
),

-- 30-day window
window_30d AS (
    SELECT
        db.student_key,
        db.academic_year,
        l.max_incident_date - 30 AS window_start_date,
        '30d' AS window_type,
        COUNT(*) AS incident_count,
        COUNT(*) AS incident_frequency_rate
    FROM discipline_base db
    JOIN year_end l
        ON db.academic_year = l.academic_year
    WHERE db.incident_date >= l.max_incident_date - 30
        AND db.incident_date <= l.max_incident_date
    GROUP BY db.student_key, db.academic_year, l.max_incident_date
),

-- 90-day window
window_90d AS (
    SELECT
        db.student_key,
        db.academic_year,
        l.max_incident_date - 90 AS window_start_date,
        '90d' AS window_type,
        COUNT(*) AS incident_count,
        COUNT(*) AS incident_frequency_rate
    FROM discipline_base db
    JOIN year_end l
        ON db.academic_year = l.academic_year
    WHERE db.incident_date >= l.max_incident_date - 90
        AND db.incident_date <= l.max_incident_date
    GROUP BY db.student_key, db.academic_year, l.max_incident_date
),

-- Term window
window_term AS (
    SELECT
        db.student_key,
        db.academic_year,
        DATE_TRUNC('quarter', l.max_incident_date) AS window_start_date,
        'term' AS window_type,
        COUNT(*) AS incident_count,
        COUNT(*) AS incident_frequency_rate
    FROM discipline_base db
    JOIN year_end l
        ON db.academic_year = l.academic_year
    WHERE db.incident_date >= DATE_TRUNC('quarter', l.max_incident_date)
        AND db.incident_date <= l.max_incident_date
    GROUP BY db.student_key, db.academic_year, l.max_incident_date
),

combined AS (
    SELECT * FROM window_30d
    UNION ALL
    SELECT * FROM window_90d
    UNION ALL
    SELECT * FROM window_term
)

SELECT
    student_key,
    academic_year,
    window_start_date,
    window_type,
    COALESCE(incident_count, 0) AS incident_count,
    COALESCE(incident_frequency_rate, 0) AS incident_frequency_rate,
    CURRENT_TIMESTAMP AS _loaded_at
FROM combined
WHERE student_key IS NOT NULL
ORDER BY student_key, academic_year, window_type
