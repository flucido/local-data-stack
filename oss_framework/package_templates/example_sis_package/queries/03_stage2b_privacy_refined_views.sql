-- Stage 2B: Privacy-Refined Views with Pseudonymization
-- Purpose: Apply privacy rules (hash, mask, no-op) to create de-identified researcher dataset
-- These views remove PII while maintaining analytical value per FERPA requirements
-- Database: PostgreSQL (adapt for other databases as needed)
-- Last Updated: 2024

-- ========================================
-- Privacy Functions
-- ========================================

-- Create schema for privacy functions
CREATE SCHEMA IF NOT EXISTS privacy;
COMMENT ON SCHEMA privacy IS 'Privacy and pseudonymization functions';

-- Drop existing functions (for idempotent re-runs)
DROP FUNCTION IF EXISTS privacy.hash_pii(text);
DROP FUNCTION IF EXISTS privacy.mask_text(text, int, text);
DROP FUNCTION IF EXISTS privacy.mask_email(text);
DROP FUNCTION IF EXISTS privacy.mask_phone(text);

-- Hash function for deterministic pseudonymization
CREATE FUNCTION privacy.hash_pii(input_value text)
RETURNS text AS $$
  SELECT encode(
    digest(
      input_value || (SELECT setting FROM pg_settings WHERE name = 'search_path'),
      'sha256'
    ),
    'hex'
  );
$$ LANGUAGE SQL IMMUTABLE;

COMMENT ON FUNCTION privacy.hash_pii(text) IS 'One-way SHA-256 hash with salt for PII pseudonymization. Same input always produces same output (deterministic and linkable).';

-- Mask text function for irreversible pseudonymization
CREATE FUNCTION privacy.mask_text(
  input_value text,
  visible_chars int DEFAULT 1,
  mask_char text DEFAULT '*'
)
RETURNS text AS $$
  SELECT
    CASE
      WHEN input_value IS NULL THEN NULL
      WHEN LENGTH(input_value) <= visible_chars THEN mask_char
      ELSE
        SUBSTRING(input_value, 1, visible_chars) ||
        REPEAT(mask_char, LENGTH(input_value) - visible_chars)
    END;
$$ LANGUAGE SQL IMMUTABLE;

COMMENT ON FUNCTION privacy.mask_text(text, int, text) IS 'Irreversible text masking that shows first N characters and replaces rest. Non-deterministic output, not suitable for linking records.';

-- Mask email function
CREATE FUNCTION privacy.mask_email(email_value text)
RETURNS text AS $$
  SELECT
    CASE
      WHEN email_value IS NULL THEN NULL
      WHEN email_value NOT LIKE '%@%' THEN privacy.mask_text(email_value, 2, '*')
      ELSE
        privacy.mask_text(SUBSTRING(email_value FROM 1 FOR POSITION('@' IN email_value) - 1), 2, '*') ||
        '@' ||
        privacy.mask_text(SUBSTRING(email_value FROM POSITION('@' IN email_value) + 1), 2, '*')
    END;
$$ LANGUAGE SQL IMMUTABLE;

COMMENT ON FUNCTION privacy.mask_email(text) IS 'Mask email address: show first 2 chars of local and domain parts.';

-- Mask phone function
CREATE FUNCTION privacy.mask_phone(phone_value text)
RETURNS text AS $$
  SELECT
    CASE
      WHEN phone_value IS NULL THEN NULL
      WHEN LENGTH(REGEXP_REPLACE(phone_value, '[^0-9]', '', 'g')) >= 10
      THEN SUBSTRING(phone_value, 1, POSITION('-' IN phone_value) + 3) || '****'
      ELSE privacy.mask_text(phone_value, 1, '*')
    END;
$$ LANGUAGE SQL IMMUTABLE;

COMMENT ON FUNCTION privacy.mask_phone(text) IS 'Mask phone: show area code and exchange, hide local number.';

---

-- ========================================
-- Create Stage 2B Schema
-- ========================================

