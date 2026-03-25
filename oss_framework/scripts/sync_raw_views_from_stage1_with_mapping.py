#!/usr/bin/env python3
"""Create DuckDB compatibility views for raw_* from Stage 1 Parquet with column mapping."""

from __future__ import annotations

from pathlib import Path

import duckdb

from config import DUCKDB_DATABASE_PATH, STAGE1_PATH


RAW_ENTITIES = [
    "raw_students",
    "raw_attendance",
    "raw_academic_records",
    "raw_discipline",
    "raw_enrollment",
    "raw_aeries_programs",
    "raw_aeries_gpa",
]

# Mapping from raw_* entity names to their corresponding Aeries domain directories
DOMAIN_MAPPING = {
    "raw_students": "students",
    "raw_attendance": "attendance_transformed",
    "raw_academic_records": "grades_transformed",
    "raw_discipline": "discipline_transformed",
    "raw_enrollment": "enrollment",
    "raw_aeries_programs": "programs",
    "raw_aeries_gpa": "gpa",
}

# Column mappings from AeRIES PascalCase to dbt snake_case
# Only includes columns actually referenced by staging models
COLUMN_MAPPINGS = {
    "raw_students": """
        StudentID as student_id,
        FirstName as first_name,
        LastName as last_name,
        Birthdate as date_of_birth,
        Gender as gender,
        EthnicityCode as ethnicity,
        RaceCode1 as race_code_1,
        RaceCode2 as race_code_2,
        RaceCode3 as race_code_3,
        RaceCode4 as race_code_4,
        RaceCode5 as race_code_5,
        Grade as grade_level,
        SchoolCode as school_id,
        HomeLanguageCode as home_language,
        NULL as ell_status,
        NULL as special_education,
        NULL as free_reduced_lunch,
        NULL as homeless,
        NULL as foster_care,
        NULL as section_504,
        SchoolEnterDate as enrollment_date,
        SchoolLeaveDate as withdrawal_date,
        ExtractedAt as created_at,
        ExtractedAt as updated_at,
        AcademicYear as load_date
    """,
    "raw_attendance": """
        StudentID as student_id,
        SchoolCode as school_id,
        AcademicYear as academic_year,
        AttendanceProgramCodePrimary as attendance_program_code,
        DaysEnrolled as days_enrolled,
        DaysPresent as days_present,
        DaysAbsence as days_absent,
        DaysExcused as days_excused,
        DaysUnexcused as days_unexcused,
        DaysTardy as days_tardy,
        DaysOfTruancy as days_truancy,
        DaysSuspension as days_suspended,
        PeriodsExpectedToAttend as periods_expected,
        PeriodsAttended as periods_attended,
        PeriodsExcusedAbsence as periods_excused_absence,
        PeriodsUnexcusedAbsence as periods_unexcused_absence,
        CASE WHEN DaysEnrolled > 0 THEN ROUND(CAST(DaysPresent AS FLOAT) / DaysEnrolled, 4) ELSE NULL END as attendance_rate,
        CASE WHEN DaysEnrolled > 0 THEN ROUND(CAST(DaysAbsence AS FLOAT) / DaysEnrolled, 4) ELSE NULL END as absence_rate,
        CASE WHEN DaysAbsence > 0 THEN ROUND(CAST(DaysExcused AS FLOAT) / DaysAbsence, 4) ELSE NULL END as excused_absence_rate,
        ExtractedAt as created_at,
        ExtractedAt as updated_at,
        AcademicYear as load_date,
        CAST(NULL AS DATE) as attendance_date  -- Aggregated data, no daily dates
    """,
    "raw_academic_records": """
        StudentID as student_id,
        CourseID as course_id,
        CourseTitle as course_title,
        SectionNumber as section_id,
        TeacherNumber as teacher_id,
        SchoolCode as school_id,
        AcademicYear as school_year,
        MP_MarkingPeriod as term,
        MP_Mark as grade,
        CAST(NULL AS DOUBLE) as score,  -- No numeric score in source, only letter grades
        MP_Credit as credit_earned,
        MP_TotalAbsences as total_absences,
        MP_TotalTardies as total_tardies,
        MP_TotalDaysEnrolled as days_enrolled,
        MP_TotalDaysPresent as days_present,
        CASE
            WHEN MP_Mark IN ('A', 'A+') THEN 4.0
            WHEN MP_Mark = 'B' THEN 3.0
            WHEN MP_Mark = 'C' THEN 2.0
            WHEN MP_Mark = 'D' THEN 1.0
            WHEN MP_Mark = 'F' THEN 0.0
            ELSE NULL
        END as gpa_points,
        CASE
            WHEN MP_Mark IN ('A', 'A+', 'B', 'C', 'D') THEN true
            WHEN MP_Mark = 'F' THEN false
            ELSE NULL
        END as is_passing,
        ExtractedAt as created_at,
        ExtractedAt as updated_at,
        AcademicYear as load_date
    """,
    "raw_discipline": """
        StudentID as student_id,
        SchoolOfIncidentCode as school_id,
        IncidentID as incident_id,
        TRY_CAST(IncidentDate AS DATE) as incident_date,
        ShortDescription as incident_type,
        Demerits as demerits,
        CASE
            WHEN Demerits >= 10 THEN 'HIGH'
            WHEN Demerits >= 5 THEN 'MEDIUM'
            WHEN Demerits > 0 THEN 'LOW'
            ELSE NULL
        END as severity_category,
        CASE
            WHEN Admin_Days > 0 THEN true
            ELSE false
        END as is_suspension,
        Admin_DispositionCode as resolution,
        CAST(Admin_Days AS INTEGER) as suspension_days,
        CAST(NULL AS VARCHAR) as severity,  -- Will be derived in staging from severity_category
        ExtractedAt as created_at,
        ExtractedAt as updated_at,
        AcademicYear as load_date
    """,
    "raw_enrollment": """
        StudentNumber as enrollment_id,
        StudentID as student_id,
        SchoolCode as school_id,
        Grade as grade_level,
        AcademicYear as school_year,
        EnterDate as enrollment_date,
        LeaveDate as withdrawal_date,
        ExitReasonCode as exit_reason_code,
        AttendanceProgramCode as attendance_program_code,
        AttendanceProgramCodeAdditional1 as attendance_program_code_add1,
        CASE
            WHEN LeaveDate IS NULL THEN 'ACTIVE'
            ELSE 'WITHDRAWN'
        END as enrollment_status,
        ExtractedAt as created_at,
        ExtractedAt as updated_at,
        AcademicYear as load_date
    """,
    "raw_aeries_programs": """
        StudentID,
        ProgramCode,
        ProgramDescription,
        EligibilityStartDate,
        EligibilityEndDate,
        ParticipationStartDate,
        ParticipationEndDate,
        AcademicYear,
        ExtractedAt,
        year
    """,
    "raw_aeries_gpa": """
        StudentID,
        SchoolCode,
        GPA_CumulativeAcademic,
        GPA_CumulativeTotal,
        CreditsAttempted,
        CreditsCompleted,
        AcademicYear,
        ExtractedAt,
        year
    """,
}


