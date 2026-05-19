-- Stage 2A: Normalized Entity Views
-- Purpose: Create normalized schema with standardized field names, types, and values
-- These views transform raw Stage 1 data into consistent, usable format
-- Database: PostgreSQL (adapt for other databases as needed)
-- Last Updated: 2024

-- ========================================
-- Create Schema and Tables
-- ========================================

-- Create Stage 2A schema
CREATE SCHEMA IF NOT EXISTS stage_2a;
COMMENT ON SCHEMA stage_2a IS 'Normalized entities with standardized schema, fields, and data types';

---

-- ========================================
-- 1. Students Normalized View
-- ========================================

-- Create students_normalized table
CREATE TABLE IF NOT EXISTS stage_2a.students_normalized AS
SELECT
  -- Keys
  s.student_id,
  
  -- Demographics
  COALESCE(s.first_name, 'UNKNOWN') as first_name,
  COALESCE(s.last_name, 'UNKNOWN') as last_name,
  TRIM(COALESCE(s.middle_name, '')) as middle_name,
  DATE_TRUNC('day', s.date_of_birth)::date as date_of_birth,
  EXTRACT(YEAR FROM s.date_of_birth) as birth_year,
  EXTRACT(MONTH FROM s.date_of_birth) as birth_month,
  CASE s.gender
    WHEN 'M' THEN 'Male'
    WHEN 'F' THEN 'Female'
    WHEN 'O' THEN 'Other'
    WHEN 'N' THEN 'Not Specified'
    ELSE COALESCE(s.gender, 'Not Specified')
  END as gender,
  CASE s.ethnicity
    WHEN 'HISP' THEN 'Hispanic'
    WHEN 'AA' THEN 'African American'
    WHEN 'W' THEN 'White'
    WHEN 'AIAN' THEN 'American Indian/Alaska Native'
    WHEN 'ASN' THEN 'Asian'
    WHEN 'PI' THEN 'Native Hawaiian/Pacific Islander'
    WHEN 'TMER' THEN 'Two or More Races'
    ELSE COALESCE(s.ethnicity, 'Unknown')
  END as ethnicity,
  
  -- Enrollment Status
  CASE s.enrollment_status
    WHEN 'A' THEN 'Active'
    WHEN 'G' THEN 'Graduated'
    WHEN 'W' THEN 'Withdrawn'
    WHEN 'T' THEN 'Transferred'
    ELSE COALESCE(s.enrollment_status, 'Unknown')
  END as enrollment_status,
  
  -- Grade and Programs
  CASE
    WHEN s.grade_level NOT BETWEEN 0 AND 12 THEN 0
    ELSE s.grade_level
  END as grade_level,
  CASE s.academic_program
    WHEN 'CP' THEN 'College Prep'
    WHEN 'VOC' THEN 'Vocational'
    WHEN 'STEM' THEN 'STEM'
    WHEN 'IB' THEN 'International Baccalaureate'
    ELSE COALESCE(s.academic_program, 'General')
  END as academic_program,
  
  -- Special Programs
  COALESCE(s.special_education, false) as special_education,
  COALESCE(s.english_learner, false) as english_learner,
  COALESCE(s.free_reduced_lunch, false) as free_reduced_lunch,
  COALESCE(s.gifted_status, false) as gifted_status,
  COALESCE(s.section_504_status, false) as section_504_status,
  
  -- Demographics Indicators
  COALESCE(s.immigrant_status, 'Unknown') as immigrant_status,
  COALESCE(s.homeless_status, 'Housed') as homeless_status,
  
  -- Contact Information (preserved in Stage 2A for configuration validation)
  s.email,
  s.phone,
  s.address,
  
  -- Dates
  DATE_TRUNC('day', s.enrollment_date)::date as enrollment_date,
  COALESCE(DATE_TRUNC('day', s.withdrawal_date)::date, NULL) as withdrawal_date,
  EXTRACT(YEAR FROM AGE(CURRENT_DATE, s.enrollment_date)) as years_enrolled,
  
  -- Academic Performance
  CASE
    WHEN s.gpa NOT BETWEEN 0.0 AND 4.0 THEN NULL
    ELSE ROUND(s.gpa::numeric, 2)
  END as gpa,
  
  -- Metadata
  s.created_date,
  s.updated_date,
  CURRENT_TIMESTAMP as normalized_date
  
FROM stage_1.students s
WHERE s.student_id IS NOT NULL;

