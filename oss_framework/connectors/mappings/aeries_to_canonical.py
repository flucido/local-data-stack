"""Aeries SIS → canonical column mappings.

Translates Aeries PascalCase column names to the vendor-neutral canonical
schema used by the SISConnector interface.  Keys prefixed with ``NULL_``
indicate columns that don't exist in the Aeries source — they become NULL
in the canonical output.
"""

# Domain: students
STUDENTS_MAPPING = {
    # Identifiers
    "StudentID": "student_id",
    "FirstName": "first_name",
    "LastName": "last_name",
    "Birthdate": "date_of_birth",
    # Demographics
    "Gender": "gender",
    "EthnicityCode": "race_ethnicity",
    "Grade": "grade_level",
    "SchoolCode": "school_id",
    "AcademicYear": "academic_year",
    # Language
    "HomeLanguageCode": "home_language",
    # Program flags — derived from programs table, set NULL at this layer
    "NULL_ell_status": "ell_status",
    "NULL_special_education_flag": "special_education_flag",
    "NULL_free_reduced_lunch_flag": "free_reduced_lunch_flag",
    "NULL_homeless_flag": "homeless_flag",
    "NULL_foster_care_flag": "foster_care_flag",
    "NULL_section_504_flag": "section_504_flag",
    # Enrollment dates
    "SchoolEnterDate": "enrollment_date",
    "SchoolLeaveDate": "withdrawal_date",
    # Metadata
    "ExtractedAt": "created_at",
}

# Domain: attendance
ATTENDANCE_MAPPING = {
    "StudentID": "student_id",
    "SchoolCode": "school_id",
    "AcademicYear": "academic_year",
    "DaysPresent": "present_flag",
    "DaysAbsence": "absent_flag",
    "DaysUnexcused": "unexcused_flag",
    "NULL_attendance_date": "attendance_date",
    "NULL_attendance_status": "attendance_status",
    "NULL_absence_reason": "absence_reason",
    "NULL_tardy_flag": "tardy_flag",
    "NULL_excused_flag": "excused_flag",
    "ExtractedAt": "created_at",
}

# Domain: grades / academic records
ACADEMIC_RECORDS_MAPPING = {
    "StudentID": "student_id",
    "SchoolCode": "school_id",
    "CourseTitle": "course_id",
    "Grade": "grade",
    "AcademicYear": "school_year",
    "NULL_record_id": "record_id",
    "NULL_score": "score",
    "NULL_term": "term",
    "NULL_section_id": "section_id",
    "NULL_teacher_id": "teacher_id",
    "ExtractedAt": "created_at",
}

# Domain: discipline
DISCIPLINE_MAPPING = {
    "StudentID": "student_id",
    "SchoolCode": "school_id",
    "NULL_incident_id": "incident_id",
    "NULL_incident_date": "incident_date",
    "NULL_incident_type": "incident_type",
    "NULL_severity": "severity",
    "NULL_resolution": "resolution",
    "NULL_suspension_days": "suspension_days",
    "ExtractedAt": "created_at",
}

# Domain: enrollment
ENROLLMENT_MAPPING = {
    "StudentID": "student_id",
    "SchoolCode": "school_id",
    "StudentNumber": "enrollment_id",
    "Grade": "grade_level",
    "AcademicYear": "school_year",
    "SchoolEnterDate": "enrollment_date",
    "SchoolLeaveDate": "withdrawal_date",
    "InactiveStatusCode": "enrollment_status",
    "ExtractedAt": "created_at",
}

# Domain: programs (already close to canonical)
PROGRAMS_MAPPING = {
    "StudentID": "student_id",
    "ProgramCode": "program_code",
    "ProgramDescription": "program_description",
    "EligibilityStartDate": "eligibility_start_date",
    "EligibilityEndDate": "eligibility_end_date",
    "ParticipationStartDate": "participation_start_date",
    "ParticipationEndDate": "participation_end_date",
    "AcademicYear": "academic_year",
    "ExtractedAt": "created_at",
    "year": "year",
}

# Per-domain aggregation (used by AeriesConnector.column_mapping)
AERIES_COLUMN_MAPPING = {
    "students": STUDENTS_MAPPING,
    "attendance": ATTENDANCE_MAPPING,
    "grades": ACADEMIC_RECORDS_MAPPING,
    "discipline": DISCIPLINE_MAPPING,
    "enrollment": ENROLLMENT_MAPPING,
    "programs": PROGRAMS_MAPPING,
}
