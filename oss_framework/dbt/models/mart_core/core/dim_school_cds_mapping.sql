{{ config(
    materialized='table',
    schema='core',
    tags=['mapping', 'cde']
) }}

WITH internal_schools AS (
    SELECT DISTINCT
        school_id,
        'SCHOOL_' || school_id AS school_name,
        UPPER(TRIM(school_id)) AS cleaned_name
    FROM {{ ref('stg_aeries__students') }}
    
    UNION
    
    SELECT DISTINCT
        school_id,
        'SCHOOL_' || school_id AS school_name,
        UPPER(TRIM(school_id)) AS cleaned_name
    FROM {{ ref('stg_aeries__attendance') }}
),

cde_schools AS (
    SELECT
        cds_code,
        school_name,
        district_name,
        city,
        county_name,
        doc_type,
        UPPER(TRIM(school_name)) AS cleaned_name,
        latitude,
        longitude
    FROM {{ ref('stg_cde__schools') }}
),

manual_mapping AS (
    SELECT
        school_id,
        cds_code,
        match_method,
        match_confidence
    FROM {{ ref('school_cds_mapping_seed') }}
),

fuzzy_matches AS (
    SELECT
        i.school_id,
        i.school_name AS internal_name,
        c.cds_code,
        c.school_name AS cde_name,
        c.district_name,
        c.city,
        levenshtein(i.cleaned_name, c.cleaned_name) AS lev_distance,
        1.0 - (CAST(levenshtein(i.cleaned_name, c.cleaned_name) AS DOUBLE) / 
               CAST(GREATEST(LENGTH(i.cleaned_name), LENGTH(c.cleaned_name)) AS DOUBLE)) AS similarity_score,
        'fuzzy_name' AS match_method,
        ROW_NUMBER() OVER (
            PARTITION BY i.school_id 
            ORDER BY levenshtein(i.cleaned_name, c.cleaned_name) ASC
        ) AS match_rank
    FROM internal_schools i
    CROSS JOIN cde_schools c
    WHERE levenshtein(i.cleaned_name, c.cleaned_name) <= 5
),

best_fuzzy_matches AS (
    SELECT
        school_id,
        cds_code,
        match_method,
        similarity_score AS match_confidence
    FROM fuzzy_matches
    WHERE match_rank = 1
      AND similarity_score >= 0.80
),

combined_mapping AS (
    SELECT
        m.school_id,
        m.cds_code,
        m.match_method,
        m.match_confidence,
        c.school_name AS cde_school_name,
        c.district_name AS cde_district_name,
        c.city AS cde_city,
        c.county_name AS cde_county,
        c.doc_type,
        c.latitude,
        c.longitude,
        TRUE AS is_mapped,
        CURRENT_TIMESTAMP AS mapped_at
    FROM manual_mapping m
    LEFT JOIN cde_schools c ON m.cds_code = c.cds_code
    
    UNION ALL
    
    SELECT
        f.school_id,
        f.cds_code,
        f.match_method,
        f.match_confidence,
        c.school_name AS cde_school_name,
        c.district_name AS cde_district_name,
        c.city AS cde_city,
        c.county_name AS cde_county,
        c.doc_type,
        c.latitude,
        c.longitude,
        TRUE AS is_mapped,
        CURRENT_TIMESTAMP AS mapped_at
    FROM best_fuzzy_matches f
    LEFT JOIN cde_schools c ON f.cds_code = c.cds_code
    WHERE NOT EXISTS (
        SELECT 1 FROM manual_mapping m WHERE m.school_id = f.school_id
    )
),

unmapped_schools AS (
    SELECT
        i.school_id,
        NULL AS cds_code,
        'unmapped' AS match_method,
        0.0 AS match_confidence,
        NULL AS cde_school_name,
        NULL AS cde_district_name,
        NULL AS cde_city,
        NULL AS cde_county,
        NULL AS doc_type,
        NULL AS latitude,
        NULL AS longitude,
        FALSE AS is_mapped,
        CURRENT_TIMESTAMP AS mapped_at
    FROM internal_schools i
    WHERE NOT EXISTS (
        SELECT 1 FROM combined_mapping c WHERE c.school_id = i.school_id
    )
)

SELECT * FROM combined_mapping
UNION ALL
SELECT * FROM unmapped_schools
ORDER BY is_mapped DESC, school_id
