{{ config(
    materialized='table',
    schema='analytics',
    unique_id='agg_discipline_windows'
) }}

WITH discipline_base AS (
    SELECT
        student_id_hash AS student_key,
        DATE(incident_date) AS incident_date
    FROM {{ ref('fact_discipline') }}
),

-- 30-day window
window_30d AS (
    SELECT
        student_key,
        CURRENT_DATE - 30 AS window_start_date,
        '30d' AS window_type,
        COUNT(*) AS incident_count,
        COUNT(*) AS incident_frequency_rate
    FROM discipline_base
    WHERE incident_date >= CURRENT_DATE - 30
        AND incident_date <= CURRENT_DATE
    GROUP BY 1
),

-- 90-day window
window_90d AS (
    SELECT
        student_key,
        CURRENT_DATE - 90 AS window_start_date,
        '90d' AS window_type,
        COUNT(*) AS incident_count,
        COUNT(*) AS incident_frequency_rate
    FROM discipline_base
    WHERE incident_date >= CURRENT_DATE - 90
        AND incident_date <= CURRENT_DATE
    GROUP BY 1
),

-- Term window
window_term AS (
    SELECT
        student_key,
        DATE_TRUNC('quarter', CURRENT_DATE) AS window_start_date,
        'term' AS window_type,
        COUNT(*) AS incident_count,
        COUNT(*) AS incident_frequency_rate
    FROM discipline_base
    WHERE incident_date >= DATE_TRUNC('quarter', CURRENT_DATE)
        AND incident_date <= CURRENT_DATE
    GROUP BY 1
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
    window_start_date,
    window_type,
    COALESCE(incident_count, 0) AS incident_count,
    COALESCE(incident_frequency_rate, 0) AS incident_frequency_rate,
    CURRENT_TIMESTAMP AS _loaded_at
FROM combined
WHERE student_key IS NOT NULL
ORDER BY student_key, window_type
