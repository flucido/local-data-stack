use crate::agent_loop::{run_two_hop_agent_loop, LocalSlmBackend};
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
            let slm = LocalSlmBackend::from_env();
            match run_two_hop_agent_loop(
                &prompt,
                engine,
                catalog,
                &slm,
                top_k.unwrap_or(5),
                max_retries.unwrap_or(2),
            ) {
                Ok(trace) => {
                    let mut val =
                        serde_json::to_value(&trace).unwrap_or_else(|_| json!({"status": "error"}));
                    if let Some(obj) = val.as_object_mut() {
                        obj.insert("status".to_string(), json!("ok"));
                        obj.insert("mode".to_string(), json!(trace.mode));
                    }
                    val
                }
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
            .header("Access-Control-Allow-Origin", "null")
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
            .header("Access-Control-Allow-Origin", "null")
            .body(Cow::Owned(body))
            .unwrap()
    }
}

pub const WEBVIEW_CSP_META: &str = r#"<meta http-equiv="Content-Security-Policy" content="default-src 'self' arrow: http://arrow.localhost; connect-src arrow: http://arrow.localhost; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline';" />"#;

pub fn is_allowed_webview_navigation(uri: &str) -> bool {
    uri.starts_with("about:")
        || uri.starts_with("data:")
        || uri.starts_with("arrow:")
        || uri.starts_with("http://localhost")
        || uri.starts_with("http://127.0.0.1")
}

pub fn build_webview_html_from_dist(ui_dist_dir: &std::path::Path) -> String {
    let assets_dir = ui_dist_dir.join("assets");
    if let Ok(entries) = std::fs::read_dir(&assets_dir) {
        let mut paths: Vec<std::path::PathBuf> =
            entries.flatten().map(|e| e.path()).collect();
        paths.sort();

        let mut css_bundle = String::new();
        let mut js_bundle = String::new();
        for path in paths {
            if let Some(ext) = path.extension().and_then(|e| e.to_str()) {
                if ext == "css" {
                    if let Ok(c) = std::fs::read_to_string(&path) {
                        css_bundle.push_str(&c);
                    }
                } else if ext == "js" {
                    if let Ok(j) = std::fs::read_to_string(&path) {
                        let escaped = j.replace("</script", "<\\/script");
                        js_bundle.push_str(&escaped);
                        js_bundle.push('\n');
                    }
                }
            }
        }
        if !js_bundle.is_empty() {
            return format!(
                r#"<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  {WEBVIEW_CSP_META}
  <title>District Student Analytics Workspace</title>
  <style>{css_bundle}</style>
</head>
<body>
  <div id="root"></div>
  <script type="module">{js_bundle}</script>
</body>
</html>"#
            );
        }
    }
    default_bootstrap_html().to_string()
}

pub fn default_bootstrap_html() -> &'static str {
    r#"<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta http-equiv="Content-Security-Policy" content="default-src 'self' arrow: http://arrow.localhost; connect-src arrow: http://arrow.localhost; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline';" />
  <title>District Student Analytics Workspace</title>
  <style>
    body {
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #0b0f19;
      color: #e2e8f0;
      padding: 24px;
    }
    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 1px solid #1e293b;
      padding-bottom: 16px;
      margin-bottom: 20px;
    }
    .badge {
      background: #065f46;
      color: #a7f3d0;
      padding: 4px 10px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 600;
    }
    pre {
      background: #111827;
      border: 1px solid #1f2937;
      border-radius: 8px;
      padding: 16px;
      overflow-x: auto;
      font-size: 13px;
    }
  </style>
</head>
<body>
  <div class="header">
    <div>
      <h2 style="margin: 0;">District Student Analytics Workspace</h2>
      <p style="margin: 4px 0 0; color: #94a3b8; font-size: 14px;">
        Private on-device school &amp; student insights
      </p>
    </div>
    <span class="badge">Offline • Ready</span>
  </div>
  <div id="app">
    <pre id="status">Initializing local data engine...</pre>
  </div>
  <script>
    window.__ipcCallbacks = {};
    window.__onRustIpcResponse = function(payload) {
      const statusEl = document.getElementById('status');
      if (statusEl) {
        statusEl.textContent = JSON.stringify(payload, null, 2);
      }
      if (payload && payload.request_id && window.__ipcCallbacks[payload.request_id]) {
        window.__ipcCallbacks[payload.request_id](payload);
        delete window.__ipcCallbacks[payload.request_id];
      }
      window.dispatchEvent(new CustomEvent('rust-ipc-message', { detail: payload }));
    };

    window.sendRustRpc = function(cmdObj) {
      const requestId = cmdObj.request_id || ('req_' + Math.random().toString(36).slice(2));
      const msg = Object.assign({}, cmdObj, { request_id: requestId });
      return new Promise((resolve, reject) => {
        const timer = setTimeout(() => {
          delete window.__ipcCallbacks[requestId];
          reject(new Error('Desktop query timed out after 30 seconds.'));
        }, 30000);
        window.__ipcCallbacks[requestId] = function(payload) {
          clearTimeout(timer);
          resolve(payload);
        };
        if (window.ipc && window.ipc.postMessage) {
          window.ipc.postMessage(JSON.stringify(msg));
        }
      });
    };

    window.addEventListener('DOMContentLoaded', () => {
      window.sendRustRpc({
        cmd: 'execute_duckdb_query',
        sql: 'SELECT academic_year, school_name, total_students, avg_gpa, avg_attendance_rate FROM main_analytics.school_summary ORDER BY academic_year ASC, total_students DESC'
      });
    });
  </script>
</body>
</html>"#
}
