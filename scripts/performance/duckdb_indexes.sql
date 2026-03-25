-- DuckDB Performance Optimization - Indexes and Query Tuning
--
-- This file contains index definitions and query optimization hints for the
-- local-data-stack analytics platform.
--
-- DuckDB automatically creates indexes on primary keys, but additional indexes
-- can significantly improve query performance for:
-- 1. Large fact tables (attendance, grades, discipline)
-- 2. Frequently filtered columns (student_id, school_id, date ranges)
-- 3. Join columns in analytics queries
--
-- Usage:
--   duckdb oss_framework/data/oea.duckdb < scripts/performance/duckdb_indexes.sql
--

-- ================================================================================
-- CORE DIMENSION TABLES
-- ================================================================================

-- Students dimension - Already has PK on student_id
-- Additional index on frequently filtered columns
CREATE INDEX IF NOT EXISTS idx_students_school_grade 
ON main_core.dim_students (school_id, grade_level);

CREATE INDEX IF NOT EXISTS idx_students_demographics
ON main_core.dim_students (ethnicity, free_reduced_lunch_flag, ell_status);

-- Schools dimension - Add index on CDS code for external joins
CREATE INDEX IF NOT EXISTS idx_schools_cds
ON main_core.dim_schools (cds_code);

-- Dates dimension - Add indexes on commonly filtered date attributes
CREATE INDEX IF NOT EXISTS idx_dates_school_year
ON main_core.dim_dates (school_year);

CREATE INDEX IF NOT EXISTS idx_dates_month_year
ON main_core.dim_dates (year, month);

-- ================================================================================
-- FACT TABLES
-- ================================================================================

-- Fact: Attendance Daily
-- High-volume table (45,000+ rows with test data, millions in production)
-- Optimize for student lookups, date ranges, and school filtering
CREATE INDEX IF NOT EXISTS idx_attendance_student_date
ON main_core.fact_attendance_daily (student_id, attendance_date);

CREATE INDEX IF NOT EXISTS idx_attendance_school_date
ON main_core.fact_attendance_daily (school_id, attendance_date);

CREATE INDEX IF NOT EXISTS idx_attendance_date_range
ON main_core.fact_attendance_daily (attendance_date);

-- Composite index for common filter patterns
CREATE INDEX IF NOT EXISTS idx_attendance_student_school
ON main_core.fact_attendance_daily (student_id, school_id, attendance_date);

-- Fact: Grades
-- Very high-volume table (200,000+ rows with test data)
-- Optimize for student, course, and term queries
CREATE INDEX IF NOT EXISTS idx_grades_student_term
ON main_core.fact_grades (student_id, term_id);

CREATE INDEX IF NOT EXISTS idx_grades_course
ON main_core.fact_grades (course_id);

CREATE INDEX IF NOT EXISTS idx_grades_teacher
ON main_core.fact_grades (teacher_id);

CREATE INDEX IF NOT EXISTS idx_grades_section
ON main_core.fact_grades (section_id);

-- Fact: Discipline Incidents
-- Medium-volume table (2,000+ rows with test data)
-- Optimize for student and incident date lookups
CREATE INDEX IF NOT EXISTS idx_discipline_student_date
ON main_core.fact_discipline_incidents (student_id, incident_date);

CREATE INDEX IF NOT EXISTS idx_discipline_type
ON main_core.fact_discipline_incidents (incident_type);

-- Fact: Enrollment
-- Medium-volume table (1,700+ rows with test data)
-- Optimize for student and school lookups
CREATE INDEX IF NOT EXISTS idx_enrollment_student
ON main_core.fact_enrollment (student_id);

CREATE INDEX IF NOT EXISTS idx_enrollment_school_year
ON main_core.fact_enrollment (school_id, school_year);

-- ================================================================================
-- FEATURE TABLES
-- ================================================================================

-- Feature: Student Attendance Windows
-- Aggregated attendance metrics by time window
CREATE INDEX IF NOT EXISTS idx_attendance_windows_student
ON main_features.feat_student_attendance_windows (student_id);

CREATE INDEX IF NOT EXISTS idx_attendance_windows_school
ON main_features.feat_student_attendance_windows (school_id);

-- Feature: Academic Performance Metrics
CREATE INDEX IF NOT EXISTS idx_academic_performance_student
ON main_features.feat_academic_performance (student_id);

CREATE INDEX IF NOT EXISTS idx_academic_performance_term
ON main_features.feat_academic_performance (term_id);

-- ================================================================================
-- SCORING TABLES
-- ================================================================================

-- Scoring: Chronic Absenteeism Risk
-- Optimize for dashboard queries (sort by risk score)
CREATE INDEX IF NOT EXISTS idx_chronic_risk_score
ON main_scoring.score_chronic_absenteeism_risk (risk_score DESC);

