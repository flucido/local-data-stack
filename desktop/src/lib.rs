pub mod agent_loop;
pub mod ipc;
pub mod medallion;
pub mod schema_pruner;

#[cfg(test)]
mod tests {
    use super::ipc::{handle_arrow_protocol_request, handle_ipc_message, parse_arrow_query_id};
    use super::medallion::{BronzeAttendanceInput, FilterSpec, MedallionEngine};
    use super::schema_pruner::{
        compile_hop1_gbnf, compile_hop2_gbnf, format_pruned_ddl, load_unified_schema,
        select_top_k_tables,
    };
    use arrow_ipc::reader::StreamReader;
    use http::{Request, StatusCode};
    use serde_json::json;
    use std::io::Cursor;
    use std::path::PathBuf;
    use std::sync::Arc;
    use uuid::Uuid;

    fn repo_root() -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .unwrap()
            .to_path_buf()
    }

    fn temp_bronze_db() -> PathBuf {
        std::env::temp_dir().join(format!("bronze_k12_test_{}.db", Uuid::new_v4().simple()))
    }

    #[test]
    fn test_engine_denies_filesystem_reads_missing_from_blocklist() {
        // ``parquet_metadata`` is deliberately absent from FORBIDDEN_FUNCTIONS,
        // so the SQL blocklist alone lets this through — it stats an arbitrary
        // Parquet file and leaks its row counts and schema. It must be refused
        // by the DuckDB-level lock instead (enable_external_access = false).
        let secret = std::env::temp_dir().join(format!(
            "medallion_sandbox_probe_{}.parquet",
            Uuid::new_v4().simple()
        ));
        let secret_escaped = secret.to_string_lossy().replace('\'', "''");
        {
            let conn = duckdb::Connection::open_in_memory().unwrap();
            conn.execute_batch(&format!(
                "COPY (SELECT 42 AS leaked_col) TO '{secret_escaped}' (FORMAT parquet);"
            ))
            .unwrap();
        }

        let bronze_path = temp_bronze_db();
        let engine = MedallionEngine::new(&bronze_path, None).unwrap();
        let read_sql = format!("SELECT * FROM parquet_metadata('{secret_escaped}')");

        let result = engine.execute_and_cache_arrow(&read_sql, None);
        match result {
            Ok(entry) => panic!(
                "engine read a file outside the warehouse (status={}): {}",
                entry.summary.status, read_sql
            ),
            Err(err) => assert!(
                err.message.to_lowercase().contains("permission")
                    || err.message.to_lowercase().contains("external access"),
                "expected a permission failure from the DuckDB sandbox, got: {} ({})",
                err.error_type,
                err.message
            ),
        }

        let _ = std::fs::remove_file(&secret);
        let _ = std::fs::remove_file(&bronze_path);
    }

    #[test]
    fn test_rust_top_k_schema_pruner_and_gbnf_compiler() {
        let catalog = load_unified_schema(&repo_root());
        assert_eq!(catalog.len(), 20);

        let edu_q = "What is the average attendance rate for English Learners in 2023-2024?";
        let pruned_edu = select_top_k_tables(edu_q, &catalog, 5);
        assert_eq!(pruned_edu.len(), 5);
        assert!(pruned_edu.contains_key("main_core.fact_attendance"));
        assert!(pruned_edu.contains_key("main_core.dim_students"));

        let cde_q = "Compare chronic absenteeism and suspension rates across schools in 2023-24.";
        let pruned_cde = select_top_k_tables(cde_q, &catalog, 5);
        assert_eq!(pruned_cde.len(), 5);
        assert!(pruned_cde.contains_key("main_analytics.mart_cde_school_accountability"));

        let ddl = format_pruned_ddl(&pruned_cde);
        // Full column lists must match the training-time prompt format exactly.
        assert!(ddl.len() < 7000);

        let hop1 = compile_hop1_gbnf();
        assert!(hop1.contains("execute_duckdb_query"));

        let cols = vec![
            "academic_year".to_string(),
            "school_name".to_string(),
            "avg_attendance_rate".to_string(),
        ];
        let hop2 = compile_hop2_gbnf(&cols);
        assert!(hop2.contains("render_workspace_ui"));
        assert!(hop2.contains(
            r#"column-name ::= "\"academic_year\"" | "\"school_name\"" | "\"avg_attendance_rate\"""#
        ));
    }

    #[test]
    fn test_medallion_sqlite_to_duckdb_and_arrow_ipc_protocol() {
        let bronze_path = temp_bronze_db();
        let engine = Arc::new(MedallionEngine::new(&bronze_path, None).unwrap());

        let sql = r#"
            SELECT academic_year, school_name, ROUND(AVG(avg_attendance_rate), 4) AS avg_attendance_rate
            FROM main_analytics.school_summary
            GROUP BY 1, 2
            ORDER BY 1 ASC, 3 DESC
        "#;
        let entry = engine
            .execute_and_cache_arrow(sql, Some("q_school_summary_01".to_string()))
            .unwrap();

        assert_eq!(entry.summary.status, "ok");
        assert_eq!(entry.summary.query_id, "q_school_summary_01");
        assert_eq!(entry.summary.row_count, 16);
        assert_eq!(entry.summary.columns.len(), 3);
        assert!(!entry.arrow_ipc_bytes.is_empty());

        // Test custom `arrow://` protocol handler and verify zero-copy Arrow IPC StreamReader decoding
        let req = Request::builder()
            .uri("arrow://q_school_summary_01")
            .body(Vec::new())
            .unwrap();
        let resp = handle_arrow_protocol_request(req, &engine);
        assert_eq!(resp.status(), StatusCode::OK);
        assert_eq!(
            resp.headers().get("Content-Type").unwrap(),
            "application/vnd.apache.arrow.stream"
        );

        let cursor = Cursor::new(resp.body().as_ref());
        let reader = StreamReader::try_new(cursor, None).unwrap();
        let decoded_rows: usize = reader.map(|b| b.unwrap().num_rows()).sum();
        assert_eq!(decoded_rows, 16);

        let _ = std::fs::remove_file(&bronze_path);
    }

    #[test]
    fn test_zero_llm_parameterized_filter_bar_cte_and_self_healing_error() {
        let bronze_path = temp_bronze_db();
        let engine = Arc::new(MedallionEngine::new(&bronze_path, None).unwrap());

        let base_sql = "SELECT academic_year, school_name, total_students FROM main_analytics.school_summary ORDER BY academic_year ASC";
        let initial = engine
            .execute_and_cache_arrow(base_sql, Some("q_base".to_string()))
            .unwrap();
        assert_eq!(initial.summary.row_count, 16);

        let filters = vec![
            FilterSpec {
                column: "academic_year".to_string(),
                control_type: "date_range".to_string(),
                min: Some(json!("2022-2023")),
                max: Some(json!("2023-2024")),
                values: None,
                value: None,
                query: None,
            },
            FilterSpec {
                column: "school_name".to_string(),
                control_type: "multi_select".to_string(),
                min: None,
                max: None,
                values: Some(vec![
                    json!("Lincoln High School"),
                    json!("Roosevelt Middle School"),
                ]),
                value: None,
                query: None,
            },
        ];

        let filtered = engine.apply_query_filters("q_base", &filters).unwrap();
        assert_eq!(filtered.summary.row_count, 4);

        // Verify BinderError preserves Candidate bindings for Hop 1b self-healing
        let bad_err = engine
            .execute_and_cache_arrow(
                "SELECT year_label, school_name FROM main_analytics.school_summary",
                None,
            )
            .unwrap_err();
        assert_eq!(bad_err.error_type, "BinderError");
        assert!(bad_err.message.contains("Candidate bindings"));

        let _ = std::fs::remove_file(&bronze_path);
    }

    #[test]
    fn test_bronze_acid_ingestion_and_school_name_override_sync() {
        let bronze_path = temp_bronze_db();
        let catalog = load_unified_schema(&repo_root());
        let engine = Arc::new(MedallionEngine::new(&bronze_path, None).unwrap());

        // Ingest a new attendance record into Bronze SQLite via IPC JSON-RPC
        let ingest_msg = json!({
            "request_id": "req_1",
            "cmd": "ingest_bronze_attendance",
            "attendance": BronzeAttendanceInput {
                student_id_hash: "stu_999".to_string(),
                school_id: "1".to_string(),
                academic_year: "2024-2025".to_string(),
                days_enrolled: 180,
                days_present: 171,
                days_absent: 9,
                unexcused_absences: 2,
                attendance_rate: 0.95,
            }
        });
        let resp = handle_ipc_message(&ingest_msg.to_string(), &engine, &catalog);
        assert_eq!(resp["status"], "ok");

        // Override the school display name in Bronze SQLite and verify Silver/Gold tables update automatically
        let override_msg = json!({
            "request_id": "req_2",
            "cmd": "override_school_name",
            "school_id": "1",
            "override_school_name": "Abraham Lincoln High School"
        });
        let resp2 = handle_ipc_message(&override_msg.to_string(), &engine, &catalog);
        assert_eq!(resp2["status"], "ok");

        let check = engine
            .execute_and_cache_arrow(
                "SELECT school_name FROM main_core.dim_schools WHERE school_id = '1'",
                None,
            )
            .unwrap();
        assert_eq!(check.summary.row_count, 1);
        assert_eq!(
            check.summary.sample_rows[0][0],
            json!("Abraham Lincoln High School")
        );

        assert_eq!(
            parse_arrow_query_id("http://arrow.localhost/q_8f3a19?ts=1"),
            "q_8f3a19"
        );
        let _ = std::fs::remove_file(&bronze_path);
    }

    #[test]
    fn test_education_warehouse_attachment_and_cross_domain_queries() {
        let bronze_path = temp_bronze_db();
        let edu_wh = repo_root()
            .join("oss_framework")
            .join("data")
            .join("analytics.duckdb");
        if !edu_wh.exists() {
            return;
        }
        let engine = Arc::new(MedallionEngine::new(&bronze_path, Some(&edu_wh)).unwrap());

        let edu_entry = engine
            .execute_and_cache_arrow(
                "SELECT academic_year, COUNT(DISTINCT student_id_hash) AS total_students FROM main_core.dim_students GROUP BY 1 ORDER BY 1",
                Some("q_edu_01".to_string()),
            )
            .unwrap();
        assert_eq!(edu_entry.summary.status, "ok");
        assert!(edu_entry.summary.row_count >= 1);
        assert!(!edu_entry.arrow_ipc_bytes.is_empty());

        let _ = std::fs::remove_file(&bronze_path);
    }

    struct SelfHealingMockSlm;

    impl super::agent_loop::SlmBackend for SelfHealingMockSlm {
        fn generate_with_grammar(
            &self,
            chatml_prompt: &str,
            gbnf_grammar: &str,
            hop: super::agent_loop::GenerationHop,
        ) -> anyhow::Result<String> {
            match hop {
                super::agent_loop::GenerationHop::Hop1Sql { retry_attempt: 0 } => {
                    assert!(gbnf_grammar.contains("execute_duckdb_query"));
                    // Intentionally emit a non-existent column `school_year` on attempt 0
                    Ok(serde_json::to_string(&json!({
                        "tool": "execute_duckdb_query",
                        "arguments": {
                            "explanation": "Initial attempt with wrong column name.",
                            "sql": "SELECT school_year, school_name, total_students FROM main_analytics.school_summary"
                        }
                    }))?)
                }
                super::agent_loop::GenerationHop::Hop1Sql { retry_attempt: 1 } => {
                    // Verify that DuckDB's Candidate bindings hint was injected into the ChatML KV context
                    assert!(chatml_prompt.contains("Candidate bindings"));
                    assert!(chatml_prompt.contains("academic_year"));
                    Ok(serde_json::to_string(&json!({
                        "tool": "execute_duckdb_query",
                        "arguments": {
                            "explanation": "Self-healed query using academic_year.",
                            "sql": "SELECT academic_year, school_name, total_students FROM main_analytics.school_summary ORDER BY 1 ASC"
                        }
                    }))?)
                }
                super::agent_loop::GenerationHop::Hop2Ui => {
                    // Verify dynamic Hop 2 GBNF restricted column-name to the exact output columns
                    assert!(gbnf_grammar.contains(r#"column-name ::= "\"academic_year\"" | "\"school_name\"" | "\"total_students\"""#));
                    Ok(serde_json::to_string(&json!({
                        "tool": "render_workspace_ui",
                        "arguments": {
                            "title": "Multi-Year School Enrollment",
                            "narrative_summary": "Self-healed two-hop execution succeeded.",
                            "components": [
                                {
                                    "component": "TimeSeriesChart",
                                    "chart_variant": "stacked_bar",
                                    "x_column": "academic_year",
                                    "y_columns": ["total_students"],
                                    "series_column": "school_name",
                                    "value_format": "integer"
                                },
                                {
                                    "component": "DataTable",
                                    "columns": ["academic_year", "school_name", "total_students"]
                                }
                            ]
                        }
                    }))?)
                }
                _ => unreachable!(),
            }
        }
    }

    #[test]
    fn test_two_hop_agent_loop_with_self_healing_retry() {
        let bronze_path = temp_bronze_db();
        let catalog = load_unified_schema(&repo_root());
        let engine = Arc::new(MedallionEngine::new(&bronze_path, None).unwrap());
        let mock_slm = SelfHealingMockSlm;

        let trace = super::agent_loop::run_two_hop_agent_loop(
            "Compare school enrollment trends across academic years.",
            &engine,
            &catalog,
            &mock_slm,
            5,
            2,
        )
        .unwrap();

        assert_eq!(trace.retries_used, 1);
        assert_eq!(trace.self_healing_errors.len(), 1);
        assert_eq!(trace.self_healing_errors[0].error_type, "BinderError");
        assert_eq!(trace.result_summary.row_count, 16);
        assert_eq!(trace.hop2_call["tool"], json!("render_workspace_ui"));

        let _ = std::fs::remove_file(&bronze_path);
    }
}