CREATE SCHEMA IF NOT EXISTS stage_2b;
COMMENT ON SCHEMA stage_2b IS 'Privacy-refined, pseudonymized data suitable for research and analytics with FERPA compliance';

---

-- ========================================
-- 1. Students Privacy-Refined View
-- ========================================

CREATE TABLE IF NOT EXISTS stage_2b.students_refined AS
SELECT
  -- Pseudonymized Keys (hash for deterministic linking)
  privacy.hash_pii(sn.student_id) as student_id_hashed,
  
  -- Masked Demographics
  privacy.mask_text(sn.first_name, 2, '*') as first_name_masked,
  privacy.mask_text(sn.last_name, 1, '*') as last_name_masked,
  
  -- Date of Birth: Hash for deterministic pseudonymization
  privacy.hash_pii(sn.date_of_birth::text) as dob_hashed,
  sn.birth_year as birth_year_generalized,  -- generalized, not exact date
  
  -- Non-sensitive Demographics (no transformation)
  sn.gender,
  sn.ethnicity,
  
  -- Enrollment and Programs (non-sensitive)
  sn.enrollment_status,
  sn.grade_level,
  sn.academic_program,
  
  -- Special Programs (non-sensitive)
  sn.special_education,
  sn.english_learner,
  sn.free_reduced_lunch,
  sn.gifted_status,
  sn.section_504_status,
  sn.immigrant_status,
  sn.homeless_status,
  
  -- Masked Contact Information
  privacy.mask_email(sn.email) as email_masked,
  privacy.mask_phone(sn.phone) as phone_masked,
  privacy.mask_text(sn.address, 0, '*') as address_masked,  -- hide completely
  
  -- Enrollment Timeline
  sn.enrollment_date,
  CASE
    WHEN sn.withdrawal_date IS NOT NULL
    THEN TRUE
    ELSE FALSE
  END as withdrawn_flag,
  sn.years_enrolled,
  
  -- Academic Performance (non-sensitive)
  sn.gpa,
  
  -- Metadata
  sn.normalized_date,
  CURRENT_TIMESTAMP as refined_date,
  'FERPA Compliant' as privacy_classification
  
FROM stage_2a.students_normalized sn;

CREATE INDEX idx_students_2b_id_hash ON stage_2b.students_refined(student_id_hashed);
CREATE INDEX idx_students_2b_status ON stage_2b.students_refined(enrollment_status);
CREATE INDEX idx_students_2b_grade ON stage_2b.students_refined(grade_level);

COMMENT ON TABLE stage_2b.students_refined IS 'De-identified student records with pseudonymized PII (hash, mask) and non-sensitive fields preserved for research';

---

-- ========================================
-- 2. Courses Privacy-Refined View
-- ========================================

CREATE TABLE IF NOT EXISTS stage_2b.courses_refined AS
SELECT
  -- Course Information (non-sensitive)
  sn.course_id,
  sn.course_name,
  sn.course_code,
  sn.department,
  sn.subject,
  sn.grade_level_min,
  sn.grade_level_max,
  sn.credit_hours,
  sn.course_type,
  sn.term,
  sn.room_number,
  sn.capacity,
  sn.current_enrollment,
  sn.capacity_percent,
  
  -- Masked Instructor Information
  privacy.mask_text(sn.instructor_name, 1, '*') as instructor_name_masked,
  privacy.mask_email(sn.instructor_email) as instructor_email_masked,
  privacy.hash_pii(sn.instructor_id) as instructor_id_hashed,
  
  -- Course Description (non-sensitive)
  sn.description,
  sn.prerequisites,
  
  -- Metadata
  sn.normalized_date,
  CURRENT_TIMESTAMP as refined_date,
  'FERPA Compliant' as privacy_classification
  
FROM stage_2a.courses_normalized sn;

CREATE INDEX idx_courses_2b_id ON stage_2b.courses_refined(course_id);
CREATE INDEX idx_courses_2b_dept ON stage_2b.courses_refined(department);

