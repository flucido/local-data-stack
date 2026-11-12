-- DuckDB Performance Optimization - Indexes and Query Tuning
--
-- Usage:
--   duckdb oss_framework/data/analytics.duckdb < scripts/performance/duckdb_indexes.sql

-- ================================================================================
-- CORE DIMENSION TABLES
-- ================================================================================

CREATE INDEX IF NOT EXISTS idx_students_school_grade
ON main_core.dim_students (school_id, grade_level);

CREATE INDEX IF NOT EXISTS idx_students_demographics
ON main_core.dim_students (ethnicity, free_reduced_lunch_flag, ell_status);

CREATE INDEX IF NOT EXISTS idx_schools_cds
ON main_core.dim_schools (cds_code);

-- ================================================================================
-- FACT TABLES
-- ================================================================================

CREATE INDEX IF NOT EXISTS idx_attendance_student_year
ON main_core.fact_attendance (student_id_hash, academic_year);

CREATE INDEX IF NOT EXISTS idx_attendance_daily_school_grade
ON main_core.fact_attendance_daily (school_id, grade_level, academic_year);

CREATE INDEX IF NOT EXISTS idx_academic_records_student_term
ON main_core.fact_academic_records (student_id_hash, term, school_year);

CREATE INDEX IF NOT EXISTS idx_academic_records_course
ON main_core.fact_academic_records (course_id);

CREATE INDEX IF NOT EXISTS idx_academic_records_teacher
ON main_core.fact_academic_records (teacher_id_hash);

CREATE INDEX IF NOT EXISTS idx_academic_records_section
ON main_core.fact_academic_records (section_id);

CREATE INDEX IF NOT EXISTS idx_discipline_student_date
ON main_core.fact_discipline (student_id_hash, incident_date);

CREATE INDEX IF NOT EXISTS idx_discipline_type
ON main_core.fact_discipline (incident_type);

CREATE INDEX IF NOT EXISTS idx_enrollment_student
ON main_core.fact_enrollment (student_id_hash);

CREATE INDEX IF NOT EXISTS idx_enrollment_school_year
ON main_core.fact_enrollment (school_id, school_year);

-- ================================================================================
-- FEATURE & SCORING TABLES
-- ================================================================================

CREATE INDEX IF NOT EXISTS idx_chronic_features_student
ON main_features.fct_chronic_absence_features (student_id_hash);

CREATE INDEX IF NOT EXISTS idx_academic_features_student
ON main_features.fct_academic_features (student_id_hash, academic_year);

CREATE INDEX IF NOT EXISTS idx_chronic_risk_score
ON main_scoring.score_chronic_absence_risk (risk_score DESC);

CREATE INDEX IF NOT EXISTS idx_chronic_risk_student
ON main_scoring.score_chronic_absence_risk (student_id_hash);

CREATE INDEX IF NOT EXISTS idx_academic_risk_score
ON main_scoring.score_academic_risk (risk_score DESC);

-- ================================================================================
-- MAINTENANCE QUERIES
-- ================================================================================

SELECT
    schema_name,
    table_name,
    index_name,
    is_unique,
    column_names
FROM duckdb_indexes()
WHERE schema_name LIKE 'main_%'
ORDER BY schema_name, table_name, index_name;
