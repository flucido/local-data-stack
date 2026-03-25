-- Stage 1: Raw Data Validation Queries
-- Purpose: Validate data quality and integrity in the landing zone
-- These queries identify issues before transformation to Stage 2A
-- Database: PostgreSQL (adapt for other databases as needed)
-- Last Updated: 2024

-- ========================================
-- 1. Table Structure Validation
-- ========================================

-- Verify all required tables exist
SELECT table_name, table_type
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN ('students', 'courses', 'enrollment', 'attendance', 'academic_records')
ORDER BY table_name;

-- Verify all required columns exist
SELECT 
  t.table_name,
  c.column_name,
  c.data_type,
  c.is_nullable
FROM information_schema.columns c
JOIN information_schema.tables t ON c.table_schema = t.table_schema AND c.table_name = t.table_name
WHERE c.table_schema = 'public'
  AND t.table_name IN ('students', 'courses', 'enrollment', 'attendance', 'academic_records')
ORDER BY t.table_name, c.ordinal_position;

---

-- ========================================
-- 2. Record Count and Distribution
-- ========================================

-- Summary of all table sizes
SELECT 
  'students' as table_name,
  COUNT(*) as total_records,
  COUNT(DISTINCT student_id) as unique_students
FROM students
UNION ALL
SELECT 
  'courses',
  COUNT(*),
  COUNT(DISTINCT course_id)
FROM courses
UNION ALL
SELECT 
  'enrollment',
  COUNT(*),
  COUNT(DISTINCT student_id)
FROM enrollment
UNION ALL
SELECT 
  'attendance',
  COUNT(*),
  COUNT(DISTINCT student_id)
FROM attendance
UNION ALL
SELECT 
  'academic_records',
  COUNT(*),
  COUNT(DISTINCT student_id)
FROM academic_records;

-- Distribution by enrollment status
SELECT 
  enrollment_status,
  COUNT(*) as count,
  ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM students), 2) as percent
FROM students
GROUP BY enrollment_status
ORDER BY count DESC;

-- Distribution by grade level
SELECT 
  grade_level,
  COUNT(*) as student_count,
  COUNT(DISTINCT student_id) as unique_count
FROM students
GROUP BY grade_level
ORDER BY grade_level;

---

-- ========================================
-- 3. NULL Value Detection
-- ========================================

-- Find NULL values in critical fields
SELECT 
  'students' as table_name,
  COUNT(*) as total_rows,
  COUNT(CASE WHEN student_id IS NULL THEN 1 END) as student_id_nulls,
  COUNT(CASE WHEN first_name IS NULL THEN 1 END) as first_name_nulls,
  COUNT(CASE WHEN last_name IS NULL THEN 1 END) as last_name_nulls,
  COUNT(CASE WHEN date_of_birth IS NULL THEN 1 END) as dob_nulls,
  COUNT(CASE WHEN enrollment_status IS NULL THEN 1 END) as status_nulls
FROM students
UNION ALL
SELECT 
  'courses',
  COUNT(*),
  COUNT(CASE WHEN course_id IS NULL THEN 1 END),
  COUNT(CASE WHEN course_name IS NULL THEN 1 END),
  0, 0, 0
FROM courses
UNION ALL
SELECT 
  'enrollment',
  COUNT(*),
  COUNT(CASE WHEN enrollment_id IS NULL THEN 1 END),
  COUNT(CASE WHEN student_id IS NULL THEN 1 END),
  COUNT(CASE WHEN course_id IS NULL THEN 1 END),
  0, 0
FROM enrollment
UNION ALL
SELECT 
  'attendance',
  COUNT(*),
  COUNT(CASE WHEN attendance_id IS NULL THEN 1 END),
  COUNT(CASE WHEN student_id IS NULL THEN 1 END),
  COUNT(CASE WHEN attendance_date IS NULL THEN 1 END),
  0, 0
FROM attendance
UNION ALL
SELECT 
  'academic_records',
  COUNT(*),
  COUNT(CASE WHEN record_id IS NULL THEN 1 END),
  COUNT(CASE WHEN student_id IS NULL THEN 1 END),
  COUNT(CASE WHEN course_id IS NULL THEN 1 END),
  0, 0
