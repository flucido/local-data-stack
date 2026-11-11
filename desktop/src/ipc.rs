use crate::agent_loop::{run_two_hop_agent_loop, DeterministicTwoHopBackend};
use crate::medallion::{BronzeAttendanceInput, FilterSpec, MedallionEngine};
use crate::schema_pruner::{
    compile_hop1_gbnf, compile_hop2_gbnf, format_pruned_ddl, select_top_k_tables, SchemaCatalog,
};
use http::{Request, Response, StatusCode};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::borrow::Cow;
use std::sync::Arc;

#[derive(Debug, Deserialize)]
#[serde(tag = "cmd", rename_all = "snake_case")]
pub enum IpcCommand {
    RunPrompt {
        prompt: String,
        #[serde(default)]
        top_k: Option<usize>,
        #[serde(default)]
        max_retries: Option<usize>,
    },
    GetSchemaCatalog {
        #[serde(default)]
        question: Option<String>,
        #[serde(default)]
        top_k: Option<usize>,
    },
    ExecuteDuckdbQuery {
        sql: String,
        #[serde(default)]
        query_id: Option<String>,
    },
    ApplyQueryFilters {
        query_id_or_sql: String,
        filters: Vec<FilterSpec>,
    },
    IngestBronzeAttendance {
        attendance: BronzeAttendanceInput,
    },
    OverrideSchoolName {
        school_id: String,
        override_school_name: String,
    },
}

#[derive(Debug, Serialize, Deserialize)]
pub struct IpcEnvelope {
    #[serde(default)]
    pub request_id: Option<String>,
    #[serde(flatten)]
    pub payload: Value,
}

pub fn handle_ipc_message(
    raw_json: &str,
    engine: &Arc<MedallionEngine>,
    catalog: &SchemaCatalog,
) -> Value {
    let parsed_val: Value = match serde_json::from_str(raw_json) {
        Ok(v) => v,
        Err(e) => {
            return json!({
                "status": "error",
                "error_type": "InvalidJsonRpc",
                "message": format!("Invalid JSON IPC message: {e}")
            });
        }
    };

    let request_id = parsed_val
        .get("request_id")
        .and_then(|v| v.as_str())
        .map(|s| s.to_string());

    let cmd: IpcCommand = match serde_json::from_value(parsed_val) {
        Ok(c) => c,
        Err(e) => {
            return json!({
                "request_id": request_id,
                "status": "error",
                "error_type": "InvalidCommand",
                "message": format!("Unsupported IPC command payload: {e}")
            });
        }
    };

    let mut resp = match cmd {
        IpcCommand::RunPrompt {
            prompt,
            top_k,
            max_retries,
        } => {
            let slm = DeterministicTwoHopBackend;
            match run_two_hop_agent_loop(
                &prompt,
                engine,
                catalog,
                &slm,
                top_k.unwrap_or(5),
                max_retries.unwrap_or(2),
            ) {
                Ok(trace) => serde_json::to_value(trace).unwrap_or_else(|_| json!({"status": "error"})),
                Err(e) => json!({
                    "status": "error",
                    "error_type": "AgentLoopError",
                    "message": e.to_string()
                }),
            }
        }

        IpcCommand::GetSchemaCatalog { question, top_k } => {
            let k = top_k.unwrap_or(5);
            let selected = if let Some(q) = question.as_deref() {
                if !q.trim().is_empty() {
                    select_top_k_tables(q, catalog, k)
                } else {
                    catalog.clone()
                }
            } else {
                catalog.clone()
            };
            let ddl = format_pruned_ddl(&selected);
            json!({
                "status": "ok",
                "table_count": selected.len(),
                "tables": selected,
                "pruned_ddl": ddl,
                "hop1_gbnf": compile_hop1_gbnf(),
            })
        }

        IpcCommand::ExecuteDuckdbQuery { sql, query_id } => {
            match engine.execute_and_cache_arrow(&sql, query_id) {
                Ok(entry) => {
                    let col_names: Vec<String> = entry
                        .summary
                        .columns
                        .iter()
                        .map(|c| c.name.clone())
                        .collect();
                    let hop2_gbnf = compile_hop2_gbnf(&col_names);
                    json!({
                        "status": "ok",
                        "arrow_uri": format!("arrow://{}", entry.query_id),
                        "arrow_byte_len": entry.arrow_ipc_bytes.len(),
                        "result_summary": entry.summary,
                        "hop2_gbnf": hop2_gbnf,
                    })
                }
                Err(err) => serde_json::to_value(err).unwrap_or_else(|_| {
                    json!({
                        "status": "error",
                        "error_type": "ExecutionError",
                        "message": "Unknown query error"
                    })
                }),
            }
        }

        IpcCommand::ApplyQueryFilters {
            query_id_or_sql,
            filters,
        } => match engine.apply_query_filters(&query_id_or_sql, &filters) {
            Ok(entry) => {
                json!({
                    "status": "ok",
                    "arrow_uri": format!("arrow://{}", entry.query_id),
                    "arrow_byte_len": entry.arrow_ipc_bytes.len(),
                    "result_summary": entry.summary,
                })
            }
            Err(err) => serde_json::to_value(err).unwrap_or_else(|_| {
                json!({
                    "status": "error",
                    "error_type": "ExecutionError",
                    "message": "Unknown filter error"
                })
            }),
        },

        IpcCommand::IngestBronzeAttendance { attendance } => {
            match engine.ingest_bronze_attendance(&attendance) {
                Ok(()) => json!({
                    "status": "ok",
                    "student_id_hash": attendance.student_id_hash,
                    "academic_year": attendance.academic_year
                }),
                Err(e) => json!({
                    "status": "error",
                    "error_type": "BronzeWriteError",
                    "message": e.to_string()
                }),
            }
        }

        IpcCommand::OverrideSchoolName {
            school_id,
            override_school_name,
        } => match engine.set_school_name_override(&school_id, &override_school_name) {
            Ok(()) => json!({
                "status": "ok",
                "school_id": school_id,
                "override_school_name": override_school_name
            }),
            Err(e) => json!({
                "status": "error",
                "error_type": "BronzeWriteError",
                "message": e.to_string()
            }),
        },
    };

    if let (Some(req_id), Some(obj)) = (request_id, resp.as_object_mut()) {
        obj.insert("request_id".to_string(), json!(req_id));
    }
    resp
}

