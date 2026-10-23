-- models/mart_core/core/dim_student_demographics.sql
-- Aggregated demographics dimension with k-anonymity enforcement
-- FERPA compliant: cell suppression for groups with fewer than 5 students
--
-- Policy: every quasi-identifier combination is aggregated first; groups
-- with student_count < 5 have ALL cells suppressed (quasi-identifiers and
-- statistics set to NULL) and are flagged with is_suppressed = true, so
-- small-cell membership can never be inferred. Groups with k >= 5 are
-- published as-is.
-- Updated: Added race codes and additional program flags

{{ config(
    materialized='table',
    schema='core',
    unique_key=['grade_level', 'gender', 'ethnicity', 'primary_race', 'school_id', 'special_education_flag', 'ell_status', 'free_reduced_lunch_flag'],
    tags=['core', 'dimensions', 'demographics', 'aggregated', 'k_anonymity']
) }}

{% set k_threshold = 5 %}

WITH aggregated AS (

    SELECT
        grade_level,
        gender,
        ethnicity,
        primary_race,
        is_multi_racial,
        school_id,

        -- Program participation flags
        special_education_flag,
        ell_status,
        free_reduced_lunch_flag,
        homeless_flag,
        foster_care_flag,
        section_504_flag,
        gate_flag,

        COUNT(DISTINCT student_id_hash) as student_count,

        ROUND(AVG(age_at_event), 1) as avg_age,
        MIN(age_at_event) as min_age,
        MAX(age_at_event) as max_age,

        COUNT(CASE WHEN enrollment_status = 'ACTIVE' THEN 1 END) as active_count,
        ROUND(
            COUNT(CASE WHEN enrollment_status = 'ACTIVE' THEN 1 END)::FLOAT
            / NULLIF(COUNT(DISTINCT student_id_hash), 0),
            3
        ) as active_rate

    FROM {{ ref('dim_students') }}
    GROUP BY
        grade_level, gender, ethnicity, primary_race, is_multi_racial, school_id,
        special_education_flag, ell_status, free_reduced_lunch_flag,
        homeless_flag, foster_care_flag, section_504_flag, gate_flag

)

SELECT
    -- Quasi-identifiers: suppressed to NULL when the group has < {{ k_threshold }} students
    CASE WHEN student_count >= {{ k_threshold }} THEN grade_level END as grade_level,
    CASE WHEN student_count >= {{ k_threshold }} THEN gender END as gender,
    CASE WHEN student_count >= {{ k_threshold }} THEN ethnicity END as ethnicity,
    CASE WHEN student_count >= {{ k_threshold }} THEN primary_race END as primary_race,
    CASE WHEN student_count >= {{ k_threshold }} THEN is_multi_racial END as is_multi_racial,
    CASE WHEN student_count >= {{ k_threshold }} THEN school_id END as school_id,

    CASE WHEN student_count >= {{ k_threshold }} THEN special_education_flag END as special_education_flag,
    CASE WHEN student_count >= {{ k_threshold }} THEN ell_status END as ell_status,
    CASE WHEN student_count >= {{ k_threshold }} THEN free_reduced_lunch_flag END as free_reduced_lunch_flag,
    CASE WHEN student_count >= {{ k_threshold }} THEN homeless_flag END as homeless_flag,
    CASE WHEN student_count >= {{ k_threshold }} THEN foster_care_flag END as foster_care_flag,
    CASE WHEN student_count >= {{ k_threshold }} THEN section_504_flag END as section_504_flag,
    CASE WHEN student_count >= {{ k_threshold }} THEN gate_flag END as gate_flag,

    -- Statistics: suppressed alongside the quasi-identifiers
    CASE WHEN student_count >= {{ k_threshold }} THEN student_count END as student_count,
    CASE WHEN student_count >= {{ k_threshold }} THEN avg_age END as avg_age,
    CASE WHEN student_count >= {{ k_threshold }} THEN min_age END as min_age,
    CASE WHEN student_count >= {{ k_threshold }} THEN max_age END as max_age,
    CASE WHEN student_count >= {{ k_threshold }} THEN active_count END as active_count,
    CASE WHEN student_count >= {{ k_threshold }} THEN active_rate END as active_rate,

    -- Transparency flag: true when every cell in the row was suppressed
    (student_count < {{ k_threshold }}) as is_suppressed

FROM aggregated
