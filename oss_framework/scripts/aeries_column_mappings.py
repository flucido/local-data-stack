#!/usr/bin/env python3
"""Column mappings from AeRIES PascalCase to dbt snake_case."""

# Map real AeRIES column names (PascalCase) to expected dbt column names (snake_case)
# Based on actual Parquet data structure and dbt staging model requirements

STUDENTS_MAPPING = {
    # Identifiers
    "StudentID": "student_id",
    "FirstName": "first_name",
    "LastName": "last_name",
    "Birthdate": "date_of_birth",
    # Demographics
    "Gender": "gender",
    "EthnicityCode": "ethnicity",
    "Grade": "grade_level",
    "SchoolCode": "school_id",
    # Language
    "HomeLanguageCode": "home_language",
    # Program flags (need to derive from programs table, set NULL for now)
    "NULL_ell_status": "ell_status",
    "NULL_special_education": "special_education",
    "NULL_free_reduced_lunch": "free_reduced_lunch",
    "NULL_homeless": "homeless",
    "NULL_foster_care": "foster_care",
    "NULL_section_504": "section_504",
    # Enrollment dates
    "SchoolEnterDate": "enrollment_date",
    "SchoolLeaveDate": "withdrawal_date",
    # Metadata
    "ExtractedAt": "created_at",
    "ExtractedAt_updated": "updated_at",  # Use same field for both
    "AcademicYear": "load_date",  # Use year as load marker
}

ATTENDANCE_MAPPING = {
    # Identifiers
    "StudentID": "student_id",
    "SchoolCode": "school_id",
    "AcademicYear": "attendance_date",  # Will need transformation - this is year not date
    # Attendance metrics
    "DaysPresent": "present_flag",
    "DaysAbsence": "absent_flag",
    "DaysUnexcused": "unexcused_flag",
    # Status (need to derive)
    "NULL_attendance_status": "attendance_status",
    "NULL_absence_reason": "absence_reason",
    "NULL_tardy_flag": "tardy_flag",
    "NULL_excused_flag": "excused_flag",
    # Metadata
    "ExtractedAt": "created_at",
    "AcademicYear": "load_date",
}

ACADEMIC_RECORDS_MAPPING = {
    # Identifiers
    "StudentID": "student_id",
    "SchoolCode": "school_id",
    "CourseTitle": "course_id",  # Best approximation
    # Performance
    "Grade": "grade",  # This might conflict with grade_level
    "NULL_score": "score",
    # Context
    "AcademicYear": "school_year",
    "NULL_term": "term",
    "NULL_section_id": "section_id",
    "NULL_teacher_id": "teacher_id",
    # Metadata
    "NULL_record_id": "record_id",
    "ExtractedAt": "created_at",
    "AcademicYear": "load_date",
}

DISCIPLINE_MAPPING = {
    # Identifiers
    "StudentID": "student_id",
    "SchoolCode": "school_id",
    # Incident details
    "NULL_incident_id": "incident_id",
    "NULL_incident_date": "incident_date",
    "NULL_incident_type": "incident_type",
    "NULL_severity": "severity",
    "NULL_resolution": "resolution",
    "NULL_suspension_days": "suspension_days",
    # Metadata
    "ExtractedAt": "created_at",
    "AcademicYear": "load_date",
}

ENROLLMENT_MAPPING = {
    # Identifiers
    "StudentID": "student_id",
    "SchoolCode": "school_id",
    "StudentNumber": "enrollment_id",  # Best approximation
    # Enrollment details
    "Grade": "grade_level",
    "AcademicYear": "school_year",
    "SchoolEnterDate": "enrollment_date",
    "SchoolLeaveDate": "withdrawal_date",
    "InactiveStatusCode": "enrollment_status",
    # Metadata
    "ExtractedAt": "created_at",
    "AcademicYear": "load_date",
}

PROGRAMS_MAPPING = {
    # Identifiers (already snake_case in real data)
    "StudentID": "StudentID",
    "ProgramCode": "ProgramCode",
    "ProgramDescription": "ProgramDescription",
    "EligibilityStartDate": "EligibilityStartDate",
    "EligibilityEndDate": "EligibilityEndDate",
    "ParticipationStartDate": "ParticipationStartDate",
    "ParticipationEndDate": "ParticipationEndDate",
    "AcademicYear": "AcademicYear",
    "ExtractedAt": "ExtractedAt",
    "year": "year",
}

GPA_MAPPING = {
    # Identifiers (need to check actual schema)
    "StudentID": "StudentID",
    "AcademicYear": "AcademicYear",
    "year": "year",
    # GPA metrics will be in the actual file
}

# Domain to mapping dictionary
DOMAIN_MAPPINGS = {
    "students": STUDENTS_MAPPING,
    "attendance_transformed": ATTENDANCE_MAPPING,
    "grades_transformed": ACADEMIC_RECORDS_MAPPING,
    "discipline_transformed": DISCIPLINE_MAPPING,
    "enrollment": ENROLLMENT_MAPPING,
    "programs": PROGRAMS_MAPPING,
    "gpa": GPA_MAPPING,
}


def generate_select_clause(domain: str, source_table: str = None) -> str:
    """Generate SQL SELECT clause with column renaming."""
    mapping = DOMAIN_MAPPINGS.get(domain, {})
    if not mapping:
        return "*"

    select_parts = []
    for pascal_col, snake_col in mapping.items():
        if pascal_col.startswith("NULL_"):
            # Column doesn't exist in source, create as NULL
            select_parts.append(f"NULL as {snake_col}")
        elif pascal_col.endswith("_updated"):
            # Use same column as another field
            base_col = pascal_col.replace("_updated", "")
            select_parts.append(f"{base_col} as {snake_col}")
        else:
            # Standard rename
            if pascal_col == snake_col:
                select_parts.append(pascal_col)
            else:
                select_parts.append(f"{pascal_col} as {snake_col}")

    return ",\n    ".join(select_parts)


if __name__ == "__main__":
    # Test output
    for domain in ["students", "attendance_transformed", "enrollment"]:
        print(f"\n{domain.upper()}:")
        print(f"SELECT\n    {generate_select_clause(domain)}")
        print(f"FROM raw_{domain}")