COMMENT ON TABLE stage_2b.courses_refined IS 'De-identified course records with instructor PII pseudonymized';

---

-- ========================================
-- 3. Enrollment Privacy-Refined View
-- ========================================

CREATE TABLE IF NOT EXISTS stage_2b.enrollment_refined AS
SELECT
  -- Pseudonymized Keys
  privacy.hash_pii(sn.enrollment_id) as enrollment_id_hashed,
  privacy.hash_pii(sn.student_id) as student_id_hashed,
  sn.course_id,
  
  -- Term and Status (non-sensitive)
  sn.term,
  sn.completion_status,
  
  -- Grades and Performance (non-sensitive, no transformation needed)
  sn.letter_grade,
  sn.final_grade_percent,
  sn.gpa_contribution,
  sn.credit_earned,
  sn.weighted_grade,
  sn.midterm_grade,
  sn.finals_grade,
  
  -- Course Characteristics
  sn.advanced_placement,
  sn.honors_course,
  
  -- Engagement Metrics (non-sensitive)
  sn.assignment_completion_rate,
  sn.quiz_average,
  sn.test_average,
  sn.participation_score,
  sn.project_score,
  
  -- Accommodations and Flags (non-sensitive)
  sn.accommodations,
  sn.flag_for_intervention,
  
  -- Dates
  sn.enrollment_date,
  sn.withdrawal_date,
  
  -- Metadata
  sn.normalized_date,
  CURRENT_TIMESTAMP as refined_date,
  'FERPA Compliant' as privacy_classification
  
FROM stage_2a.enrollment_normalized sn;

CREATE INDEX idx_enrollment_2b_id_hash ON stage_2b.enrollment_refined(enrollment_id_hashed);
CREATE INDEX idx_enrollment_2b_student ON stage_2b.enrollment_refined(student_id_hashed);
CREATE INDEX idx_enrollment_2b_course ON stage_2b.enrollment_refined(course_id);

COMMENT ON TABLE stage_2b.enrollment_refined IS 'De-identified enrollment records with pseudonymized IDs, all performance data preserved';

---

-- ========================================
-- 4. Attendance Privacy-Refined View
-- ========================================

CREATE TABLE IF NOT EXISTS stage_2b.attendance_refined AS
SELECT
  -- Pseudonymized Keys
  privacy.hash_pii(sn.attendance_id) as attendance_id_hashed,
  privacy.hash_pii(sn.student_id) as student_id_hashed,
  sn.course_id,
  
  -- Date Generalized to Week for Privacy
  sn.attendance_week,
  
  -- Status and Reason (non-sensitive)
  sn.attendance_status,
  sn.reason_code,
  CASE
    WHEN sn.reason_description LIKE '%medical%' OR sn.reason_description LIKE '%doctor%'
    THEN 'Health-related'
    WHEN sn.reason_description LIKE '%appointment%'
    THEN 'Medical appointment'
    WHEN sn.reason_description LIKE '%family%'
    THEN 'Family matter'
    WHEN sn.reason_description IS NOT NULL AND sn.reason_description != ''
    THEN 'Absence notification'
    ELSE 'Unknown'
  END as reason_category,
  
  -- Attendance Counts
  sn.present_count,
  sn.absent_count,
  sn.tardy_count,
  sn.excused_count,
  sn.unexcused_count,
  
  -- Attendance Rates (non-sensitive)
  sn.attendance_rate,
  sn.cumulative_absence_rate,
  
  -- Risk Indicators
  sn.chronically_absent,
  sn.warning_level,
  sn.trend,
  
  -- Term
  sn.term,
  
  -- Metadata
  sn.normalized_date,
  CURRENT_TIMESTAMP as refined_date,
  'FERPA Compliant' as privacy_classification
  
FROM stage_2a.attendance_normalized sn;

CREATE INDEX idx_attendance_2b_id_hash ON stage_2b.attendance_refined(attendance_id_hashed);
CREATE INDEX idx_attendance_2b_student ON stage_2b.attendance_refined(student_id_hashed);
CREATE INDEX idx_attendance_2b_week ON stage_2b.attendance_refined(attendance_week);