CREATE INDEX IF NOT EXISTS idx_chronic_risk_student
ON main_scoring.score_chronic_absenteeism_risk (student_id);

-- Scoring: Academic Risk
CREATE INDEX IF NOT EXISTS idx_academic_risk_score
ON main_scoring.score_academic_risk (risk_score DESC);

-- Scoring: Wellbeing Risk
CREATE INDEX IF NOT EXISTS idx_wellbeing_risk_score
ON main_scoring.score_wellbeing_risk (overall_risk_score DESC);

CREATE INDEX IF NOT EXISTS idx_wellbeing_risk_student
ON main_scoring.score_wellbeing_risk (student_id);

-- ================================================================================
-- QUERY OPTIMIZATION HINTS
-- ================================================================================

-- DuckDB-specific optimizations (not standard SQL, for reference only):
--
-- 1. Partition large Parquet files by date:
--    COPY fact_attendance_daily TO 'data/attendance.parquet'
--    (FORMAT PARQUET, PARTITION_BY (year, month), COMPRESSION ZSTD);
--
-- 2. Use sorted data for better compression:
--    CREATE TABLE fact_attendance_sorted AS
--    SELECT * FROM fact_attendance_daily ORDER BY student_id, attendance_date;
--
-- 3. Enable query profiling:
--    PRAGMA enable_profiling;
--    PRAGMA profiling_output = 'query_profile.json';
--
-- 4. Check query plan:
--    EXPLAIN SELECT * FROM fact_attendance_daily WHERE student_id = 'STU0001';
--
-- 5. Statistics for query optimizer:
--    ANALYZE main_core.fact_attendance_daily;

-- ================================================================================
-- MAINTENANCE QUERIES
-- ================================================================================

-- View all indexes
SELECT 
    schema_name,
    table_name,
    index_name,
    is_unique,
    column_names
FROM duckdb_indexes()
WHERE schema_name LIKE 'main_%'
ORDER BY schema_name, table_name, index_name;

-- Check table sizes (row counts and storage)
SELECT 
    table_schema,
    table_name,
    estimated_size AS rows,
    column_count,
    index_count
FROM duckdb_tables()
WHERE table_schema LIKE 'main_%'
ORDER BY estimated_size DESC;

-- Analyze query performance (run after enabling profiling)
-- EXPLAIN ANALYZE <your query here>;

-- ================================================================================
-- PERFORMANCE TESTING QUERIES
-- ================================================================================

-- Test 1: Student attendance lookup (should use idx_attendance_student_date)
-- EXPLAIN SELECT * 
-- FROM main_core.fact_attendance_daily 
-- WHERE student_id = 'STU0001' 
--   AND attendance_date BETWEEN '2025-01-01' AND '2025-12-31';

-- Test 2: School attendance summary (should use idx_attendance_school_date)
-- EXPLAIN SELECT 
--     school_id,
--     COUNT(*) as total_records,
--     AVG(CASE WHEN present_flag THEN 1.0 ELSE 0.0 END) as attendance_rate
-- FROM main_core.fact_attendance_daily
-- WHERE attendance_date >= '2025-01-01'
-- GROUP BY school_id;

-- Test 3: Chronic absenteeism dashboard (should use idx_chronic_risk_score)
-- EXPLAIN SELECT *
-- FROM main_scoring.score_chronic_absenteeism_risk
-- WHERE risk_score > 50
-- ORDER BY risk_score DESC
-- LIMIT 100;

-- Test 4: Student wellbeing profile (should use idx_wellbeing_risk_student)
-- EXPLAIN SELECT 
--     w.*,
--     s.first_name,
--     s.last_name
-- FROM main_scoring.score_wellbeing_risk w
-- JOIN main_core.dim_students s ON w.student_id = s.student_id
-- WHERE w.overall_risk_score > 60
-- ORDER BY w.overall_risk_score DESC;

-- ================================================================================
-- INCREMENTAL MODEL OPTIMIZATION
-- ================================================================================

-- For future incremental dbt models, consider:
--
-- 1. fact_attendance_daily.sql - Add incremental materialization:
--    {{ config(
--        materialized='incremental',
--        unique_key='attendance_id',
--        incremental_strategy='delete+insert',
--        partition_by={'field': 'attendance_date', 'data_type': 'date', 'granularity': 'month'}
--    ) }}
--
-- 2. Add indexes on partition columns:
--    CREATE INDEX idx_attendance_partition ON fact_attendance_daily(attendance_date);
--
-- 3. Use merge strategy for upserts:
--    incremental_strategy='merge'

-- ================================================================================
-- CLEANUP
-- ================================================================================

-- Drop unused indexes (example, commented out for safety)
-- DROP INDEX IF EXISTS idx_old_index;

-- Rebuild fragmented indexes (DuckDB handles this automatically)
-- ANALYZE;  -- Update statistics after bulk inserts
