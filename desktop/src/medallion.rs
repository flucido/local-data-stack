use anyhow::{anyhow, Result};
use arrow::record_batch::RecordBatch;
use arrow::util::display::ArrayFormatter;
use arrow_ipc::writer::StreamWriter;
use duckdb::Connection as DuckConnection;
use regex::Regex;
use rusqlite::{params, Connection as SqliteConnection};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::{HashMap, HashSet};
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex, OnceLock, RwLock};
use uuid::Uuid;

const MAX_RESULT_ROWS: usize = 1000;

const FORBIDDEN_TOKENS: &[&str] = &[
    "drop", "delete", "insert", "update", "alter", "truncate", "create", "attach", "detach",
    "pragma",
];

const FORBIDDEN_FUNCTIONS: &[&str] = &[
    "read_parquet",
    "parquet_scan",
    "query_parquet",
    "read_csv",
    "read_csv_auto",
    "csv_scan",
    "query_csv",
    "from_csv",
    "sniff_csv",
    "read_text",
    "read_blob",
    "read_json",
    "read_json_auto",
    "read_json_objects",
    "read_ndjson",
    "json_scan",
    "query_json",
    "read_xlsx",
    "from_excel",
    "glob",
    "iceberg_scan",
    "delta_scan",
];

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct ColumnSummary {
    pub name: String,
    #[serde(rename = "type")]
    pub data_type: String,
    pub distinct_count: usize,
    pub null_count: usize,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub min: Option<Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub max: Option<Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub sample_values: Option<Vec<Value>>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct DuckDBResultSummary {
    pub status: String,
    pub query_id: String,
    pub row_count: usize,
    pub columns: Vec<ColumnSummary>,
    pub sample_rows: Vec<Vec<Value>>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct DuckDBExecutionError {
    pub status: String,
    pub error_type: String,
    pub message: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FilterSpec {
    pub column: String,
    pub control_type: String,
    #[serde(default)]
    pub min: Option<Value>,
    #[serde(default)]
    pub max: Option<Value>,
    #[serde(default)]
    pub values: Option<Vec<Value>>,
    #[serde(default)]
    pub value: Option<Value>,
    #[serde(default)]
    pub query: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BronzeAttendanceInput {
    pub student_id_hash: String,
    pub school_id: String,
    pub academic_year: String,
    pub days_enrolled: i64,
    pub days_present: i64,
    pub days_absent: i64,
    pub unexcused_absences: i64,
    pub attendance_rate: f64,
}

#[derive(Debug, Clone)]
pub struct CachedQueryEntry {
    pub query_id: String,
    pub base_sql: String,
    pub arrow_ipc_bytes: Vec<u8>,
    pub summary: DuckDBResultSummary,
}

#[derive(Default, Clone)]
pub struct ArrowCache {
    inner: Arc<RwLock<HashMap<String, CachedQueryEntry>>>,
}

impl ArrowCache {
    pub fn new() -> Self {
        Self {
            inner: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    pub fn insert(&self, entry: CachedQueryEntry) {
        if let Ok(mut guard) = self.inner.write() {
            guard.insert(entry.query_id.clone(), entry);
        }
    }

    pub fn get(&self, query_id: &str) -> Option<CachedQueryEntry> {
        self.inner
            .read()
            .ok()
            .and_then(|g| g.get(query_id).cloned())
    }
}

pub struct MedallionEngine {
    bronze_path: PathBuf,
    duck_conn: Mutex<DuckConnection>,
    pub arrow_cache: ArrowCache,
}

impl MedallionEngine {
    pub fn new(bronze_path: impl AsRef<Path>, edu_warehouse_path: Option<&Path>) -> Result<Self> {
        let bronze_path = bronze_path.as_ref().to_path_buf();
        Self::init_bronze_sqlite(&bronze_path)?;

        let duck_conn = DuckConnection::open_in_memory()?;
        let engine = Self {
            bronze_path,
            duck_conn: Mutex::new(duck_conn),
            arrow_cache: ArrowCache::new(),
        };

        engine.sync_bronze_to_silver_and_gold()?;
        if let Some(edu_path) = edu_warehouse_path {
            if edu_path.exists() {
                let _ = engine.attach_education_warehouse(edu_path);
            }
        }
        // Must come after the ATTACH above: attaching reads the warehouse file
        // from disk, which ``enable_external_access = false`` forbids. Doing it
        // last also means the engine never runs a query with disk/network
        // access available.
        engine.lock_down_duckdb()?;
        Ok(engine)
    }

    /// Close off DuckDB's external surface, then freeze the configuration.
    ///
    /// ``FORBIDDEN_TOKENS``/``FORBIDDEN_FUNCTIONS`` are a blocklist, so any
    /// read/write function missing from them (``read_blob``, ``read_text``,
    /// ``COPY ... TO``, extension installs) would otherwise still reach the
    /// filesystem or network with LLM-authored SQL. This is the engine-level
    /// counterpart of ``_apply_sandbox_settings`` in nl_query/data_engine.py.
    ///
    /// The order matters: ``enable_external_access`` is itself a configuration
    /// option, so it cannot be changed once ``lock_configuration`` is set.
    ///
    /// Every connection opened on this database instance shares the setting,
    /// and a failure here is fatal — serving queries behind a blocklist alone
    /// is exactly what this method exists to stop.
    fn lock_down_duckdb(&self) -> Result<()> {
        let duck = self
            .duck_conn
            .lock()
            .map_err(|_| anyhow!("DuckDB mutex poisoned"))?;
        duck.execute_batch("SET enable_external_access = false;\nSET lock_configuration = true;")?;
        Ok(())
    }

    fn init_bronze_sqlite(bronze_path: &Path) -> Result<()> {
        if let Some(parent) = bronze_path.parent() {
            if !parent.as_os_str().is_empty() {
                std::fs::create_dir_all(parent)?;
            }
        }
        let conn = SqliteConnection::open(bronze_path)?;
        conn.execute_batch(
            r#"
            PRAGMA journal_mode = WAL;
            CREATE TABLE IF NOT EXISTS bronze_schools (
                school_id TEXT PRIMARY KEY,
                school_name TEXT NOT NULL,
                school_type TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS bronze_students (
                student_id_hash TEXT NOT NULL,
                academic_year TEXT NOT NULL,
                grade_level INTEGER NOT NULL,
                gender TEXT NOT NULL,
                ethnicity TEXT NOT NULL,
                primary_race TEXT NOT NULL,
                sed_status INTEGER NOT NULL,
                ell_status INTEGER NOT NULL,
                sped_status INTEGER NOT NULL,
                PRIMARY KEY (student_id_hash, academic_year)
            );
            CREATE TABLE IF NOT EXISTS bronze_attendance (
                student_id_hash TEXT NOT NULL,
                school_id TEXT NOT NULL,
                academic_year TEXT NOT NULL,
                days_enrolled INTEGER NOT NULL,
                days_present INTEGER NOT NULL,
                days_absent INTEGER NOT NULL,
                unexcused_absences INTEGER NOT NULL,
                attendance_rate REAL NOT NULL,
                PRIMARY KEY (student_id_hash, academic_year)
            );
            CREATE TABLE IF NOT EXISTS bronze_school_name_overrides (
                school_id TEXT PRIMARY KEY,
                override_school_name TEXT NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS bronze_school_summary (
                school_id TEXT NOT NULL,
                academic_year TEXT NOT NULL,
                school_name TEXT NOT NULL,
                school_type TEXT NOT NULL,
                total_students INTEGER NOT NULL,
                avg_gpa REAL NOT NULL,
                avg_attendance_rate REAL NOT NULL,
                total_incidents INTEGER NOT NULL,
                students_with_incidents INTEGER NOT NULL,
                PRIMARY KEY (school_id, academic_year)
            );
            CREATE TABLE IF NOT EXISTS bronze_equity_by_race (
                academic_year TEXT NOT NULL,
                primary_race TEXT NOT NULL,
                student_count INTEGER NOT NULL,
                avg_gpa REAL NOT NULL,
                avg_attendance_rate REAL NOT NULL,
                incident_count INTEGER NOT NULL,
                PRIMARY KEY (academic_year, primary_race)
            );
            CREATE TABLE IF NOT EXISTS bronze_cde_accountability (
                academic_year TEXT NOT NULL,
                cds_code TEXT NOT NULL,
                school_name TEXT NOT NULL,
                reporting_category TEXT NOT NULL,
                reporting_category_label TEXT NOT NULL,
                ca_chronic_absent_rate_pct REAL NOT NULL,
                su_suspension_rate_pct REAL NOT NULL,
                exp_total_expulsions INTEGER NOT NULL,
                PRIMARY KEY (academic_year, cds_code, reporting_category)
            );
            "#,
        )?;

        let count: i64 =
            conn.query_row("SELECT COUNT(*) FROM bronze_schools", [], |r| r.get(0))?;
        if count == 0 {
            conn.execute_batch(
                r#"
                INSERT INTO bronze_schools VALUES
                    ('1', 'Lincoln High School', 'High'),
                    ('2', 'Roosevelt Middle School', 'Middle'),
                    ('3', 'Washington Elementary School', 'Elementary'),
                    ('4', 'Jefferson High School', 'High');

                INSERT INTO bronze_students VALUES
                    ('stu_001', '2023-2024', 10, 'F', 'Hispanic', 'Hispanic/Latino', 1, 1, 0),
                    ('stu_002', '2023-2024', 11, 'M', 'Hispanic', 'Hispanic/Latino', 1, 1, 0),
                    ('stu_003', '2023-2024', 9,  'F', 'Not Hispanic', 'Black/African American', 1, 0, 1),
                    ('stu_004', '2023-2024', 12, 'M', 'Not Hispanic', 'White', 0, 0, 0),
                    ('stu_005', '2023-2024', 10, 'F', 'Not Hispanic', 'Asian', 0, 1, 0),
                    ('stu_006', '2024-2025', 11, 'F', 'Hispanic', 'Hispanic/Latino', 1, 1, 0),
                    ('stu_007', '2024-2025', 12, 'M', 'Hispanic', 'Hispanic/Latino', 1, 0, 0),
                    ('stu_008', '2024-2025', 10, 'F', 'Not Hispanic', 'Black/African American', 1, 0, 1);

                INSERT INTO bronze_attendance VALUES
                    ('stu_001', '1', '2023-2024', 180, 166, 14, 4, 0.9222),
                    ('stu_002', '1', '2023-2024', 180, 160, 20, 7, 0.8889),
                    ('stu_003', '2', '2023-2024', 180, 155, 25, 9, 0.8611),
                    ('stu_004', '4', '2023-2024', 180, 173, 7,  1, 0.9611),
                    ('stu_005', '3', '2023-2024', 180, 175, 5,  0, 0.9722),
                    ('stu_006', '1', '2024-2025', 180, 168, 12, 3, 0.9333),
                    ('stu_007', '1', '2024-2025', 180, 164, 16, 5, 0.9111),
                    ('stu_008', '2', '2024-2025', 180, 158, 22, 8, 0.8778);

                INSERT INTO bronze_school_summary VALUES
                    ('1', '2021-2022', 'Lincoln High School', 'High', 1180, 2.86, 0.912, 128, 86),
                    ('2', '2021-2022', 'Roosevelt Middle School', 'Middle', 810, 2.94, 0.924, 94, 65),
                    ('3', '2021-2022', 'Washington Elementary School', 'Elementary', 590, 3.21, 0.941, 24, 19),
                    ('4', '2021-2022', 'Jefferson High School', 'High', 1050, 2.79, 0.903, 142, 98),
                    ('1', '2022-2023', 'Lincoln High School', 'High', 1205, 2.89, 0.916, 121, 82),
                    ('2', '2022-2023', 'Roosevelt Middle School', 'Middle', 835, 2.98, 0.929, 88, 61),
                    ('3', '2022-2023', 'Washington Elementary School', 'Elementary', 605, 3.25, 0.945, 21, 17),
                    ('4', '2022-2023', 'Jefferson High School', 'High', 1080, 2.83, 0.908, 134, 91),
                    ('1', '2023-2024', 'Lincoln High School', 'High', 1240, 2.92, 0.918, 115, 78),
                    ('2', '2023-2024', 'Roosevelt Middle School', 'Middle', 860, 3.04, 0.934, 82, 54),
                    ('3', '2023-2024', 'Washington Elementary School', 'Elementary', 620, 3.28, 0.948, 19, 15),
                    ('4', '2023-2024', 'Jefferson High School', 'High', 1120, 2.85, 0.909, 132, 89),
                    ('1', '2024-2025', 'Lincoln High School', 'High', 1265, 2.96, 0.924, 108, 72),
                    ('2', '2024-2025', 'Roosevelt Middle School', 'Middle', 875, 3.09, 0.938, 76, 50),
                    ('3', '2024-2025', 'Washington Elementary School', 'Elementary', 635, 3.31, 0.952, 16, 13),
                    ('4', '2024-2025', 'Jefferson High School', 'High', 1145, 2.90, 0.915, 124, 83);

                INSERT INTO bronze_equity_by_race VALUES
                    ('2023-2024', 'Hispanic/Latino', 1650, 2.84, 0.915, 168),
                    ('2023-2024', 'White', 980, 3.18, 0.942, 72),
                    ('2023-2024', 'Asian', 540, 3.46, 0.964, 18),
                    ('2023-2024', 'Black/African American', 420, 2.71, 0.892, 64),
                    ('2023-2024', 'Two or More Races', 250, 3.08, 0.931, 26),
                    ('2024-2025', 'Hispanic/Latino', 1690, 2.89, 0.921, 154),
                    ('2024-2025', 'White', 995, 3.22, 0.946, 66),
                    ('2024-2025', 'Asian', 555, 3.49, 0.967, 15),
                    ('2024-2025', 'Black/African American', 430, 2.76, 0.899, 59),
                    ('2024-2025', 'Two or More Races', 250, 3.12, 0.936, 23);

                INSERT INTO bronze_cde_accountability VALUES
                    ('2023-24', '19647330000001', 'Lincoln High School', 'RB', 'Black / African American', 28.4, 6.8, 2),
                    ('2023-24', '19647330000001', 'Lincoln High School', 'SED', 'Socioeconomically Disadvantaged', 24.1, 4.9, 3),
                    ('2023-24', '19647330000001', 'Lincoln High School', 'RH', 'Hispanic / Latino', 22.6, 4.2, 2),
                    ('2023-24', '19647330000001', 'Lincoln High School', 'EL', 'English Learners', 21.8, 3.7, 1),
                    ('2023-24', '19647330000001', 'Lincoln High School', 'TA', 'All Students', 18.5, 3.4, 4),
                    ('2023-24', '19647330000001', 'Lincoln High School', 'RW', 'White', 14.2, 2.8, 1),
                    ('2023-24', '19647330000001', 'Lincoln High School', 'RA', 'Asian', 8.6, 1.1, 0);
                "#,
            )?;
        }
        Ok(())
    }

    pub fn ingest_bronze_attendance(&self, input: &BronzeAttendanceInput) -> Result<()> {
        let sqlite = SqliteConnection::open(&self.bronze_path)?;
        sqlite.execute(
            r#"
            INSERT OR REPLACE INTO bronze_attendance
            (student_id_hash, school_id, academic_year, days_enrolled, days_present, days_absent, unexcused_absences, attendance_rate)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)
            "#,
            params![
                input.student_id_hash,
                input.school_id,
                input.academic_year,
                input.days_enrolled,
                input.days_present,
                input.days_absent,
                input.unexcused_absences,
                input.attendance_rate,
            ],
        )?;
        self.sync_bronze_to_silver_and_gold()
    }

    pub fn set_school_name_override(&self, school_id: &str, override_school_name: &str) -> Result<()> {
        let sqlite = SqliteConnection::open(&self.bronze_path)?;
        sqlite.execute(
            r#"
            INSERT OR REPLACE INTO bronze_school_name_overrides (school_id, override_school_name, updated_at)
            VALUES (?1, ?2, CURRENT_TIMESTAMP)
            "#,
            params![school_id, override_school_name],
        )?;
        self.sync_bronze_to_silver_and_gold()
    }

    /// Synchronize Bronze SQLite ACID tables into DuckDB K-12 Silver (`main_core`) & Gold (`main_analytics`) tables.
    pub fn sync_bronze_to_silver_and_gold(&self) -> Result<()> {
        let sqlite = SqliteConnection::open(&self.bronze_path)?;
        let duck = self
            .duck_conn
            .lock()
            .map_err(|_| anyhow!("DuckDB mutex poisoned"))?;

        duck.execute_batch(
            r#"
            CREATE SCHEMA IF NOT EXISTS main_core;
            CREATE SCHEMA IF NOT EXISTS main_analytics;
            CREATE SCHEMA IF NOT EXISTS main_staging;

            CREATE OR REPLACE TABLE main_core.dim_schools (
                school_id VARCHAR,
                school_name VARCHAR,
                school_type VARCHAR
            );

            CREATE OR REPLACE TABLE main_core.dim_students (
                student_id_hash VARCHAR,
                academic_year VARCHAR,
                grade_level BIGINT,
                gender VARCHAR,
                ethnicity VARCHAR,
                primary_race VARCHAR,
                sed_status BOOLEAN,
                ell_status BOOLEAN,
                sped_status BOOLEAN
            );

            CREATE OR REPLACE TABLE main_core.fact_attendance (
                student_id_hash VARCHAR,
                school_id VARCHAR,
                academic_year VARCHAR,
                days_enrolled BIGINT,
                days_present BIGINT,
                days_absent BIGINT,
                unexcused_absences BIGINT,
                attendance_rate DOUBLE
            );

            CREATE OR REPLACE TABLE main_analytics.school_summary (
                school_id VARCHAR,
                academic_year VARCHAR,
                school_name VARCHAR,
                school_type VARCHAR,
                total_students BIGINT,
                avg_gpa DOUBLE,
                avg_attendance_rate DOUBLE,
                total_incidents BIGINT,
                students_with_incidents BIGINT
            );

            CREATE OR REPLACE TABLE main_analytics.equity_by_race (
                academic_year VARCHAR,
                primary_race VARCHAR,
                student_count BIGINT,
                avg_gpa DOUBLE,
                avg_attendance_rate DOUBLE,
                incident_count BIGINT
            );

            CREATE OR REPLACE TABLE main_analytics.mart_cde_school_accountability (
                academic_year VARCHAR,
                cds_code VARCHAR,
                school_name VARCHAR,
                reporting_category VARCHAR,
                reporting_category_label VARCHAR,
                ca_chronic_absent_rate_pct DOUBLE,
                su_suspension_rate_pct DOUBLE,
                exp_total_expulsions BIGINT
            );
            "#,
        )?;

        // 1. Sync dim_schools (applying any Bronze school_name overrides)
        {
            let mut stmt = sqlite.prepare(
                r#"
                SELECT s.school_id,
                       COALESCE(o.override_school_name, s.school_name) AS school_name,
                       s.school_type
                FROM bronze_schools s
                LEFT JOIN bronze_school_name_overrides o
                  ON s.school_id = o.school_id
                "#,
            )?;
            let rows = stmt.query_map([], |r| {
                Ok((
                    r.get::<_, String>(0)?,
                    r.get::<_, String>(1)?,
                    r.get::<_, String>(2)?,
                ))
            })?;
            for row in rows {
                let (id, name, stype) = row?;
                duck.execute(
                    "INSERT INTO main_core.dim_schools VALUES (?, ?, ?)",
                    duckdb::params![id, name, stype],
                )?;
            }
        }

        // 2. Sync dim_students
        {
            let mut stmt = sqlite.prepare(
                r#"
                SELECT student_id_hash, academic_year, grade_level, gender, ethnicity,
                       primary_race, sed_status, ell_status, sped_status
                FROM bronze_students
                "#,
            )?;
            let rows = stmt.query_map([], |r| {
                Ok((
                    r.get::<_, String>(0)?,
                    r.get::<_, String>(1)?,
                    r.get::<_, i64>(2)?,
                    r.get::<_, String>(3)?,
                    r.get::<_, String>(4)?,
                    r.get::<_, String>(5)?,
                    r.get::<_, i64>(6)? != 0,
                    r.get::<_, i64>(7)? != 0,
                    r.get::<_, i64>(8)? != 0,
                ))
            })?;
            for row in rows {
                let (sid, yr, gr, gen, eth, race, sed, ell, sped) = row?;
                duck.execute(
                    "INSERT INTO main_core.dim_students VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    duckdb::params![sid, yr, gr, gen, eth, race, sed, ell, sped],
                )?;
            }
        }

        // 3. Sync fact_attendance
        {
            let mut stmt = sqlite.prepare(
                r#"
                SELECT student_id_hash, school_id, academic_year, days_enrolled,
                       days_present, days_absent, unexcused_absences, attendance_rate
                FROM bronze_attendance
                "#,
            )?;
            let rows = stmt.query_map([], |r| {
                Ok((
                    r.get::<_, String>(0)?,
                    r.get::<_, String>(1)?,
                    r.get::<_, String>(2)?,
                    r.get::<_, i64>(3)?,
                    r.get::<_, i64>(4)?,
                    r.get::<_, i64>(5)?,
                    r.get::<_, i64>(6)?,
                    r.get::<_, f64>(7)?,
                ))
            })?;
            for row in rows {
                let (sid, sch_id, yr, enr, pres, abs, unex, rate) = row?;
                duck.execute(
                    "INSERT INTO main_core.fact_attendance VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    duckdb::params![sid, sch_id, yr, enr, pres, abs, unex, rate],
                )?;
            }
        }

        // 4. Sync school_summary (applying school_name override if present)
        {
            let mut stmt = sqlite.prepare(
                r#"
                SELECT ss.school_id,
                       ss.academic_year,
                       COALESCE(o.override_school_name, ss.school_name) AS school_name,
                       ss.school_type,
                       ss.total_students,
                       ss.avg_gpa,
                       ss.avg_attendance_rate,
                       ss.total_incidents,
                       ss.students_with_incidents
                FROM bronze_school_summary ss
                LEFT JOIN bronze_school_name_overrides o
                  ON ss.school_id = o.school_id
                "#,
            )?;
            let rows = stmt.query_map([], |r| {
                Ok((
                    r.get::<_, String>(0)?,
                    r.get::<_, String>(1)?,
                    r.get::<_, String>(2)?,
                    r.get::<_, String>(3)?,
                    r.get::<_, i64>(4)?,
                    r.get::<_, f64>(5)?,
                    r.get::<_, f64>(6)?,
                    r.get::<_, i64>(7)?,
                    r.get::<_, i64>(8)?,
                ))
            })?;
            for row in rows {
                let (id, yr, name, stype, tot, gpa, att, inc, st_inc) = row?;
                duck.execute(
                    "INSERT INTO main_analytics.school_summary VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    duckdb::params![id, yr, name, stype, tot, gpa, att, inc, st_inc],
                )?;
            }
        }

        // 5. Sync equity_by_race
        {
            let mut stmt = sqlite.prepare(
                r#"
                SELECT academic_year, primary_race, student_count, avg_gpa, avg_attendance_rate, incident_count
                FROM bronze_equity_by_race
                "#,
            )?;
            let rows = stmt.query_map([], |r| {
                Ok((
                    r.get::<_, String>(0)?,
                    r.get::<_, String>(1)?,
                    r.get::<_, i64>(2)?,
                    r.get::<_, f64>(3)?,
                    r.get::<_, f64>(4)?,
                    r.get::<_, i64>(5)?,
                ))
            })?;
            for row in rows {
                let (yr, race, cnt, gpa, att, inc) = row?;
                duck.execute(
                    "INSERT INTO main_analytics.equity_by_race VALUES (?, ?, ?, ?, ?, ?)",
                    duckdb::params![yr, race, cnt, gpa, att, inc],
                )?;
            }
        }

        // 6. Sync mart_cde_school_accountability
        {
            let mut stmt = sqlite.prepare(
                r#"
                SELECT academic_year, cds_code, school_name, reporting_category,
                       reporting_category_label, ca_chronic_absent_rate_pct, su_suspension_rate_pct, exp_total_expulsions
                FROM bronze_cde_accountability
                "#,
            )?;
            let rows = stmt.query_map([], |r| {
                Ok((
                    r.get::<_, String>(0)?,
                    r.get::<_, String>(1)?,
                    r.get::<_, String>(2)?,
                    r.get::<_, String>(3)?,
                    r.get::<_, String>(4)?,
                    r.get::<_, f64>(5)?,
                    r.get::<_, f64>(6)?,
                    r.get::<_, i64>(7)?,
                ))
            })?;
            for row in rows {
                let (yr, cds, sname, rc, rcl, ca, su, exp) = row?;
                duck.execute(
                    "INSERT INTO main_analytics.mart_cde_school_accountability VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    duckdb::params![yr, cds, sname, rc, rcl, ca, su, exp],
                )?;
            }
        }

        Ok(())
    }

    /// Attach the K-12 Education warehouse (`analytics.duckdb`) in read-only mode and expose
    /// its `main_core`, `main_analytics`, and `main_staging` views in the unified session.
    pub fn attach_education_warehouse(&self, edu_path: &Path) -> Result<()> {
        let duck = self
            .duck_conn
            .lock()
            .map_err(|_| anyhow!("DuckDB mutex poisoned"))?;
        let escaped = edu_path.to_string_lossy().replace('\'', "''");
        duck.execute_batch(&format!(
            "ATTACH IF NOT EXISTS '{escaped}' AS edu_wh (READ_ONLY);"
        ))?;

        let mut stmt = duck.prepare(
            r#"
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_catalog = 'edu_wh'
              AND table_schema IN ('main_core', 'main_analytics')
              AND table_name NOT LIKE '_dlt%'
              AND lower(table_name) NOT LIKE '%pii_lookup%'
            "#,
        )?;
        let pairs: Vec<(String, String)> = stmt
            .query_map([], |r| Ok((r.get(0)?, r.get(1)?)))?
            .filter_map(|r| r.ok())
            .collect();

        for (schema, table) in pairs {
            let quoted_schema = format!("\"{}\"", schema.replace('"', "\"\""));
            let quoted_table = format!("\"{}\"", table.replace('"', "\"\""));
            let view_sql = format!(
                "CREATE OR REPLACE VIEW {quoted_schema}.{quoted_table} AS SELECT * FROM \"edu_wh\".{quoted_schema}.{quoted_table}"
            );
            let _ = duck.execute(&view_sql, []);
        }
        Ok(())
    }
}

struct CompiledSqlValidators {
    forbidden_tokens: Vec<(&'static str, Regex)>,
    forbidden_functions: Vec<(&'static str, Regex)>,
    wildcard_re: Regex,
    forbidden_pii_re: Regex,
}

fn sql_validators() -> &'static CompiledSqlValidators {
    static VALIDATORS: OnceLock<CompiledSqlValidators> = OnceLock::new();
    VALIDATORS.get_or_init(|| {
        let forbidden_tokens = FORBIDDEN_TOKENS
            .iter()
            .map(|&token| {
                let pat = format!(r"\b{}\b", regex::escape(token));
                (token, Regex::new(&pat).expect("valid token regex"))
            })
            .collect();
        let forbidden_functions = FORBIDDEN_FUNCTIONS
            .iter()
            .map(|&func| {
                let pat = format!(r"\b{}\s*\(", regex::escape(func));
                (func, Regex::new(&pat).expect("valid function regex"))
            })
            .collect();
        let wildcard_re = Regex::new(
            r"(?is)\bselect\s+(?:all\s+|distinct\s+)?\*|\bselect\b[^;]*?\w+\.\s*\*|\bcolumns\s*\(",
        )
        .expect("valid wildcard regex");
        let forbidden_pii_re = Regex::new(
            r"(?i)\bstg_aeries__|\bstg_cde__schools\b|\w+_raw\b|\bfirst_name\b|\blast_name\b|\bdate_of_birth\b|\bstudent_id_raw\b",
        )
        .expect("valid pii regex");
        CompiledSqlValidators {
            forbidden_tokens,
            forbidden_functions,
            wildcard_re,
            forbidden_pii_re,
        }
    })
}

const DENIED_SQL_SUBSTRINGS: &[&str] = &[
    "main_privacy_sensitive.",
    "edu_wh.",
    "priv_",
    "pii_lookup",
    "_dlt",
    "main_staging.",
    "stg_aeries__",
    "_raw",
];

pub fn extract_sql_from_input(raw_input: &str) -> String {
    let trimmed = raw_input.trim();
    if trimmed.starts_with('{') && trimmed.ends_with('}') {
        if let Ok(val) = serde_json::from_str::<Value>(trimmed) {
            if let Some(sql) = val
                .get("arguments")
                .and_then(|a| a.get("sql"))
                .and_then(|s| s.as_str())
            {
                return sql.trim().trim_end_matches(';').trim().to_string();
            }
            if let Some(sql) = val.get("sql").and_then(|s| s.as_str()) {
                return sql.trim().trim_end_matches(';').trim().to_string();
            }
        }
    }
    trimmed.trim_end_matches(';').trim().to_string()
}

pub fn validate_read_only_sql(sql: &str) -> Result<(), DuckDBExecutionError> {
    let cleaned = sql.trim();
    if cleaned.is_empty() {
        return Err(DuckDBExecutionError {
            status: "error".to_string(),
            error_type: "ValidationError".to_string(),
            message: "Empty SQL query — nothing to execute.".to_string(),
        });
    }

    let validators = sql_validators();
    let lower = cleaned.to_lowercase();
    for (token, re) in &validators.forbidden_tokens {
        if re.is_match(&lower) {
            return Err(DuckDBExecutionError {
                status: "error".to_string(),
                error_type: "ValidationError".to_string(),
                message: format!(
                    "Forbidden operation detected: '{token}'. Only SELECT queries are allowed."
                ),
            });
        }
    }

    if !lower.contains("select") {
        return Err(DuckDBExecutionError {
            status: "error".to_string(),
            error_type: "ValidationError".to_string(),
            message: "Only SELECT queries are allowed. No SELECT found.".to_string(),
        });
    }

    for (func, re) in &validators.forbidden_functions {
        if re.is_match(&lower) {
            return Err(DuckDBExecutionError {
                status: "error".to_string(),
                error_type: "ValidationError".to_string(),
                message: format!(
                    "Forbidden file-reading function detected: '{func}'. Only warehouse tables are allowed."
                ),
            });
        }
    }

    for denied in DENIED_SQL_SUBSTRINGS {
        if lower.contains(denied) {
            return Err(DuckDBExecutionError {
                status: "error".to_string(),
                error_type: "ValidationError".to_string(),
                message: format!("Reference to restricted object '{denied}' is not allowed."),
            });
        }
    }

    if let Some(m) = validators.forbidden_pii_re.find(&lower) {
        return Err(DuckDBExecutionError {
            status: "error".to_string(),
            error_type: "ValidationError".to_string(),
            message: format!(
                "Forbidden PII or staging column/table '{}' is not allowed.",
                m.as_str()
            ),
        });
    }

    if validators.wildcard_re.is_match(&lower) && lower.contains("dim_students") {
        return Err(DuckDBExecutionError {
            status: "error".to_string(),
            error_type: "ValidationError".to_string(),
            message: "Wildcard SELECT * against protected table 'dim_students' is not allowed."
                .to_string(),
        });
    }

    Ok(())
}

pub fn format_duckdb_error_message(raw_err: &str) -> DuckDBExecutionError {
    let trimmed = raw_err.trim();
    for (prefix, label) in [
        ("Binder Error:", "BinderError"),
        ("Catalog Error:", "CatalogError"),
        ("Parser Error:", "ParserError"),
        ("Conversion Error:", "ConversionError"),
    ] {
        if let Some(rest) = trimmed.strip_prefix(prefix) {
            return DuckDBExecutionError {
                status: "error".to_string(),
                error_type: label.to_string(),
                message: rest.trim().to_string(),
            };
        }
    }
    DuckDBExecutionError {
        status: "error".to_string(),
        error_type: "ExecutionError".to_string(),
        message: trimmed.to_string(),
    }
}

fn serialize_batches_to_ipc(batches: &[RecordBatch], schema: &arrow_schema::SchemaRef) -> Result<Vec<u8>> {
    let mut buf = Vec::new();
    {
        let mut writer = StreamWriter::try_new(&mut buf, schema)?;
        for batch in batches {
            writer.write(batch)?;
        }
        writer.finish()?;
    }
    Ok(buf)
}

fn format_cell_value(formatter: &ArrayFormatter<'_>, row_idx: usize, data_type: &str) -> Value {
    let s = formatter.value(row_idx).to_string();
    let upper = data_type.to_uppercase();
    if upper.contains("INT") {
        if let Ok(i) = s.parse::<i64>() {
            return json!(i);
        }
    } else if upper.contains("DOUBLE")
        || upper.contains("FLOAT")
        || upper.contains("DECIMAL")
        || upper.contains("NUMERIC")
        || upper.contains("REAL")
    {
        if let Ok(f) = s.parse::<f64>() {
            if f.is_finite() {
                return json!(f);
            }
        }
    } else if upper.contains("BOOL") {
        if let Ok(b) = s.parse::<bool>() {
            return json!(b);
        }
    }
    json!(s)
}

fn is_numeric_or_temporal(dtype: &str) -> bool {
    let upper = dtype.to_uppercase();
    [
        "INT", "DOUBLE", "FLOAT", "DECIMAL", "NUMERIC", "REAL", "DATE", "TIME",
    ]
    .iter()
    .any(|k| upper.contains(k))
}

impl MedallionEngine {
    pub fn execute_and_cache_arrow(
        &self,
        raw_input: &str,
        custom_query_id: Option<String>,
    ) -> std::result::Result<CachedQueryEntry, DuckDBExecutionError> {
        let sql = extract_sql_from_input(raw_input);
        validate_read_only_sql(&sql)?;

        let duck = self.duck_conn.lock().map_err(|_| DuckDBExecutionError {
            status: "error".to_string(),
            error_type: "ExecutionError".to_string(),
            message: "DuckDB connection lock poisoned".to_string(),
        })?;

        // Describe logical types and trigger binder/catalog validation first
        let desc_sql = format!("DESCRIBE SELECT * FROM (\n{sql}\n) AS _desc");
        let mut col_types: HashMap<String, String> = HashMap::new();
        {
            let mut desc_stmt = duck
                .prepare(&desc_sql)
                .map_err(|e| format_duckdb_error_message(&e.to_string()))?;
            let desc_rows = desc_stmt
                .query_map([], |r| Ok((r.get::<_, String>(0)?, r.get::<_, String>(1)?)))
                .map_err(|e| format_duckdb_error_message(&e.to_string()))?;
            for r in desc_rows.flatten() {
                col_types.insert(r.0, r.1);
            }
        }

        let safe_sql = format!("SELECT * FROM (\n{sql}\n) AS _safe LIMIT {MAX_RESULT_ROWS}");
        let mut stmt = duck
            .prepare(&safe_sql)
            .map_err(|e| format_duckdb_error_message(&e.to_string()))?;
        let arrow_iter = stmt
            .query_arrow([])
            .map_err(|e| format_duckdb_error_message(&e.to_string()))?;
        let schema = arrow_iter.get_schema();
        let batches: Vec<RecordBatch> = arrow_iter.collect();

        let ipc_bytes = serialize_batches_to_ipc(&batches, &schema).map_err(|e| {
            DuckDBExecutionError {
                status: "error".to_string(),
                error_type: "SerializationError".to_string(),
                message: e.to_string(),
            }
        })?;

        let query_id = custom_query_id.unwrap_or_else(|| {
            let short = &Uuid::new_v4().simple().to_string()[..8];
            format!("q_{short}")
        });

        let summary = build_result_summary(&query_id, &schema, &batches, &col_types);

        let entry = CachedQueryEntry {
            query_id,
            base_sql: sql,
            arrow_ipc_bytes: ipc_bytes,
            summary,
        };
        self.arrow_cache.insert(entry.clone());
        Ok(entry)
    }

    pub fn apply_query_filters(
        &self,
        query_id_or_sql: &str,
        filters: &[FilterSpec],
    ) -> std::result::Result<CachedQueryEntry, DuckDBExecutionError> {
        let base_sql = if let Some(existing) = self.arrow_cache.get(query_id_or_sql) {
            existing.base_sql
        } else {
            extract_sql_from_input(query_id_or_sql)
        };
        validate_read_only_sql(&base_sql)?;

        // Verify filter columns against base query schema
        let valid_cols: HashSet<String> = {
            let duck = self.duck_conn.lock().map_err(|_| DuckDBExecutionError {
                status: "error".to_string(),
                error_type: "ExecutionError".to_string(),
                message: "DuckDB mutex poisoned".to_string(),
            })?;
            let desc_sql = format!("DESCRIBE SELECT * FROM (\n{base_sql}\n) AS _desc");
            let mut stmt = duck
                .prepare(&desc_sql)
                .map_err(|e| format_duckdb_error_message(&e.to_string()))?;
            let rows = stmt
                .query_map([], |r| r.get::<_, String>(0))
                .map_err(|e| format_duckdb_error_message(&e.to_string()))?;
            rows.flatten().collect()
        };

        let mut where_clauses: Vec<String> = Vec::new();
        for f in filters {
            if !valid_cols.contains(&f.column) {
                return Err(DuckDBExecutionError {
                    status: "error".to_string(),
                    error_type: "ValidationError".to_string(),
                    message: format!("Invalid filter column '{}'.", f.column),
                });
            }
            let quoted_col = format!("\"{}\"", f.column.replace('"', "\"\""));
            match f.control_type.as_str() {
                "date_range" | "numeric_range" => {
                    if let Some(min_v) = &f.min {
                        where_clauses.push(format!("{quoted_col} >= {}", sql_literal(min_v)));
                    }
                    if let Some(max_v) = &f.max {
                        where_clauses.push(format!("{quoted_col} <= {}", sql_literal(max_v)));
                    }
                }
                "multi_select" => {
                    if let Some(vals) = &f.values {
                        if !vals.is_empty() {
                            let lits: Vec<String> = vals.iter().map(sql_literal).collect();
                            where_clauses.push(format!("{quoted_col} IN ({})", lits.join(", ")));
                        }
                    }
                }
                "single_select" => {
                    if let Some(val) = &f.value {
                        where_clauses.push(format!("{quoted_col} = {}", sql_literal(val)));
                    }
                }
                "search" => {
                    if let Some(q) = &f.query {
                        let trimmed = q.trim();
                        if !trimmed.is_empty() {
                            let escaped = trimmed.replace('\'', "''");
                            where_clauses.push(format!(
                                "CAST({quoted_col} AS VARCHAR) ILIKE '%{escaped}%'"
                            ));
                        }
                    }
                }
                other => {
                    return Err(DuckDBExecutionError {
                        status: "error".to_string(),
                        error_type: "ValidationError".to_string(),
                        message: format!("Unsupported filter control_type: '{other}'"),
                    });
                }
            }
        }

        let where_sql = if where_clauses.is_empty() {
            String::new()
        } else {
            format!("WHERE {}", where_clauses.join(" AND "))
        };

        let wrapped_sql = format!(
            "WITH _base AS (\n{base_sql}\n)\nSELECT * FROM _base\n{where_sql}"
        );

        let mut entry = self.execute_and_cache_arrow(&wrapped_sql, None)?;
        // Preserve original base_sql so subsequent FilterBar changes continue wrapping the clean base query
        entry.base_sql = base_sql;
        self.arrow_cache.insert(entry.clone());
        Ok(entry)
    }
}

fn sql_literal(val: &Value) -> String {
    match val {
        Value::Number(n) => n.to_string(),
        Value::Bool(b) => {
            if *b {
                "TRUE".to_string()
            } else {
                "FALSE".to_string()
            }
        }
        Value::String(s) => format!("'{}'", s.replace('\'', "''")),
        _ => format!("'{}'", val.to_string().replace('\'', "''")),
    }
}

fn build_result_summary(
    query_id: &str,
    schema: &arrow_schema::SchemaRef,
    batches: &[RecordBatch],
    logical_types: &HashMap<String, String>,
) -> DuckDBResultSummary {
    let row_count: usize = batches.iter().map(|b| b.num_rows()).sum();
    let num_cols = schema.fields().len();

    let mut col_values: Vec<Vec<Value>> = vec![Vec::new(); num_cols];
    let mut null_counts: Vec<usize> = vec![0; num_cols];
    let mut sample_rows: Vec<Vec<Value>> = Vec::new();

    for batch in batches {
        let formatters: Vec<Option<ArrayFormatter<'_>>> = (0..num_cols)
            .map(|c_idx| {
                ArrayFormatter::try_new(batch.column(c_idx).as_ref(), &Default::default()).ok()
            })
            .collect();

        for r_idx in 0..batch.num_rows() {
            let capture_sample = sample_rows.len() < 3;
            let mut sample_row = if capture_sample {
                Vec::with_capacity(num_cols)
            } else {
                Vec::new()
            };

            for c_idx in 0..num_cols {
                let col_arr = batch.column(c_idx);
                let field_name = schema.field(c_idx).name();
                let dtype = logical_types
                    .get(field_name)
                    .cloned()
                    .unwrap_or_else(|| format!("{:?}", schema.field(c_idx).data_type()));

                if col_arr.is_null(r_idx) {
                    null_counts[c_idx] += 1;
                    if capture_sample {
                        sample_row.push(Value::Null);
                    }
                } else if let Some(fmt) = &formatters[c_idx] {
                    let v = format_cell_value(fmt, r_idx, &dtype);
                    col_values[c_idx].push(v.clone());
                    if capture_sample {
                        sample_row.push(v);
                    }
                }
            }
            if capture_sample {
                sample_rows.push(sample_row);
            }
        }
    }

    let mut columns = Vec::with_capacity(num_cols);
    for (c_idx, field) in schema.fields().iter().enumerate() {
        let name = field.name().clone();
        let dtype = logical_types
            .get(&name)
            .cloned()
            .unwrap_or_else(|| format!("{:?}", field.data_type()).to_uppercase());

        let vals = &col_values[c_idx];
        let mut distinct_set: HashSet<String> = HashSet::new();
        let mut unique_ordered: Vec<Value> = Vec::new();
        for v in vals {
            let key = serde_json::to_string(v).unwrap_or_default();
            if distinct_set.insert(key) {
                unique_ordered.push(v.clone());
            }
        }

        let (min_val, max_val, sample_vals) = if is_numeric_or_temporal(&dtype) && !vals.is_empty() {
            let mut min_v = vals[0].clone();
            let mut max_v = vals[0].clone();
            for v in vals.iter().skip(1) {
                if compare_json_values(v, &min_v) == std::cmp::Ordering::Less {
                    min_v = v.clone();
                }
                if compare_json_values(v, &max_v) == std::cmp::Ordering::Greater {
                    max_v = v.clone();
                }
            }
            (Some(min_v), Some(max_v), None)
        } else if !unique_ordered.is_empty() {
            (
                None,
                None,
                Some(unique_ordered.into_iter().take(3).collect()),
            )
        } else {
            (None, None, None)
        };

        columns.push(ColumnSummary {
            name,
            data_type: dtype,
            distinct_count: distinct_set.len(),
            null_count: null_counts[c_idx],
            min: min_val,
            max: max_val,
            sample_values: sample_vals,
        });
    }

    DuckDBResultSummary {
        status: "ok".to_string(),
        query_id: query_id.to_string(),
        row_count,
        columns,
        sample_rows,
    }
}

fn compare_json_values(a: &Value, b: &Value) -> std::cmp::Ordering {
    match (a.as_f64(), b.as_f64()) {
        (Some(fa), Some(fb)) => fa.partial_cmp(&fb).unwrap_or(std::cmp::Ordering::Equal),
        _ => a
            .as_str()
            .unwrap_or_default()
            .cmp(b.as_str().unwrap_or_default()),
    }
}