FROM academic_records;

---

-- ========================================
-- 4. Uniqueness Constraints
-- ========================================

-- Check for duplicate student IDs
SELECT 
  student_id,
  COUNT(*) as duplicate_count
FROM students
GROUP BY student_id
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC;

-- Check for duplicate course IDs
SELECT 
  course_id,
  COUNT(*) as duplicate_count
FROM courses
GROUP BY course_id
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC;

-- Check for duplicate enrollments (same student + course + term)
SELECT 
  student_id,
  course_id,
  term,
  COUNT(*) as duplicate_count
FROM enrollment
GROUP BY student_id, course_id, term
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC;

---

-- ========================================
-- 5. Data Type and Format Validation
-- ========================================

-- Find invalid dates
SELECT 
  student_id,
  date_of_birth,
  EXTRACT(YEAR FROM date_of_birth) as birth_year
FROM students
WHERE date_of_birth IS NOT NULL
  AND (date_of_birth > CURRENT_DATE
    OR date_of_birth < '1900-01-01'
    OR EXTRACT(YEAR FROM date_of_birth) NOT BETWEEN 1900 AND EXTRACT(YEAR FROM CURRENT_DATE))
ORDER BY date_of_birth DESC;

-- Find invalid enrollment dates (future dates)
SELECT 
  enrollment_id,
  student_id,
  enrollment_date,
  withdrawal_date
FROM enrollment
WHERE enrollment_date > CURRENT_DATE
   OR (withdrawal_date IS NOT NULL AND withdrawal_date > CURRENT_DATE)
ORDER BY enrollment_date DESC;

-- Find invalid GPA values
SELECT 
  gpa,
  COUNT(*) as count
FROM students
WHERE gpa IS NOT NULL
  AND (gpa < 0.0 OR gpa > 4.0)
GROUP BY gpa
ORDER BY count DESC;

-- Find invalid grade values
SELECT DISTINCT grade
FROM enrollment
WHERE grade NOT IN ('A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D+', 'D', 'D-', 'F', 'I', 'W', 'P', 'NP')
  AND grade IS NOT NULL
ORDER BY grade;

---

-- ========================================
-- 6. Referential Integrity
-- ========================================

-- Check for enrollment records with non-existent students
SELECT 
  COUNT(*) as orphaned_enrollment_count
FROM enrollment e
WHERE NOT EXISTS (
  SELECT 1 FROM students s WHERE s.student_id = e.student_id
);

-- Check for enrollment records with non-existent courses
SELECT 
  COUNT(*) as orphaned_enrollment_count
FROM enrollment e
WHERE NOT EXISTS (
  SELECT 1 FROM courses c WHERE c.course_id = e.course_id
);

-- Check for attendance records with non-existent students
SELECT 
  COUNT(*) as orphaned_attendance_count
FROM attendance a
WHERE NOT EXISTS (
  SELECT 1 FROM students s WHERE s.student_id = a.student_id
);

-- Check for academic_records with non-existent students
SELECT 
  COUNT(*) as orphaned_academic_records_count
FROM academic_records ar
WHERE NOT EXISTS (
  SELECT 1 FROM students s WHERE s.student_id = ar.student_id
);

---

-- ========================================
-- 7. Enrollment Status Consistency
-- ========================================

-- Students with grade_level inconsistencies
SELECT 
  student_id,
  first_name,
  last_name,
  grade_level,
  enrollment_status
FROM students
WHERE grade_level NOT BETWEEN 0 AND 12
  OR enrollment_status NOT IN ('Active', 'Graduated', 'Withdrawn', 'Transferred', 'On Leave')
ORDER BY student_id;

-- Withdrawn students with future withdrawal dates
SELECT 
  student_id,
  enrollment_status,
  withdrawal_date,
  CURRENT_DATE - withdrawal_date as days_since_withdrawal
FROM students
WHERE enrollment_status = 'Withdrawn'
  AND (withdrawal_date IS NULL OR withdrawal_date > CURRENT_DATE)