CREATE INDEX idx_students_norm_id ON stage_2a.students_normalized(student_id);
CREATE INDEX idx_students_norm_status ON stage_2a.students_normalized(enrollment_status);
CREATE INDEX idx_students_norm_grade ON stage_2a.students_normalized(grade_level);

COMMENT ON TABLE stage_2a.students_normalized IS 'Normalized student records with standardized field names and types';

---

-- ========================================
-- 2. Courses Normalized View
-- ========================================

CREATE TABLE IF NOT EXISTS stage_2a.courses_normalized AS
SELECT
  -- Keys
  c.course_id,
  
  -- Course Information
  COALESCE(c.course_name, 'UNKNOWN') as course_name,
  TRIM(COALESCE(c.course_code, '')) as course_code,
  COALESCE(c.department, 'Unknown') as department,
  COALESCE(c.subject, 'General') as subject,
  
  -- Grade and Credit
  CASE
    WHEN c.grade_level_min NOT BETWEEN 0 AND 12 THEN 0
    ELSE c.grade_level_min
  END as grade_level_min,
  CASE
    WHEN c.grade_level_max NOT BETWEEN 0 AND 12 THEN 12
    ELSE c.grade_level_max
  END as grade_level_max,
  CASE
    WHEN c.credit_hours NOT BETWEEN 0 AND 10 THEN 1.0
    ELSE ROUND(c.credit_hours::numeric, 2)
  END as credit_hours,
  
  -- Course Type
  CASE c.course_type
    WHEN 'AP' THEN 'Advanced Placement'
    WHEN 'HON' THEN 'Honors'
    WHEN 'REG' THEN 'Regular'
    WHEN 'REM' THEN 'Remedial'
    ELSE COALESCE(c.course_type, 'Regular')
  END as course_type,
  
  -- Scheduling
  c.term,
  c.meeting_schedule,
  c.room_number,
  
  -- Capacity
  COALESCE(c.capacity, 0) as capacity,
  COALESCE(c.enrollment_count, 0) as current_enrollment,
  CASE
    WHEN c.capacity = 0 THEN 0
    ELSE ROUND(100.0 * c.enrollment_count / c.capacity, 1)
  END as capacity_percent,
  
  -- Prerequisites and Requirements
  c.prerequisites,
  c.description,
  
  -- Instructor Information (preserved in Stage 2A for validation)
  c.instructor_name,
  c.instructor_email,
  c.instructor_id,
  
  -- Metadata
  c.created_date,
  c.updated_date,
  CURRENT_TIMESTAMP as normalized_date
  
FROM stage_1.courses c
WHERE c.course_id IS NOT NULL;

CREATE INDEX idx_courses_norm_id ON stage_2a.courses_normalized(course_id);
CREATE INDEX idx_courses_norm_dept ON stage_2a.courses_normalized(department);
CREATE INDEX idx_courses_norm_subject ON stage_2a.courses_normalized(subject);

COMMENT ON TABLE stage_2a.courses_normalized IS 'Normalized course records with standardized names and calculated fields';

---

-- ========================================
-- 3. Enrollment Normalized View
-- ========================================

