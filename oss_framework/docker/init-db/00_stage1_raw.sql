-- OSS Framework SIS Database Initialization
-- Stage 1: Raw Data (Landing Zone)
-- Date: 2025-01-26

CREATE SCHEMA IF NOT EXISTS stage_1;

-- ============================================
-- STAGE 1: RAW TABLES (FROM SIS EXPORT)
-- ============================================

CREATE TABLE stage_1.students (
    student_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    district_student_id VARCHAR(50) UNIQUE,
    first_name VARCHAR(100),
    middle_name VARCHAR(100),
    last_name VARCHAR(100),
    date_of_birth DATE,
    gender VARCHAR(50),
    race_ethnicity VARCHAR(100),
    home_language VARCHAR(50),
    english_learner BOOLEAN DEFAULT false,
    special_education_status VARCHAR(100),
    free_reduced_lunch BOOLEAN DEFAULT false,
    homeless_status BOOLEAN DEFAULT false,
    foster_care BOOLEAN DEFAULT false,
    migrant_status BOOLEAN DEFAULT false,
    email VARCHAR(255),
    phone_primary VARCHAR(20),
    phone_secondary VARCHAR(20),
    address_street VARCHAR(255),
    address_city VARCHAR(100),
    address_state VARCHAR(2),
    address_zip VARCHAR(10),
    emergency_contact_name VARCHAR(100),
    emergency_contact_phone VARCHAR(20),
    enrollment_date DATE,
    withdrawal_date DATE,
    withdrawal_reason VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    data_source VARCHAR(50) DEFAULT 'SIS_EXPORT',
    load_date DATE DEFAULT CURRENT_DATE
);

CREATE TABLE stage_1.courses (
    course_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    district_course_id VARCHAR(50) UNIQUE,
    course_code VARCHAR(20),
    course_name VARCHAR(255),
    description TEXT,
    subject_area VARCHAR(100),
    grade_level_min INT,
    grade_level_max INT,
    credit_hours NUMERIC(5,2),
    instructional_minutes INT,
    is_honors BOOLEAN DEFAULT false,
    is_ap BOOLEAN DEFAULT false,
    is_ib BOOLEAN DEFAULT false,
    department VARCHAR(100),
    semester VARCHAR(20),
    academic_year VARCHAR(10),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    data_source VARCHAR(50) DEFAULT 'SIS_EXPORT',
    load_date DATE DEFAULT CURRENT_DATE
);

CREATE TABLE stage_1.enrollment (
    enrollment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id UUID REFERENCES stage_1.students(student_id),
    course_id UUID REFERENCES stage_1.courses(course_id),
    enrollment_date DATE,
    withdrawal_date DATE,
    withdrawal_reason VARCHAR(255),
    grade_earned VARCHAR(5),
    grade_numeric NUMERIC(5,2),
    grade_letter VARCHAR(2),
    gpa_points NUMERIC(5,2),
    credits_earned NUMERIC(5,2),
    attendance_percentage NUMERIC(5,2),
    tardies_count INT DEFAULT 0,
    absences_count INT DEFAULT 0,
    excused_absences INT DEFAULT 0,
    behavior_incidents INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    data_source VARCHAR(50) DEFAULT 'SIS_EXPORT',
    load_date DATE DEFAULT CURRENT_DATE
);

CREATE TABLE stage_1.attendance (
    attendance_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id UUID REFERENCES stage_1.students(student_id),
    course_id UUID REFERENCES stage_1.courses(course_id),
    attendance_date DATE,
    status VARCHAR(20),
    minutes_present INT,
    minutes_absent INT,
    is_tardy BOOLEAN DEFAULT false,
    is_excused BOOLEAN DEFAULT false,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    data_source VARCHAR(50) DEFAULT 'SIS_EXPORT',
    load_date DATE DEFAULT CURRENT_DATE
);

CREATE TABLE stage_1.academic_records (
    record_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id UUID REFERENCES stage_1.students(student_id),
    course_id UUID REFERENCES stage_1.courses(course_id),
    assignment_name VARCHAR(255),
    assignment_type VARCHAR(50),
    points_possible NUMERIC(10,2),
    points_earned NUMERIC(10,2),
    percentage_score NUMERIC(5,2),
    due_date DATE,
    submission_date DATE,
    is_late BOOLEAN DEFAULT false,
    submission_status VARCHAR(50),
    teacher_comments TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    data_source VARCHAR(50) DEFAULT 'SIS_EXPORT',
    load_date DATE DEFAULT CURRENT_DATE
);

-- ============================================
-- INDEXES FOR PERFORMANCE
-- ============================================

CREATE INDEX idx_stage_1_students_district_id ON stage_1.students(district_student_id);
CREATE INDEX idx_stage_1_students_enrollment_date ON stage_1.students(enrollment_date);
CREATE INDEX idx_stage_1_courses_district_id ON stage_1.courses(district_course_id);
CREATE INDEX idx_stage_1_enrollment_student_id ON stage_1.enrollment(student_id);
CREATE INDEX idx_stage_1_enrollment_course_id ON stage_1.enrollment(course_id);
CREATE INDEX idx_stage_1_attendance_student_id ON stage_1.attendance(student_id);
CREATE INDEX idx_stage_1_attendance_date ON stage_1.attendance(attendance_date);
CREATE INDEX idx_stage_1_academic_records_student_id ON stage_1.academic_records(student_id);

-- ============================================
-- AUDIT LOGGING
-- ============================================

CREATE TABLE stage_1.data_quality_log (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    table_name VARCHAR(100),
    record_count INT,
    null_count INT,
    duplicate_count INT,
    validation_status VARCHAR(50),
    validation_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

-- ============================================
-- VALIDATION CHECKS (Stage 1)
-- ============================================

CREATE OR REPLACE FUNCTION stage_1.validate_students()
RETURNS TABLE (
    validation_name VARCHAR,
    record_count INT,
    issue_count INT,
    status VARCHAR
) AS $$
BEGIN
    RETURN QUERY
    WITH checks AS (
        SELECT 'total_records' as check_name, COUNT(*) as total FROM stage_1.students
        UNION ALL
        SELECT 'null_first_names', COUNT(*) FROM stage_1.students WHERE first_name IS NULL
        UNION ALL
        SELECT 'null_last_names', COUNT(*) FROM stage_1.students WHERE last_name IS NULL
        UNION ALL
        SELECT 'invalid_dob', COUNT(*) FROM stage_1.students WHERE date_of_birth > CURRENT_DATE
        UNION ALL
        SELECT 'future_enrollment_dates', COUNT(*) FROM stage_1.students WHERE enrollment_date > CURRENT_DATE
    )
    SELECT 
        check_name::VARCHAR,
        (SELECT total FROM checks WHERE check_name = 'total_records')::INT,
        total::INT,
        CASE WHEN total > 0 THEN 'FAIL' ELSE 'PASS' END::VARCHAR
    FROM checks
    WHERE check_name != 'total_records';
END;
$$ LANGUAGE plpgsql;