ORDER BY withdrawal_date DESC;

-- Active students with very old enrollment dates (potential status error)
SELECT 
  student_id,
  enrollment_date,
  EXTRACT(YEAR FROM AGE(CURRENT_DATE, enrollment_date)) as years_enrolled
FROM students
WHERE enrollment_status = 'Active'
  AND enrollment_date < CURRENT_DATE - INTERVAL '20 years'
ORDER BY enrollment_date;

---

-- ========================================
-- 8. Date Range Validation
-- ========================================

-- Attendance dates outside expected range
SELECT 
  attendance_date,
  COUNT(*) as record_count
FROM attendance
WHERE attendance_date > CURRENT_DATE
   OR attendance_date < CURRENT_DATE - INTERVAL '4 years'
GROUP BY attendance_date
ORDER BY attendance_date DESC;

-- Academic record dates inconsistencies
SELECT 
  ar.record_id,
  ar.assignment_date,
  ar.submission_date,
  CASE WHEN ar.submission_date < ar.assignment_date THEN 'ERROR: submitted before assigned'
       WHEN ar.submission_date > ar.assignment_date + INTERVAL '1 year' THEN 'WARNING: very late submission'
       ELSE 'OK' END as date_issue
FROM academic_records ar
WHERE ar.submission_date < ar.assignment_date
   OR ar.submission_date > ar.assignment_date + INTERVAL '1 year'
ORDER BY ar.record_id;

---

-- ========================================
-- 9. Numeric Ranges and Outliers
-- ========================================

-- Attendance rate outliers (should be 0.0-1.0)
SELECT 
  student_id,
  attendance_rate,
  COUNT(*) as record_count
FROM attendance
WHERE attendance_rate IS NOT NULL
  AND (attendance_rate < 0.0 OR attendance_rate > 1.0)
GROUP BY student_id, attendance_rate
ORDER BY attendance_rate DESC;

-- Grade percentage outliers
SELECT 
  enrollment_id,
  student_id,
  course_id,
  final_grade_percent
FROM enrollment
WHERE final_grade_percent IS NOT NULL
  AND (final_grade_percent < 0 OR final_grade_percent > 100)
ORDER BY final_grade_percent DESC;

-- Credit hours validation
SELECT 
  course_id,
  credit_hours,
  COUNT(DISTINCT enrollment_id) as enrollment_count
FROM enrollment e
JOIN courses c ON e.course_id = c.course_id
WHERE c.credit_hours IS NOT NULL
  AND (c.credit_hours < 0 OR c.credit_hours > 10)
GROUP BY course_id, credit_hours;

---

-- ========================================
-- 10. Time Series Gaps
-- ========================================

-- Check for missing attendance records (gaps in daily attendance)
WITH attendance_dates AS (
  SELECT DISTINCT attendance_date
  FROM attendance
  WHERE attendance_date >= CURRENT_DATE - INTERVAL '30 days'
  ORDER BY attendance_date
)
SELECT 
  a1.attendance_date,
  a2.attendance_date,
  (a2.attendance_date - a1.attendance_date) as gap_days
FROM attendance_dates a1
JOIN attendance_dates a2 ON a2.attendance_date = a1.attendance_date + INTERVAL '1 day'
WHERE (a2.attendance_date - a1.attendance_date) > INTERVAL '1 day'
LIMIT 20;

---

-- ========================================
-- 11. Privacy and Sensitivity
-- ========================================

-- Check for empty/missing sensitive fields
SELECT 
  COUNT(*) as total,
  COUNT(CASE WHEN email IS NULL THEN 1 END) as email_nulls,
  COUNT(CASE WHEN phone IS NULL THEN 1 END) as phone_nulls,
  COUNT(CASE WHEN ssn IS NULL THEN 1 END) as ssn_nulls,
  COUNT(CASE WHEN address IS NULL THEN 1 END) as address_nulls
FROM students;

