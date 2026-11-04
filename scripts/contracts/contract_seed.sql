-- Contract-test seed schema.
--
-- The dashboard contract queries in contract_query_manifest.json only validate
-- that each dashboard query compiles and executes against the mart schema; they
-- do not assert values. analytics.duckdb is produced by the dbt run and is
-- gitignored, so a clean CI checkout has no database to query. This script
-- creates empty fixtures for the five marts the manifest references so the
-- contract check runs on a clean clone instead of failing on a missing file.
--
-- Column types mirror the real marts in oss_framework/dbt/models/marts/, so a
-- column rename or drop in dbt still breaks these queries and fails the check.
-- Re-seed a real database with: dbt run --select marts (see oss_framework/dbt).

CREATE SCHEMA IF NOT EXISTS main_analytics;

CREATE OR REPLACE TABLE main_analytics.v_chronic_absenteeism_risk (
    student_key VARCHAR,
    grade_level INTEGER,
    school_id VARCHAR,
    academic_year VARCHAR,
    gender VARCHAR,
    race_ethnicity VARCHAR,
    english_learner BOOLEAN,
    special_education BOOLEAN,
    economically_disadvantaged BOOLEAN,
    homeless_flag BOOLEAN,
    attendance_rate_30d DOUBLE,
    unexcused_absence_rate_30d DOUBLE,
    discipline_incidents_30d HUGEINT,
    absence_discipline_correlation_score DOUBLE,
    attendance_rate_90d DOUBLE,
    attendance_trend_90d VARCHAR,
    chronic_absence_flag INTEGER,
    chronic_absenteeism_risk_score DOUBLE,
    snapshot_date DATE,
    risk_level VARCHAR,
    _loaded_at TIMESTAMPTZ
);

CREATE OR REPLACE TABLE main_analytics.v_equity_outcomes_by_demographics (
    race_ethnicity VARCHAR,
    english_learner BOOLEAN,
    special_education BOOLEAN,
    economically_disadvantaged BOOLEAN,
    cohort_size BIGINT,
    pct_good_attendance DOUBLE,
    pct_no_discipline DOUBLE,
    avg_gpa DOUBLE,
    pct_gpa_2_5_plus DOUBLE,
    pct_below_c DOUBLE,
    _loaded_at TIMESTAMPTZ
);

CREATE OR REPLACE TABLE main_analytics.v_class_section_comparison (
    course_id VARCHAR,
    school_id VARCHAR,
    grade_level INTEGER,
    enrollment_count BIGINT,
    avg_grade_numeric DOUBLE,
    pct_passed DOUBLE,
    pct_a_b_grades DOUBLE,
    course_avg_grade DOUBLE,
    grade_diff_from_course_avg DOUBLE,
    pct_passed_ell DOUBLE,
    pct_passed_sped DOUBLE,
    pct_passed_frl DOUBLE,
    pass_rate_rank BIGINT,
    grade_rank BIGINT,
    effectiveness_rating VARCHAR,
    term VARCHAR,
    _loaded_at TIMESTAMPTZ
);

CREATE OR REPLACE TABLE main_analytics.v_performance_correlations (
    correlation_pair VARCHAR,
    correlation_coefficient DOUBLE,
    expected_direction VARCHAR,
    data_points BIGINT,
    strength VARCHAR,
    _loaded_at TIMESTAMPTZ
);

CREATE OR REPLACE TABLE main_analytics.v_wellbeing_risk_profiles (
    student_key VARCHAR,
    grade_level INTEGER,
    school_id VARCHAR,
    academic_year VARCHAR,
    attendance_risk_score DOUBLE,
    discipline_risk_score DECIMAL(20, 1),
    academic_risk_score INTEGER,
    high_risk_domain_count INTEGER,
    wellbeing_risk_score DOUBLE,
    wellbeing_risk_level VARCHAR,
    primary_concern VARCHAR,
    snapshot_date DATE,
    _loaded_at TIMESTAMPTZ
);