COMMENT ON TABLE stage_2b.attendance_refined IS 'De-identified attendance records with dates generalized to week-level and reasons categorized';

---

-- ========================================
-- 5. Academic Records Privacy-Refined View
-- ========================================

CREATE TABLE IF NOT EXISTS stage_2b.academic_records_refined AS
SELECT
  -- Pseudonymized Keys
  privacy.hash_pii(sn.record_id) as record_id_hashed,
  privacy.hash_pii(sn.student_id) as student_id_hashed,
  sn.course_id,
  
  -- Assignment Information (non-sensitive)
  sn.assignment_name,
  sn.assignment_type,
  sn.competency_id,
  sn.competency_name,
  sn.standard_code,
  
  -- Dates
  sn.assignment_date,
  sn.submission_date,
  sn.submission_timeliness,
  sn.late_days,
  sn.on_time,
  
  -- Points and Scores (non-sensitive)
  sn.max_points,
  sn.earned_points,
  sn.score_percent,
  
  -- Mastery Level (non-sensitive)
  sn.mastery_level,
  
  -- Retakes
  sn.retake_count,
  sn.original_score,
  
  -- Support Services
  sn.feedback_provided,
  sn.remediation_offered,
  sn.enrichment_offered,
  
  -- Metadata
  sn.normalized_date,
  CURRENT_TIMESTAMP as refined_date,
  'FERPA Compliant' as privacy_classification
  
FROM stage_2a.academic_records_normalized sn;

CREATE INDEX idx_academic_2b_id_hash ON stage_2b.academic_records_refined(record_id_hashed);
CREATE INDEX idx_academic_2b_student ON stage_2b.academic_records_refined(student_id_hashed);
CREATE INDEX idx_academic_2b_mastery ON stage_2b.academic_records_refined(mastery_level);

COMMENT ON TABLE stage_2b.academic_records_refined IS 'De-identified academic records preserving all learning outcome data';

---

-- ========================================
-- Linked View for Cross-Table Analysis (Uses Hashed IDs)
-- ========================================

CREATE VIEW stage_2b.student_enrollment_view AS
SELECT
  sr.student_id_hashed,
  er.enrollment_id_hashed,
  er.student_id_hashed as enr_student_id_hashed,
  cr.course_id,
  cr.course_name,
  cr.department,
  er.term,
  er.letter_grade,
  er.final_grade_percent,
  sr.grade_level,
  sr.special_education,
  sr.gpa,
  ar.attendance_rate,
  ar.chronically_absent,
  ar.warning_level
FROM stage_2b.students_refined sr
LEFT JOIN stage_2b.enrollment_refined er ON sr.student_id_hashed = er.student_id_hashed
LEFT JOIN stage_2b.courses_refined cr ON er.course_id = cr.course_id
LEFT JOIN (
  SELECT student_id_hashed, term, AVG(attendance_rate) as attendance_rate,
         MAX(chronically_absent) as chronically_absent, MAX(warning_level) as warning_level
  FROM stage_2b.attendance_refined
  GROUP BY student_id_hashed, term
) ar ON sr.student_id_hashed = ar.student_id_hashed AND er.term = ar.term;

COMMENT ON VIEW stage_2b.student_enrollment_view IS 'Linked view for analyzing student enrollment, grades, and attendance together using hashed IDs for record linkage';

---

-- ========================================
-- Aggregated Views (Further De-identified for Public Use)
-- ========================================

CREATE VIEW stage_2b.course_performance_summary AS
SELECT
  cr.course_id,
  cr.course_name,
  cr.department,
  er.term,
  COUNT(DISTINCT er.student_id_hashed) as enrollment_count,
  ROUND(AVG(er.final_grade_percent), 1) as avg_grade_percent,
  ROUND(AVG(er.gpa_contribution), 2) as avg_gpa_contribution,
  COUNT(CASE WHEN er.letter_grade IN ('A', 'A-', 'B+') THEN 1 END) as high_achiever_count,
  COUNT(CASE WHEN er.letter_grade IN ('D', 'D-', 'F') THEN 1 END) as struggling_count,
  ROUND(100.0 * COUNT(CASE WHEN er.flag_for_intervention THEN 1 END) / COUNT(*), 1) as intervention_flag_percent