-- Check for PII patterns that might need masking
SELECT 
  COUNT(*) as total,
  COUNT(CASE WHEN email LIKE '%@%.%' THEN 1 END) as valid_emails,
  COUNT(CASE WHEN phone LIKE '+1-%' OR phone LIKE '(%' THEN 1 END) as valid_phones,
  COUNT(CASE WHEN ssn ~ '^\d{3}-\d{2}-\d{4}$' THEN 1 END) as valid_ssns
FROM students
WHERE email IS NOT NULL OR phone IS NOT NULL OR ssn IS NOT NULL;

---

-- ========================================
-- 12. Summary Quality Report
-- ========================================

-- Overall data quality scorecard
SELECT 
  'Students' as entity,
  (SELECT COUNT(*) FROM students) as total_records,
  (SELECT COUNT(*) FROM students WHERE student_id IS NULL) as critical_errors,
  (SELECT COUNT(*) FROM students WHERE first_name IS NULL OR last_name IS NULL) as data_gaps,
  (SELECT COUNT(DISTINCT student_id) FROM students) as unique_ids,
  CASE 
    WHEN (SELECT COUNT(*) FROM students) = 0 THEN 'NO DATA'
    WHEN (SELECT COUNT(*) FROM students WHERE student_id IS NULL) > 0 THEN 'CRITICAL'
    WHEN (SELECT COUNT(*) FROM students WHERE first_name IS NULL OR last_name IS NULL) > (SELECT COUNT(*) FROM students) * 0.05 THEN 'WARNING'
    ELSE 'PASS'
  END as overall_status
UNION ALL
SELECT 
  'Enrollment',
  (SELECT COUNT(*) FROM enrollment),
  (SELECT COUNT(*) FROM enrollment WHERE enrollment_id IS NULL),
  (SELECT COUNT(*) FROM enrollment WHERE student_id IS NULL OR course_id IS NULL),
  (SELECT COUNT(DISTINCT student_id) FROM enrollment),
  CASE 
    WHEN (SELECT COUNT(*) FROM enrollment) = 0 THEN 'NO DATA'
    WHEN (SELECT COUNT(*) FROM enrollment WHERE enrollment_id IS NULL OR student_id IS NULL) > 0 THEN 'CRITICAL'
    ELSE 'PASS'
  END
UNION ALL
SELECT 
  'Attendance',
  (SELECT COUNT(*) FROM attendance),
  (SELECT COUNT(*) FROM attendance WHERE student_id IS NULL),
  (SELECT COUNT(*) FROM attendance WHERE attendance_date IS NULL),
  (SELECT COUNT(DISTINCT student_id) FROM attendance),
  CASE 
    WHEN (SELECT COUNT(*) FROM attendance) = 0 THEN 'NO DATA'
    WHEN (SELECT COUNT(*) FROM attendance WHERE student_id IS NULL) > 0 THEN 'CRITICAL'
    ELSE 'PASS'
  END
ORDER BY entity;

---

-- ========================================
-- Export Summary
-- ========================================
-- Run this query to get a JSON export of validation results
-- Useful for automated monitoring and alerting

SELECT JSON_BUILD_OBJECT(
  'export_date', CURRENT_TIMESTAMP,
  'tables', JSON_BUILD_OBJECT(
    'students', (SELECT COUNT(*) FROM students),
    'courses', (SELECT COUNT(*) FROM courses),
    'enrollment', (SELECT COUNT(*) FROM enrollment),
    'attendance', (SELECT COUNT(*) FROM attendance),
    'academic_records', (SELECT COUNT(*) FROM academic_records)
  ),
  'issues', JSON_BUILD_OBJECT(
    'null_student_ids', (SELECT COUNT(*) FROM students WHERE student_id IS NULL),
    'duplicate_students', (SELECT COUNT(*) FROM (SELECT COUNT(*) FROM students GROUP BY student_id HAVING COUNT(*) > 1) t),
    'orphaned_enrollments', (SELECT COUNT(*) FROM enrollment WHERE NOT EXISTS (SELECT 1 FROM students WHERE student_id = enrollment.student_id)),
    'future_dates', (SELECT COUNT(*) FROM enrollment WHERE enrollment_date > CURRENT_DATE)
  )
) as validation_report;
