
-- models/staging/stg_attendance.sql
-- Staging: Standardize raw_attendance with schema normalization
-- Light transformations: date parts, day categorization

{{ config(
    schema='staging',
    tags=['staging', 'attendance']
) }}

SELECT
    CAST(StudentID AS VARCHAR) as student_id_raw,
    CAST(SchoolCode AS VARCHAR) as school_id,
    CAST(AcademicYear AS VARCHAR) as academic_year,
    CAST(AttendanceProgramCodePrimary AS VARCHAR) as attendance_program_code,

    -- Aggregated metrics (already calculated in source)
    CAST(DaysEnrolled AS INTEGER) as days_enrolled,
    CAST(DaysPresent AS INTEGER) as days_present,
    CAST(DaysAbsence AS INTEGER) as days_absent,
    CAST(DaysExcused AS INTEGER) as days_excused,
    CAST(DaysUnexcused AS INTEGER) as days_unexcused,
    CAST(DaysTardy AS INTEGER) as days_tardy,
    CAST(DaysOfTruancy AS INTEGER) as days_truancy,
    CAST(DaysSuspension AS INTEGER) as days_suspended,
    CAST(DaysInSchoolSuspension AS INTEGER) as days_in_school_suspension,
    CAST(DaysCompleteIndependentStudy AS INTEGER) as days_complete_independent_study,
    CAST(DaysIncompleteIndependentStudy AS INTEGER) as days_incomplete_independent_study,

    CAST(PeriodsExpectedToAttend AS INTEGER) as periods_expected,
    CAST(PeriodsAttended AS INTEGER) as periods_attended,
    CAST(PeriodsExcusedAbsence AS INTEGER) as periods_excused_absence,
    CAST(PeriodsUnexcusedAbsence AS INTEGER) as periods_unexcused_absence,
    CAST(PeriodsOutOfSchoolSuspension AS INTEGER) as periods_out_of_school_suspension,
    CAST(PeriodsAttendedInSchoolSuspension AS INTEGER) as periods_in_school_suspension,

    -- Rate calculations (already in source)
    CAST(NULL AS DOUBLE) as attendance_rate,
    CAST(NULL AS DOUBLE) as absence_rate,
    CAST(NULL AS DOUBLE) as excused_absence_rate,

    CURRENT_TIMESTAMP as dbt_load_timestamp,
    '{{ run_started_at }}' as dbt_run_timestamp
FROM {{ source('raw', 'raw_attendance') }}