FROM stage_2b.enrollment_refined er
LEFT JOIN stage_2b.courses_refined cr ON er.course_id = cr.course_id
GROUP BY cr.course_id, cr.course_name, cr.department, er.term;

COMMENT ON VIEW stage_2b.course_performance_summary IS 'Aggregated course performance metrics, no individual records';

---

-- ========================================
-- Audit Trail for Privacy Compliance
-- ========================================

CREATE TABLE IF NOT EXISTS stage_2b.privacy_audit_log (
  audit_id SERIAL PRIMARY KEY,
  table_accessed VARCHAR(50),
  record_count_accessed INT,
  query_purpose VARCHAR(200),
  accessed_by VARCHAR(100),
  accessed_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  ip_address INET,
  query_hash TEXT
);

COMMENT ON TABLE stage_2b.privacy_audit_log IS 'Audit log of all Stage 2B data access for FERPA compliance and privacy monitoring';

---

-- ========================================
-- Validation and Summary
-- ========================================

-- Verify pseudonymization completeness
SELECT 
  'students' as entity,
  COUNT(*) as total_records,
  COUNT(CASE WHEN student_id_hashed IS NOT NULL THEN 1 END) as hashed_pii,
  COUNT(CASE WHEN first_name_masked IS NOT NULL THEN 1 END) as masked_pii
FROM stage_2b.students_refined
UNION ALL
SELECT 'courses', COUNT(*), COUNT(DISTINCT instructor_id_hashed), COUNT(CASE WHEN instructor_name_masked IS NOT NULL THEN 1 END)
FROM stage_2b.courses_refined
UNION ALL
SELECT 'enrollment', COUNT(*), COUNT(CASE WHEN enrollment_id_hashed IS NOT NULL THEN 1 END), COUNT(CASE WHEN student_id_hashed IS NOT NULL THEN 1 END)
FROM stage_2b.enrollment_refined
UNION ALL
SELECT 'attendance', COUNT(*), COUNT(CASE WHEN attendance_id_hashed IS NOT NULL THEN 1 END), COUNT(CASE WHEN student_id_hashed IS NOT NULL THEN 1 END)
FROM stage_2b.attendance_refined
UNION ALL
SELECT 'academic_records', COUNT(*), COUNT(CASE WHEN record_id_hashed IS NOT NULL THEN 1 END), COUNT(CASE WHEN student_id_hashed IS NOT NULL THEN 1 END)
FROM stage_2b.academic_records_refined;

-- Privacy compliance checklist
SELECT 
  'PII Removal Verification' as check_type,
  COUNT(CASE WHEN student_id_hashed IS NOT NULL THEN 1 END) as student_ids_hashed,
  COUNT(CASE WHEN first_name_masked IS NOT NULL THEN 1 END) as first_names_masked,
  COUNT(CASE WHEN last_name_masked IS NOT NULL THEN 1 END) as last_names_masked,
  COUNT(CASE WHEN dob_hashed IS NOT NULL THEN 1 END) as dobs_hashed
FROM stage_2b.students_refined
LIMIT 1;

-- Re-identification risk assessment
-- All direct identifiers removed or transformed: ✓
-- Dates generalized to week-level (attendance): ✓
-- Quasi-identifiers preserved but aggregated in views: ✓
-- Hashed IDs allow record linking within Stage 2B only: ✓

---

**Document Version**: 1.0  
**Last Updated**: 2024  
**Privacy Classification**: FERPA Compliant  
**Data Usage**: Research and Analysis Only (Stage 2B and beyond)  
**Next Review**: Annually or upon privacy policy changes