CREATE TABLE IF NOT EXISTS stage_2a.enrollment_normalized AS
SELECT
  -- Keys
  e.enrollment_id,
  e.student_id,
  e.course_id,
  
  -- Term and Status
  e.term,
  CASE e.completion_status
    WHEN 'C' THEN 'Completed'
    WHEN 'I' THEN 'In Progress'
    WHEN 'W' THEN 'Withdrawn'
    WHEN 'I' THEN 'Incomplete'
    ELSE COALESCE(e.completion_status, 'Unknown')
  END as completion_status,
  
  -- Grades and Performance
  CASE e.grade
    WHEN 'A' THEN 'A'
    WHEN 'A-' THEN 'A-'
    WHEN 'B+' THEN 'B+'
    WHEN 'B' THEN 'B'
    WHEN 'B-' THEN 'B-'
    WHEN 'C+' THEN 'C+'
    WHEN 'C' THEN 'C'
    WHEN 'C-' THEN 'C-'
    WHEN 'D+' THEN 'D+'
    WHEN 'D' THEN 'D'
    WHEN 'D-' THEN 'D-'
    WHEN 'F' THEN 'F'
    WHEN 'I' THEN 'Incomplete'
    WHEN 'W' THEN 'Withdrawn'
    WHEN 'P' THEN 'Pass'
    WHEN 'NP' THEN 'No Pass'
    ELSE 'Unknown'
  END as letter_grade,
  
  CASE
    WHEN e.final_grade_percent NOT BETWEEN 0 AND 100 THEN NULL
    ELSE ROUND(e.final_grade_percent::numeric, 1)
  END as final_grade_percent,
  
  CASE
    WHEN e.gpa_contribution NOT BETWEEN 0.0 AND 4.0 THEN NULL
    ELSE ROUND(e.gpa_contribution::numeric, 2)
  END as gpa_contribution,
  
  -- Credit and Weighted Grade
  CASE
    WHEN e.credit_earned NOT BETWEEN 0 AND 10 THEN NULL
    ELSE ROUND(e.credit_earned::numeric, 2)
  END as credit_earned,
  
  CASE
    WHEN e.weighted_grade NOT BETWEEN 0.0 AND 5.0 THEN NULL
    ELSE ROUND(e.weighted_grade::numeric, 2)
  END as weighted_grade,
  
  -- Component Grades
  CASE
    WHEN e.midterm_grade NOT IN ('A', 'B', 'C', 'D', 'F', 'I', 'W') THEN NULL
    ELSE e.midterm_grade
  END as midterm_grade,
  
  CASE
    WHEN e.finals_grade NOT IN ('A', 'B', 'C', 'D', 'F', 'I', 'W') THEN NULL
    ELSE e.finals_grade
  END as finals_grade,
  
  -- Course Characteristics
  COALESCE(e.advanced_placement, false) as advanced_placement,
  COALESCE(e.honors, false) as honors_course,
  
  -- Engagement and Effort
  CASE
    WHEN e.assignment_completion_rate NOT BETWEEN 0 AND 1 THEN NULL
    ELSE ROUND((e.assignment_completion_rate::numeric), 3)
  END as assignment_completion_rate,
  
  CASE
    WHEN e.quiz_average NOT BETWEEN 0 AND 100 THEN NULL
    ELSE ROUND(e.quiz_average::numeric, 1)
  END as quiz_average,
  
  CASE
    WHEN e.test_average NOT BETWEEN 0 AND 100 THEN NULL
    ELSE ROUND(e.test_average::numeric, 1)
  END as test_average,
  
  CASE
    WHEN e.participation_score NOT BETWEEN 0 AND 10 THEN NULL
    ELSE ROUND(e.participation_score::numeric, 1)
  END as participation_score,
  
  CASE
    WHEN e.project_score NOT BETWEEN 0 AND 100 THEN NULL
    ELSE ROUND(e.project_score::numeric, 1)
  END as project_score,
  
  -- Accommodations and Flags
  COALESCE(e.accommodations, 'None') as accommodations,
  COALESCE(e.flag_for_intervention, false) as flag_for_intervention,
  
  -- Dates
  DATE_TRUNC('day', e.enrollment_date)::date as enrollment_date,
  COALESCE(DATE_TRUNC('day', e.withdrawal_date)::date, NULL) as withdrawal_date,
  
  -- Metadata
  e.created_date,
  e.updated_date,
  CURRENT_TIMESTAMP as normalized_date
  
FROM stage_1.enrollment e
WHERE e.enrollment_id IS NOT NULL
  AND e.student_id IS NOT NULL
  AND e.course_id IS NOT NULL;

CREATE INDEX idx_enrollment_norm_id ON stage_2a.enrollment_normalized(enrollment_id);
CREATE INDEX idx_enrollment_norm_student ON stage_2a.enrollment_normalized(student_id);
CREATE INDEX idx_enrollment_norm_course ON stage_2a.enrollment_normalized(course_id);
CREATE INDEX idx_enrollment_norm_term ON stage_2a.enrollment_normalized(term);

COMMENT ON TABLE stage_2a.enrollment_normalized IS 'Normalized enrollment records with standardized grades and performance metrics';

---

-- ========================================
-- 4. Attendance Normalized View
-- ========================================

