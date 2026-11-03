use crate::medallion::{DuckDBExecutionError, DuckDBResultSummary, MedallionEngine};
use crate::schema_pruner::{
    compile_hop1_gbnf, compile_hop2_gbnf, format_pruned_ddl, select_top_k_tables, SchemaCatalog,
};
use anyhow::{anyhow, Result};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::sync::Arc;
use std::time::Instant;

pub const TWO_HOP_SYSTEM_INSTRUCTIONS: &str = r#"You are a sovereign local-first analytical SQL and Generative UI agent.
You operate in a strict Two-Hop Tool-Calling Protocol:
- Hop 1: Emit ONLY a JSON tool call to `execute_duckdb_query` with `explanation` and a valid read-only DuckDB `sql` query (`SELECT` or `WITH`).
- Hop 1b (if `duckdb_execution_error` is returned): Read the `Candidate bindings` hint carefully and emit a corrected `execute_duckdb_query` tool call.
- Hop 2 (after `duckdb_result_summary` is returned): Emit ONLY a JSON tool call to `render_workspace_ui` selecting 1 to 4 components (`KPIGrid`, `TimeSeriesChart`, `CategoryBarChart`, `BudgetVarianceChart`, `DataTable`, `FilterBar`) bound strictly to the returned column names."#;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum GenerationHop {
    Hop1Sql { retry_attempt: usize },
    Hop2Ui,
}

