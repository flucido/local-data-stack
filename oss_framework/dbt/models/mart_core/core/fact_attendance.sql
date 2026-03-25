
-- models/mart_core/core/fact_attendance.sql
-- Fact: Aggregate attendance summary per student per year (NOT daily grain)

{{ config(
    materialized='table',
    schema='core',
    unique_key=['student_id_hash', 'academic_year', 'school_id'],
    tags=['core', 'facts', 'attendance']
) }}

SELECT
    -- Foreign keys
    {{ hash_pii_secure('sta.student_id_raw') }} as student_id_hash,
    sta.school_id,
    sta.academic_year,
    
    -- Enrollment counts
    sta.days_enrolled,
    sta.days_present,
    sta.days_absent,
    sta.days_excused,
    sta.days_unexcused,
    sta.days_tardy,
    sta.days_truancy,
    sta.days_suspended,
    sta.days_in_school_suspension,
    sta.days_complete_independent_study,
    sta.days_incomplete_independent_study,
    
    -- Period-based attendance
    sta.periods_expected,
    sta.periods_attended,
    sta.periods_excused_absence,
    sta.periods_unexcused_absence,
    sta.periods_out_of_school_suspension,
    sta.periods_in_school_suspension,
    
    -- Calculated rates
    sta.attendance_rate,
    sta.absence_rate,
    sta.excused_absence_rate,
    -- Audit
    CAST(NULL AS TIMESTAMP) as created_at,
    CURRENT_TIMESTAMP as dbt_processed_date

FROM {{ ref('stg_aeries__attendance') }} sta