CREATE TABLE IF NOT EXISTS stage_2a.attendance_normalized AS
SELECT
  -- Keys
  a.attendance_id,
  a.student_id,
  a.course_id,
  
  -- Date (normalized to beginning of week for privacy)
  DATE_TRUNC('week', a.attendance_date)::date as attendance_week,
  
  -- Status
  CASE a.status
    WHEN 'P' THEN 'Present'
    WHEN 'A' THEN 'Absent'
    WHEN 'T' THEN 'Tardy'
    WHEN 'E' THEN 'Excused'
    WHEN 'U' THEN 'Unexcused'
    ELSE COALESCE(a.status, 'Unknown')
  END as attendance_status,
  
  -- Absence Type
  COALESCE(a.reason_code, 'Unknown') as reason_code,
  COALESCE(a.reason_description, '') as reason_description,
  
  -- Counts
  COALESCE(a.present_count, 0) as present_count,
  COALESCE(a.absent_count, 0) as absent_count,
  COALESCE(a.tardy_count, 0) as tardy_count,
  COALESCE(a.excused_count, 0) as excused_count,
  COALESCE(a.unexcused_count, 0) as unexcused_count,
  
  -- Rates
  CASE
    WHEN a.attendance_rate NOT BETWEEN 0 AND 1 THEN NULL
    ELSE ROUND((a.attendance_rate::numeric), 4)
  END as attendance_rate,
  
  CASE
    WHEN a.cumulative_absence_rate NOT BETWEEN 0 AND 1 THEN NULL
    ELSE ROUND((a.cumulative_absence_rate::numeric), 4)
  END as cumulative_absence_rate,
  
  -- Risk Indicators
  COALESCE(a.chronically_absent, false) as chronically_absent,
  CASE a.warning_level
    WHEN 'GREEN' THEN 'Low Risk'
    WHEN 'YELLOW' THEN 'Medium Risk'
    WHEN 'RED' THEN 'High Risk'
    ELSE 'Unknown'
  END as warning_level,
  
  CASE a.trend
    WHEN 'IMP' THEN 'Improving'
    WHEN 'STAB' THEN 'Stable'
    WHEN 'DEC' THEN 'Declining'
    ELSE 'Unknown'
  END as trend,
  
  -- Term
  a.term,
  
  -- Metadata
  a.created_date,
  a.updated_date,
  CURRENT_TIMESTAMP as normalized_date
  
FROM stage_1.attendance a
WHERE a.attendance_id IS NOT NULL
  AND a.student_id IS NOT NULL;

CREATE INDEX idx_attendance_norm_id ON stage_2a.attendance_normalized(attendance_id);
CREATE INDEX idx_attendance_norm_student ON stage_2a.attendance_normalized(student_id);
CREATE INDEX idx_attendance_norm_week ON stage_2a.attendance_normalized(attendance_week);
CREATE INDEX idx_attendance_norm_status ON stage_2a.attendance_normalized(attendance_status);

COMMENT ON TABLE stage_2a.attendance_normalized IS 'Normalized attendance records with dates generalized to week level';

---

-- ========================================
-- 5. Academic Records Normalized View
-- ========================================

CREATE TABLE IF NOT EXISTS stage_2a.academic_records_normalized AS
SELECT
  -- Keys
  ar.record_id,
  ar.student_id,
  ar.course_id,
  
  -- Assignment Information
  ar.assignment_name,
  ar.assignment_type,
  COALESCE(ar.competency_id, 'Unknown') as competency_id,
  COALESCE(ar.competency_name, '') as competency_name,
  COALESCE(ar.standard_code, '') as standard_code,
  
  -- Dates
  DATE_TRUNC('day', ar.assignment_date)::date as assignment_date,
  DATE_TRUNC('day', ar.submission_date)::date as submission_date,
  
  CASE
    WHEN ar.submission_date < ar.assignment_date THEN 'Early'
    WHEN ar.submission_date = ar.assignment_date THEN 'On Time'
    WHEN ar.submission_date <= ar.assignment_date + INTERVAL '3 days' THEN 'Late (< 3 days)'
    WHEN ar.submission_date <= ar.assignment_date + INTERVAL '7 days' THEN 'Late (< 7 days)'
    ELSE 'Very Late'
  END as submission_timeliness,
  
  COALESCE(ar.late_days, 0) as late_days,
  COALESCE(ar.on_time, ar.late_days = 0) as on_time,
  
  -- Points and Scores
  CASE
    WHEN ar.max_points NOT BETWEEN 0 AND 10000 THEN NULL
    ELSE ROUND(ar.max_points::numeric, 2)
  END as max_points,
  
  CASE
    WHEN ar.earned_points NOT BETWEEN 0 AND 10000 THEN NULL
    ELSE ROUND(ar.earned_points::numeric, 2)
  END as earned_points,
  
  CASE
    WHEN ar.score_percent NOT BETWEEN 0 AND 100 THEN NULL
    ELSE ROUND(ar.score_percent::numeric, 1)
  END as score_percent,
  
  -- Mastery Level
  CASE ar.mastery_level
    WHEN 'A' THEN 'Advanced'
    WHEN 'P' THEN 'Proficient'
    WHEN 'D' THEN 'Developing'
    WHEN 'B' THEN 'Beginning'
    ELSE COALESCE(ar.mastery_level, 'Unknown')
  END as mastery_level,
  
  -- Retakes
  COALESCE(ar.retake_count, 0) as retake_count,
  CASE
    WHEN ar.original_score NOT BETWEEN 0 AND 100 THEN NULL
    ELSE ROUND(ar.original_score::numeric, 1)
  END as original_score,
  
  -- Feedback and Support
  COALESCE(ar.feedback_provided, false) as feedback_provided,
  COALESCE(ar.remediation_offered, false) as remediation_offered,
  COALESCE(ar.enrichment_offered, false) as enrichment_offered,
  
  -- Metadata
  ar.created_date,
  ar.updated_date,
  CURRENT_TIMESTAMP as normalized_date
  