/// Pluggable Small Language Model inference trait supporting in-process `llama.cpp` FFI,
/// local `llama-server` HTTP with `cache_prompt: true` + `grammar`, or deterministic test mocks.
pub trait SlmBackend: Send + Sync {
    fn generate_with_grammar(
        &self,
        chatml_prompt: &str,
        gbnf_grammar: &str,
        hop: GenerationHop,
    ) -> Result<String>;
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TwoHopExecutionTrace {
    pub question: String,
    pub pruned_tables: Vec<String>,
    pub hop1_call: Value,
    pub self_healing_errors: Vec<DuckDBExecutionError>,
    pub retries_used: usize,
    pub arrow_uri: String,
    pub arrow_byte_len: usize,
    pub result_summary: DuckDBResultSummary,
    pub hop2_call: Value,
    pub total_latency_ms: f64,
}

/// Format a ChatML turn block (`<|im_start|>role\ncontent<|im_end|>\n`).
pub fn format_chatml_turn(role: &str, content: &str) -> String {
    format!("<|im_start|>{role}\n{content}<|im_end|>\n")
}

/// Build the initial ChatML prefix (`system` + `pruned_ddl` + `user`) evaluated in the KV cache.
pub fn build_hop1_chatml_prefix(question: &str, pruned_ddl: &str) -> String {
    let sys_body = format!("{TWO_HOP_SYSTEM_INSTRUCTIONS}\n\n{pruned_ddl}");
    let mut prompt = String::new();
    prompt.push_str(&format_chatml_turn("system", &sys_body));
    prompt.push_str(&format_chatml_turn("user", question));
    prompt.push_str("<|im_start|>assistant\n");
    prompt
}

/// Append a tool output (`duckdb_execution_error` or `duckdb_result_summary`) onto the active
/// ChatML conversation buffer so `llama.cpp` reuses the existing KV cache prefix.
pub fn append_tool_response_chatml(
    active_conversation: &mut String,
    assistant_json: &str,
    tool_payload: &Value,
) {
    active_conversation.push_str(assistant_json.trim());
    active_conversation.push_str("<|im_end|>\n");
    let tool_str = serde_json::to_string(tool_payload).unwrap_or_else(|_| "{}".to_string());
    active_conversation.push_str(&format_chatml_turn("tool", &tool_str));
    active_conversation.push_str("<|im_start|>assistant\n");
}

/// Execute the full Two-Hop + Self-Healing Agent Loop:
///   1. Top-K Schema Pruning (`k = top_k`)
///   2. Hop 1 SQL generation constrained by `hop1_sql.gbnf`
///   3. In-process DuckDB execution with up to `max_retries` (default 2) Hop 1b self-healing retries
///   4. Hop 2 Generative UI selection constrained by dynamic `compile_hop2_gbnf(output_columns)`
pub fn run_two_hop_agent_loop(
    question: &str,
    engine: &Arc<MedallionEngine>,
    catalog: &SchemaCatalog,
    slm: &dyn SlmBackend,
    top_k: usize,
    max_retries: usize,
) -> Result<TwoHopExecutionTrace> {
    let start = Instant::now();

    // Step 1: Top-K Schema Pruning (<800 tokens DDL)
    let pruned_catalog = select_top_k_tables(question, catalog, top_k.max(1));
    let pruned_tables: Vec<String> = pruned_catalog.keys().cloned().collect();
    let pruned_ddl = format_pruned_ddl(&pruned_catalog);

    // Step 2: Assemble KV-Cached ChatML Prefix
    let mut chatml_context = build_hop1_chatml_prefix(question, &pruned_ddl);
    let hop1_gbnf = compile_hop1_gbnf();

    let mut self_healing_errors: Vec<DuckDBExecutionError> = Vec::new();
    let mut final_hop1_call: Option<Value> = None;
    let mut cached_entry = None;

    // Step 3: Hop 1 + Hop 1b Self-Healing SQL Loop (capped at max_retries)
    for attempt in 0..=max_retries {
        let raw_hop1 = slm.generate_with_grammar(
            &chatml_context,
            &hop1_gbnf,
            GenerationHop::Hop1Sql {
                retry_attempt: attempt,
            },
        )?;

        let parsed_hop1: Value = serde_json::from_str(raw_hop1.trim()).map_err(|e| {
            anyhow!("Hop 1 output violated JSON grammar on attempt {attempt}: {e}")
        })?;

        match engine.execute_and_cache_arrow(&raw_hop1, None) {
            Ok(entry) => {
                // Append successful Hop 1 assistant turn + duckdb_result_summary onto KV cache
                let summary_val = serde_json::to_value(&entry.summary)?;
                append_tool_response_chatml(&mut chatml_context, &raw_hop1, &summary_val);
                final_hop1_call = Some(parsed_hop1);
                cached_entry = Some(entry);
                break;
            }
            Err(duck_err) => {
                self_healing_errors.push(duck_err.clone());
                if attempt == max_retries {
                    return Err(anyhow!(
                        "SQL execution failed after {} self-healing retries: {} ({})",
                        max_retries,
                        duck_err.message,
                        duck_err.error_type
                    ));
                }
                let err_val = serde_json::to_value(&duck_err)?;
                append_tool_response_chatml(&mut chatml_context, &raw_hop1, &err_val);
            }
        }
    }

    let entry = cached_entry.ok_or_else(|| anyhow!("Missing cached query entry after Hop 1"))?;
    let hop1_call = final_hop1_call.unwrap_or_else(|| json!({}));

    // Step 4: Compile dynamic Hop 2 GBNF with exact DuckDB output columns
    let output_cols: Vec<String> = entry
        .summary
        .columns
        .iter()
        .map(|c| c.name.clone())
        .collect();
    let hop2_gbnf = compile_hop2_gbnf(&output_cols);

    // Step 5: Sample Hop 2 (`render_workspace_ui`) reusing the active KV-cached conversation
    let raw_hop2 = slm.generate_with_grammar(&chatml_context, &hop2_gbnf, GenerationHop::Hop2Ui)?;
    let hop2_call: Value = serde_json::from_str(raw_hop2.trim())
        .map_err(|e| anyhow!("Hop 2 output violated JSON grammar: {e}"))?;

    // Verify Hop 2 column bindings against output_cols
    validate_hop2_column_bindings(&hop2_call, &output_cols)?;

    let total_latency_ms = (start.elapsed().as_secs_f64() * 1000.0 * 100.0).round() / 100.0;

    Ok(TwoHopExecutionTrace {
        question: question.to_string(),
        pruned_tables,
        hop1_call,
        retries_used: self_healing_errors.len(),
        self_healing_errors,
        arrow_uri: format!("arrow://{}", entry.query_id),
        arrow_byte_len: entry.arrow_ipc_bytes.len(),
        result_summary: entry.summary,
        hop2_call,
        total_latency_ms,
    })
}

pub fn validate_hop2_column_bindings(hop2_call: &Value, allowed_columns: &[String]) -> Result<()> {
    if hop2_call.get("tool").and_then(|t| t.as_str()) != Some("render_workspace_ui") {
        return Err(anyhow!("Hop 2 tool must be 'render_workspace_ui'"));
    }
    let components = hop2_call
        .get("arguments")
        .and_then(|a| a.get("components"))
        .and_then(|c| c.as_array())
        .ok_or_else(|| anyhow!("Hop 2 'arguments.components' must be an array"))?;

    if components.is_empty() || components.len() > 4 {
        return Err(anyhow!("Hop 2 must contain 1 to 4 components"));
    }

    let check_col = |col: &str, ctx: &str| -> Result<()> {
        if !allowed_columns.is_empty() && !allowed_columns.iter().any(|c| c == col) {
            return Err(anyhow!(
                "{ctx}: column '{col}' is not in query output columns {allowed_columns:?}"
            ));
        }
        Ok(())
    };

    for (idx, comp) in components.iter().enumerate() {
        let comp_type = comp
            .get("component")
            .and_then(|c| c.as_str())
            .unwrap_or("");
        let ctx = format!("components[{idx}] ({comp_type})");
        match comp_type {
            "KPIGrid" => {
                if let Some(metrics) = comp.get("metrics").and_then(|m| m.as_array()) {
                    for m in metrics {
                        if let Some(vc) = m.get("value_column").and_then(|v| v.as_str()) {
                            check_col(vc, &ctx)?;
                        }
                        if let Some(dc) = m.get("delta_column").and_then(|v| v.as_str()) {
                            check_col(dc, &ctx)?;
                        }
                    }
                }
            }
            "TimeSeriesChart" => {
                if let Some(xc) = comp.get("x_column").and_then(|v| v.as_str()) {
                    check_col(xc, &ctx)?;
                }
                if let Some(ycols) = comp.get("y_columns").and_then(|v| v.as_array()) {
                    for yc in ycols.iter().filter_map(|v| v.as_str()) {
                        check_col(yc, &ctx)?;
                    }
                }
                if let Some(sc) = comp.get("series_column").and_then(|v| v.as_str()) {
                    check_col(sc, &ctx)?;
                }
            }
            "CategoryBarChart" => {
                if let Some(cc) = comp.get("category_column").and_then(|v| v.as_str()) {
                    check_col(cc, &ctx)?;
                }
                if let Some(vcols) = comp.get("value_columns").and_then(|v| v.as_array()) {
                    for vc in vcols.iter().filter_map(|v| v.as_str()) {
                        check_col(vc, &ctx)?;
                    }
                }
            }
            "BudgetVarianceChart" => {
                for field in ["category_column", "actual_column", "budget_column", "variance_column"] {
                    if let Some(c) = comp.get(field).and_then(|v| v.as_str()) {
                        check_col(c, &ctx)?;
                    }
                }
            }
            "DataTable" => {
                if let Some(cols) = comp.get("columns").and_then(|v| v.as_array()) {
                    for c in cols.iter().filter_map(|v| v.as_str()) {
                        check_col(c, &ctx)?;
                    }
                }
            }
            "FilterBar" => {
                if let Some(ctrls) = comp.get("controls").and_then(|v| v.as_array()) {
                    for ctrl in ctrls {
                        if let Some(c) = ctrl.get("column").and_then(|v| v.as_str()) {
                            check_col(c, &ctx)?;
                        }
                    }
                }
            }
            other => {
                return Err(anyhow!("Unknown component type '{other}'"));
            }
        }
    }
    Ok(())
}

/// Deterministic Heuristic Two-Hop Backend used when no GGUF server is attached or during offline smoke tests.
pub struct DeterministicTwoHopBackend;

impl SlmBackend for DeterministicTwoHopBackend {
    fn generate_with_grammar(
        &self,
        chatml_prompt: &str,
        _gbnf_grammar: &str,
        hop: GenerationHop,
    ) -> Result<String> {
        let lower = chatml_prompt.to_lowercase();
        match hop {
            GenerationHop::Hop1Sql { .. } => {
                let (explanation, sql) = if lower.contains("subgroup") || lower.contains("accountability") {
                    (
                        "Compare chronic absenteeism and suspension rates across CDE reporting categories in 2023-24.",
                        "SELECT reporting_category_label, ROUND(AVG(ca_chronic_absent_rate_pct), 2) AS avg_chronic_absent_rate, ROUND(AVG(su_suspension_rate_pct), 2) AS avg_suspension_rate FROM main_analytics.mart_cde_school_accountability WHERE academic_year = '2023-24' GROUP BY reporting_category_label ORDER BY avg_chronic_absent_rate DESC",
                    )
                } else if lower.contains("race") || lower.contains("equity") {
                    (
                        "Compare student counts, average GPA, and attendance rates by racial group in 2023-2024.",
                        "SELECT primary_race, student_count, avg_gpa, avg_attendance_rate, incident_count FROM main_analytics.equity_by_race WHERE academic_year = '2023-2024' ORDER BY student_count DESC",
                    )
                } else if lower.contains("english learner") {
                    (
                        "Calculate average attendance rate for English Learners in 2023-2024.",
                        "SELECT ROUND(AVG(a.attendance_rate), 4) AS avg_attendance_rate FROM main_core.fact_attendance a JOIN main_core.dim_students s ON a.student_id_hash = s.student_id_hash AND a.academic_year = s.academic_year WHERE a.academic_year = '2023-2024' AND s.ell_status = TRUE",
                    )
                } else {
                    (
                        "Compare school enrollment, average GPA, and attendance rate trends across academic years.",
                        "SELECT academic_year, school_name, total_students, avg_gpa, avg_attendance_rate FROM main_analytics.school_summary ORDER BY academic_year ASC, total_students DESC",
                    )
                };
                Ok(serde_json::to_string(&json!({
                    "tool": "execute_duckdb_query",
                    "arguments": {
                        "explanation": explanation,
                        "sql": sql
                    }
                }))?)
            }
            GenerationHop::Hop2Ui => {
                // Inspect the injected duckdb_result_summary in the last tool turn to synthesize a valid Hop 2 UI call
                let ui_call = synthesize_hop2_from_chatml(chatml_prompt);
                Ok(serde_json::to_string(&ui_call)?)
            }
        }
    }
}

pub fn synthesize_hop2_from_chatml(chatml_prompt: &str) -> Value {
    // Parse the last `<|im_start|>tool\n{...}<|im_end|>` block
    let mut last_summary: Option<DuckDBResultSummary> = None;
    for segment in chatml_prompt.rsplit("<|im_start|>tool\n") {
        if let Some(end_idx) = segment.find("<|im_end|>") {
            let json_slice = &segment[..end_idx];
            if let Ok(parsed) = serde_json::from_str::<DuckDBResultSummary>(json_slice) {
                last_summary = Some(parsed);
                break;
            }
        }
    }

    if let Some(summary) = last_summary {
        let col_names: Vec<String> = summary.columns.iter().map(|c| c.name.clone()).collect();
        if summary.row_count == 1 && !col_names.is_empty() {
            let val_col = col_names.last().unwrap().clone();
            return json!({
                "tool": "render_workspace_ui",
                "arguments": {
                    "title": "Scalar KPI Summary",
                    "narrative_summary": format!("Single-row K-12 analytical summary for {}.", val_col),
                    "components": [
                        {
                            "component": "KPIGrid",
                            "metrics": [
                                {
                                    "label": val_col,
                                    "value_column": val_col,
                                    "value_format": "decimal"
                                }
                            ]
                        }
                    ]
                }
            });
        }

        if col_names.len() >= 2 {
            let first_col = col_names[0].clone();
            let last_col = col_names.last().unwrap().clone();
            let is_temporal = first_col.contains("month")
                || first_col.contains("date")
                || first_col.contains("year");
            let chart_comp = if is_temporal {
                json!({
                    "component": "TimeSeriesChart",
                    "chart_variant": "bar",
                    "x_column": first_col,
                    "y_columns": [last_col],
                    "value_format": "decimal"
                })
            } else {
                json!({
                    "component": "CategoryBarChart",
                    "chart_variant": "horizontal",
                    "category_column": first_col,
                    "value_columns": [last_col],
                    "value_format": "decimal"
                })
            };

            return json!({
                "tool": "render_workspace_ui",
                "arguments": {
                    "title": "K-12 Analytical Workspace Breakdown",
                    "narrative_summary": format!("Visualizing {} across {} ({} rows).", last_col, first_col, summary.row_count),
                    "components": [
                        {
                            "component": "FilterBar",
                            "controls": [
                                { "column": first_col, "control_type": "multi_select", "label": "Filter" }
                            ]
                        },
                        chart_comp,
                        {
                            "component": "DataTable",
                            "columns": col_names
                        }
                    ]
                }
            });
        }
    }

    json!({
        "tool": "render_workspace_ui",
        "arguments": {
            "title": "Analytical Result",
            "narrative_summary": "Query executed.",
            "components": []
        }
    })
}