def _base_table_exists(con: duckdb.DuckDBPyConnection, name: str) -> bool:
    row = con.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_schema = 'main'
          AND table_name = ?
          AND table_type = 'BASE TABLE'
        """,
        [name],
    ).fetchone()
    return bool(row and row[0] > 0)


def _view_exists(con: duckdb.DuckDBPyConnection, name: str) -> bool:
    row = con.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_schema = 'main'
          AND table_name = ?
          AND table_type = 'VIEW'
        """,
        [name],
    ).fetchone()
    return bool(row and row[0] > 0)


def sync_raw_views_from_stage1(
    db_path: str | Path | None = None,
    stage1_path: str | Path | None = None,
    rename_legacy_tables: bool = True,
) -> dict:
    """Create or replace raw_* views for AeRIES Parquet files with column mapping.

    Handles year=YYYY-YYYY partitioning and PascalCase to snake_case conversion.
    """
    db = str(db_path or DUCKDB_DATABASE_PATH)
    stage1 = Path(stage1_path or STAGE1_PATH).resolve()

    con = duckdb.connect(db)
    try:
        actions: list[str] = []
        for entity in RAW_ENTITIES:
            legacy = f"legacy_{entity}"

            if rename_legacy_tables and _base_table_exists(con, entity):
                # Avoid overwriting if a legacy table already exists
                if not _base_table_exists(con, legacy) and not _view_exists(con, legacy):
                    con.execute(f"ALTER TABLE {entity} RENAME TO {legacy}")
                    actions.append(f"renamed_table:{entity}->{legacy}")
                else:
                    actions.append(f"kept_table:{entity} (legacy exists)")

            # Get column mapping for this entity
            column_select = COLUMN_MAPPINGS.get(entity, "*")
            if column_select != "*":
                column_select = column_select.strip()

            # All domains now use year-based partitioning at stage1/aeries/{domain}/year=*/
            domain = DOMAIN_MAPPING.get(entity, entity.replace("raw_aeries_", ""))
            parquet_glob = stage1 / "aeries" / domain / "year=*" / "*.parquet"

            # DuckDB doesn't support prepared parameters for this DDL statement.
            parquet_glob_sql = str(parquet_glob).replace("'", "''")

            # Create view with column mapping
            sql = f"""
                CREATE OR REPLACE VIEW {entity} AS 
                SELECT {column_select}
                FROM read_parquet('{parquet_glob_sql}')
            """

            con.execute(sql)
            actions.append(f"view:{entity}<-{parquet_glob} (mapped)")

        return {
            "db_path": db,
            "stage1_path": str(stage1),
            "actions": actions,
        }
    finally:
        con.close()


if __name__ == "__main__":
    result = sync_raw_views_from_stage1()
    print("✅ Synced raw_* views from Stage 1 Parquet with column mapping")
    for a in result["actions"]:
        print(f"  - {a}")