FROM stage_1.academic_records ar
WHERE ar.record_id IS NOT NULL
  AND ar.student_id IS NOT NULL;

CREATE INDEX idx_academic_norm_id ON stage_2a.academic_records_normalized(record_id);
CREATE INDEX idx_academic_norm_student ON stage_2a.academic_records_normalized(student_id);
CREATE INDEX idx_academic_norm_course ON stage_2a.academic_records_normalized(course_id);
CREATE INDEX idx_academic_norm_mastery ON stage_2a.academic_records_normalized(mastery_level);

COMMENT ON TABLE stage_2a.academic_records_normalized IS 'Normalized academic records with calculated fields and standardized values';

---

-- ========================================
-- Validation Queries
-- ========================================

-- Verify transformation completeness
SELECT 
  'students' as entity,
  COUNT(*) as normalized_count,
  (SELECT COUNT(*) FROM stage_1.students WHERE student_id IS NOT NULL) as source_count,
  ROUND(100.0 * COUNT(*) / NULLIF((SELECT COUNT(*) FROM stage_1.students WHERE student_id IS NOT NULL), 0), 1) as percent_transformed
FROM stage_2a.students_normalized
UNION ALL
SELECT 'courses', COUNT(*), (SELECT COUNT(*) FROM stage_1.courses WHERE course_id IS NOT NULL), 
  ROUND(100.0 * COUNT(*) / NULLIF((SELECT COUNT(*) FROM stage_1.courses WHERE course_id IS NOT NULL), 0), 1)
FROM stage_2a.courses_normalized
UNION ALL
SELECT 'enrollment', COUNT(*), (SELECT COUNT(*) FROM stage_1.enrollment WHERE enrollment_id IS NOT NULL),
  ROUND(100.0 * COUNT(*) / NULLIF((SELECT COUNT(*) FROM stage_1.enrollment WHERE enrollment_id IS NOT NULL), 0), 1)
FROM stage_2a.enrollment_normalized
UNION ALL
SELECT 'attendance', COUNT(*), (SELECT COUNT(*) FROM stage_1.attendance WHERE attendance_id IS NOT NULL),
  ROUND(100.0 * COUNT(*) / NULLIF((SELECT COUNT(*) FROM stage_1.attendance WHERE attendance_id IS NOT NULL), 0), 1)
FROM stage_2a.attendance_normalized
UNION ALL
SELECT 'academic_records', COUNT(*), (SELECT COUNT(*) FROM stage_1.academic_records WHERE record_id IS NOT NULL),
  ROUND(100.0 * COUNT(*) / NULLIF((SELECT COUNT(*) FROM stage_1.academic_records WHERE record_id IS NOT NULL), 0), 1)
FROM stage_2a.academic_records_normalized;

-- Check for remaining NULLs in critical fields
SELECT 
  'students' as entity,
  COUNT(*) as total,
  COUNT(CASE WHEN first_name = 'UNKNOWN' THEN 1 END) as missing_names
FROM stage_2a.students_normalized
WHERE first_name = 'UNKNOWN' OR last_name = 'UNKNOWN';

---

-- ========================================
-- Export and Summary
-- ========================================

-- Summary statistics by entity
SELECT 
  'Normalized Data Summary' as report_type,
  CURRENT_TIMESTAMP as generated_at,
  JSON_BUILD_OBJECT(
    'students', (SELECT COUNT(*) FROM stage_2a.students_normalized),
    'courses', (SELECT COUNT(*) FROM stage_2a.courses_normalized),
    'enrollments', (SELECT COUNT(*) FROM stage_2a.enrollment_normalized),
    'attendance_records', (SELECT COUNT(*) FROM stage_2a.attendance_normalized),
    'academic_records', (SELECT COUNT(*) FROM stage_2a.academic_records_normalized)
  ) as record_counts;
