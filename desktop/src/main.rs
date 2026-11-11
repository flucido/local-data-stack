use anyhow::Result;
use local_data_stack_desktop::ipc::{handle_arrow_protocol_request, handle_ipc_message};
use local_data_stack_desktop::medallion::MedallionEngine;
use local_data_stack_desktop::schema_pruner::load_unified_schema;
use std::env;
use std::path::PathBuf;
use std::sync::Arc;
use tao::dpi::LogicalSize;
use tao::event::{Event, WindowEvent};
use tao::event_loop::{ControlFlow, EventLoopBuilder};
use tao::window::WindowBuilder;
use wry::WebViewBuilder;

enum UserEvent {
    IpcResponse(String),
}

fn resolve_repo_root() -> PathBuf {
    if let Ok(p) = env::var("LFED_REPO_ROOT") {
        return PathBuf::from(p);
    }
    let manifest = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    manifest.parent().unwrap_or(&manifest).to_path_buf()
}

fn build_webview_html(ui_dist_dir: &std::path::Path) -> String {
    let assets_dir = ui_dist_dir.join("assets");
    if let Ok(entries) = std::fs::read_dir(&assets_dir) {
        let mut css_bundle = String::new();
        let mut js_bundle = String::new();
        for entry in entries.flatten() {
            let path = entry.path();
            if let Some(ext) = path.extension().and_then(|e| e.to_str()) {
                if ext == "css" {
                    if let Ok(c) = std::fs::read_to_string(&path) {
                        css_bundle.push_str(&c);
                    }
                } else if ext == "js" {
                    if let Ok(j) = std::fs::read_to_string(&path) {
                        js_bundle.push_str(&j);
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
  <title>Sovereign Local-First Analytics & Generative UI Engine</title>
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

fn default_bootstrap_html() -> &'static str {
    r#"<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Sovereign Local-First Analytics & Generative UI Engine</title>
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
      <h2 style="margin: 0;">Sovereign Local-First Analytics & Generative UI Engine</h2>
      <p style="margin: 4px 0 0; color: #94a3b8; font-size: 14px;">
        Rust Host (Tao + Wry) • SQLite Bronze • DuckDB Silver/Gold • Zero-Copy <code>arrow://</code> IPC
      </p>
    </div>
    <span class="badge">Zero-Cloud • Local Engine Ready</span>
  </div>
  <div id="app">
    <pre id="status">Initializing Wry IPC bridge...</pre>
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

fn main() -> Result<()> {
    let args: Vec<String> = env::args().collect();
    let repo_root = resolve_repo_root();
    let bronze_path = repo_root.join("data").join("bronze_k12.db");
    let edu_warehouse = repo_root
        .join("oss_framework")
        .join("data")
        .join("analytics.duckdb");

    let catalog = Arc::new(load_unified_schema(&repo_root));
    let engine = Arc::new(MedallionEngine::new(
        &bronze_path,
        Some(edu_warehouse.as_path()),
    )?);

    if args.iter().any(|a| a == "--headless-self-test") {
        let entry = engine
            .execute_and_cache_arrow(
                "SELECT academic_year, school_name, total_students, avg_gpa, avg_attendance_rate FROM main_analytics.school_summary ORDER BY 1 ASC",
                Some("q_self_test".to_string()),
            )
            .map_err(|e| anyhow::anyhow!("{:?}", e))?;
        println!(
            "Headless self-test OK: query_id={}, rows={}, arrow_ipc_bytes={}, schema_tables={}",
            entry.query_id,
            entry.summary.row_count,
            entry.arrow_ipc_bytes.len(),
            catalog.len()
        );
        return Ok(());
    }

    let event_loop = EventLoopBuilder::<UserEvent>::with_user_event().build();
    let proxy = event_loop.create_proxy();

    let window = WindowBuilder::new()
        .with_title("Sovereign Local-First Analytics & Generative UI Engine")
        .with_inner_size(LogicalSize::new(1360.0, 860.0))
        .build(&event_loop)?;

    let engine_for_arrow = Arc::clone(&engine);
    let engine_for_ipc = Arc::clone(&engine);
    let catalog_for_ipc = Arc::clone(&catalog);

    let ui_dist_dir = repo_root.join("desktop").join("ui").join("dist");
    let html_content = build_webview_html(&ui_dist_dir);

    let webview = WebViewBuilder::new()
        .with_custom_protocol("arrow".into(), move |_webview_id, request| {
            handle_arrow_protocol_request(request, &engine_for_arrow)
        })
        .with_ipc_handler(move |req| {
            let body_bytes = req.body().as_bytes().to_vec();
            let engine = Arc::clone(&engine_for_ipc);
            let catalog = Arc::clone(&catalog_for_ipc);
            let proxy = proxy.clone();
            std::thread::spawn(move || {
                let body_str = String::from_utf8_lossy(&body_bytes);
                let resp_val = handle_ipc_message(&body_str, &engine, &catalog);
                if let Ok(resp_json) = serde_json::to_string(&resp_val) {
                    let _ = proxy.send_event(UserEvent::IpcResponse(resp_json));
                }
            });
        })
        .with_initialization_script(
            r#"
            window.__ipcCallbacks = {};
            window.__onRustIpcResponse = function(payload) {
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
            "#,
        )
        .with_html(html_content)
        .build(&window)?;

    event_loop.run(move |event, _, control_flow| {
        *control_flow = ControlFlow::Wait;
        match event {
            Event::WindowEvent {
                event: WindowEvent::CloseRequested,
                ..
            } => *control_flow = ControlFlow::Exit,
            Event::UserEvent(UserEvent::IpcResponse(json_str)) => {
                let js = format!("window.__onRustIpcResponse && window.__onRustIpcResponse({json_str});");
                let _ = webview.evaluate_script(&js);
            }
            _ => {}
        }
    });
}