/// Extract the `query_id` from a custom `arrow://` protocol URI such as:
///   - `arrow://q_8f3a19`
///   - `arrow://localhost/q_8f3a19`
///   - `http://arrow.localhost/q_8f3a19`
pub fn parse_arrow_query_id(uri_str: &str) -> String {
    let trimmed = uri_str
        .trim()
        .trim_start_matches("arrow://")
        .trim_start_matches("http://arrow.localhost/")
        .trim_start_matches("https://arrow.localhost/")
        .trim_start_matches("localhost/")
        .trim_matches('/');
    trimmed
        .split('?')
        .next()
        .unwrap_or("")
        .trim_matches('/')
        .to_string()
}

pub fn handle_arrow_protocol_request(
    request: Request<Vec<u8>>,
    engine: &Arc<MedallionEngine>,
) -> Response<Cow<'static, [u8]>> {
    let query_id = parse_arrow_query_id(&request.uri().to_string());
    if let Some(entry) = engine.arrow_cache.get(&query_id) {
        Response::builder()
            .status(StatusCode::OK)
            .header("Content-Type", "application/vnd.apache.arrow.stream")
            .header("Access-Control-Allow-Origin", "*")
            .header("X-Query-Id", entry.query_id)
            .header("X-Row-Count", entry.summary.row_count.to_string())
            .body(Cow::Owned((*entry.arrow_ipc_bytes).clone()))
            .unwrap()
    } else {
        let body = serde_json::to_vec(&json!({
            "status": "error",
            "error_type": "QueryIdNotFound",
            "message": format!("No cached Arrow stream for query_id '{query_id}'")
        }))
        .unwrap_or_default();
        Response::builder()
            .status(StatusCode::NOT_FOUND)
            .header("Content-Type", "application/json")
            .header("Access-Control-Allow-Origin", "*")
            .body(Cow::Owned(body))
            .unwrap()
    }
}
