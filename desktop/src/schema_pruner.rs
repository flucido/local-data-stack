use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet, HashMap, HashSet};
use std::fs;
use std::path::Path;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct TableColumn {
    pub name: String,
    #[serde(rename = "type")]
    pub data_type: String,
    #[serde(default)]
    pub description: String,
    #[serde(default)]
    pub sample_values: Vec<String>,
}

pub type SchemaCatalog = BTreeMap<String, Vec<TableColumn>>;

#[derive(Debug, Deserialize)]
struct TrainingSchemaFile {
    tables: BTreeMap<String, Vec<TableColumn>>,
}

const JOIN_KEYS: &[&str] = &[
    "student_id_hash",
    "cds_code",
    "school_id",
    "academic_year",
    "county_code",
    "district_code",
    "school_code",
    "reporting_category",
    "primary_race",
];

fn domain_synonyms(token: &str) -> &'static [&'static str] {
    match token {
        "absent" => &[
            "absenteeism",
            "chronic",
            "attendance",
            "days_absent",
            "ca_chronic_absent_rate_pct",
            "v_chronic_absenteeism_risk",
        ],
        "absenteeism" => &[
            "chronic",
            "attendance",
            "mart_cde_school_accountability",
            "stg_cde__chronic_absenteeism",
            "v_chronic_absenteeism_risk",
        ],
        "attendance" => &[
            "fact_attendance",
            "attendance_rate",
            "days_enrolled",
            "days_absent",
            "unexcused_absences",
        ],
        "suspend" | "suspension" => &[
            "discipline",
            "fact_discipline",
            "incident_type",
            "suspension_days",
            "su_suspension_rate_pct",
            "stg_cde__suspension",
            "mart_cde_school_accountability",
        ],
        "expel" | "expulsion" => &[
            "stg_cde__expulsion",
            "exp_total_expulsions",
            "mart_cde_school_accountability",
        ],
        "restraint" | "seclusion" => &[
            "stg_cde__restraint_seclusion",
            "mechanical_restraint_count",
            "physical_restraint_count",
            "seclusion_count",
        ],
        "meal" | "lunch" | "poverty" | "frpm" => &[
            "frpm",
            "free_reduced_lunch_flag",
            "frpm_free_pct_k12",
            "stg_cde__frpm",
        ],
        "homeless" | "dwelling" => &[
            "homeless_flag",
            "stg_cde__homeless_enrollment",
            "homeless_student_enrollment",
        ],
        "hispanic" | "race" | "ethnicity" | "equity" => &[
            "reporting_category",
            "ethnicity",
            "primary_race",
            "equity_by_race",
            "v_equity_outcomes_by_demographics",
            "rh",
        ],
        "english" | "learner" | "ell" => &[
            "ell_status",
            "home_language",
            "reporting_category",
            "el",
            "dim_student_demographics",
        ],
        "gpa" | "grade" | "course" => &[
            "fact_academic_records",
            "gpa_points",
            "grade_level",
            "course_id",
            "is_passing",
            "school_summary",
            "equity_by_race",
        ],
        "caspp" | "assessment" | "math" | "ela" | "proficiency" => &[
            "stg_cde__assessment_caspp",
            "pct_met_and_above",
            "pct_exceeded",
            "test_id",
            "mean_scale_score",
        ],
        "staff" | "teacher" => &[
            "stg_cde__staff_demo",
            "school_name",
            "district_name",
        ],
        "school" | "district" | "county" => &[
            "dim_schools",
            "school_summary",
            "mart_cde_school_accountability",
            "school_name",
            "county_name",
            "district_name",
        ],
        _ => &[],
    }
}

pub fn load_unified_schema(repo_root: &Path) -> SchemaCatalog {
    let mut catalog = SchemaCatalog::new();
    let schema_path = repo_root.join("training").join("training_schema.json");
    if let Ok(contents) = fs::read_to_string(&schema_path) {
        if let Ok(parsed) = serde_json::from_str::<TrainingSchemaFile>(&contents) {
            for (k, v) in parsed.tables {
                catalog.insert(k, v);
            }
        }
    }
    catalog
}

fn tokenize(text: &str) -> Vec<String> {
    let mut tokens = Vec::new();
    let lower = text.to_lowercase();
    for raw in lower.split(|c: char| !c.is_ascii_alphanumeric() && c != '_') {
        if raw.len() > 1 {
            tokens.push(raw.to_string());
            if raw.contains('_') {
                for part in raw.split('_') {
                    if part.len() > 1 {
                        tokens.push(part.to_string());
                    }
                }
            }
        }
    }
    tokens
}

fn expand_query_tokens(question: &str) -> Vec<String> {
    let base = tokenize(question);
    let mut expanded = base.clone();
    for tok in &base {
        for syn in domain_synonyms(tok) {
            expanded.extend(tokenize(syn));
        }
    }
    expanded
}

pub fn score_tables_bm25(question: &str, catalog: &SchemaCatalog) -> Vec<(String, f64)> {
    if catalog.is_empty() {
        return Vec::new();
    }
    let query_tokens = expand_query_tokens(question);
    let join_key_set: HashSet<&str> = JOIN_KEYS.iter().copied().collect();

    let mut table_docs: HashMap<String, Vec<String>> = HashMap::new();
    let mut table_join_keys: HashMap<String, BTreeSet<String>> = HashMap::new();
    let mut doc_freq: HashMap<String, usize> = HashMap::new();

    for (t_name, cols) in catalog {
        let mut doc = Vec::new();
        let t_toks = tokenize(t_name);
        for _ in 0..3 {
            doc.extend(t_toks.iter().cloned());
        }
        let mut j_keys = BTreeSet::new();
        for col in cols {
            if join_key_set.contains(col.name.as_str()) {
                j_keys.insert(col.name.clone());
            }
            let c_toks = tokenize(&col.name);
            for _ in 0..2 {
                doc.extend(c_toks.iter().cloned());
            }
            if !col.description.is_empty() {
                doc.extend(tokenize(&col.description));
            }
            for sv in &col.sample_values {
                doc.extend(tokenize(sv));
            }
        }
        let unique: HashSet<String> = doc.iter().cloned().collect();
        for u in unique {
            *doc_freq.entry(u).or_insert(0) += 1;
        }
        table_docs.insert(t_name.clone(), doc);
        table_join_keys.insert(t_name.clone(), j_keys);
    }

    let num_docs = catalog.len() as f64;
    let total_len: usize = table_docs.values().map(|d| d.len()).sum();
    let avg_dl = (total_len as f64) / num_docs.max(1.0);
    let k1 = 1.5_f64;
    let b = 0.75_f64;

    let mut raw_scores: HashMap<String, f64> = HashMap::new();
    for (t_name, doc) in &table_docs {
        let dl = doc.len() as f64;
        let mut tf_map: HashMap<&str, usize> = HashMap::new();
        for tok in doc {
            *tf_map.entry(tok.as_str()).or_insert(0) += 1;
        }
        let mut score = 0.0_f64;
        for q_tok in &query_tokens {
            let tf = *tf_map.get(q_tok.as_str()).unwrap_or(&0) as f64;
            if tf == 0.0 {
                continue;
            }
            let df = *doc_freq.get(q_tok.as_str()).unwrap_or(&0) as f64;
            let idf = (1.0 + (num_docs - df + 0.5) / (df + 0.5)).ln();
            let denom = tf + k1 * (1.0 - b + b * (dl / avg_dl.max(1.0)));
            score += idf * ((tf * (k1 + 1.0)) / denom);
        }

        if t_name.contains("mart_") || t_name.contains("main_analytics.") {
            score += 0.35;
        } else if t_name.contains("main_core.") {
            score += 0.20;
        }
        raw_scores.insert(t_name.clone(), score);
    }

    let mut initial: Vec<(String, f64)> = raw_scores
        .iter()
        .map(|(k, v)| (k.clone(), *v))
        .collect();
    initial.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));

    let top_anchors: Vec<String> = initial
        .iter()
        .take(2)
        .filter(|(_, s)| *s > 0.0)
        .map(|(t, _)| t.clone())
        .collect();
    let mut anchor_keys = BTreeSet::new();
    for anchor in &top_anchors {
        if let Some(keys) = table_join_keys.get(anchor) {
            for k in keys {
                anchor_keys.insert(k.clone());
            }
        }
    }

    let mut final_scores: Vec<(String, f64)> = raw_scores
        .into_iter()
        .map(|(t_name, base_score)| {
            let shared_count = table_join_keys
                .get(&t_name)
                .map(|ks| ks.intersection(&anchor_keys).count())
                .unwrap_or(0);
            let is_anchor = top_anchors.contains(&t_name);
            let mut fk_boost = if shared_count > 0 && !is_anchor {
                0.4 * (shared_count as f64)
            } else {
                0.0
            };
            if shared_count > 0 && (t_name.contains(".dim_") || t_name.starts_with("dim_")) {
                fk_boost += 0.5;
            }
            (t_name, ((base_score + fk_boost) * 10000.0).round() / 10000.0)
        })
        .collect();

    final_scores.sort_by(|a, b| {
        b.1.partial_cmp(&a.1)
            .unwrap_or(std::cmp::Ordering::Equal)
            .then_with(|| a.0.cmp(&b.0))
    });
    final_scores
}

pub fn select_top_k_tables(question: &str, catalog: &SchemaCatalog, k: usize) -> SchemaCatalog {
    let ranked = score_tables_bm25(question, catalog);
    let mut pruned = SchemaCatalog::new();
    for (t_name, _) in ranked.into_iter().take(k.max(1)) {
        if let Some(cols) = catalog.get(&t_name) {
            pruned.insert(t_name, cols.clone());
        }
    }
    pruned
}

pub fn format_pruned_ddl(pruned: &SchemaCatalog) -> String {
    let mut lines = vec!["AVAILABLE WAREHOUSE TABLES (TOP-K PRUNED):".to_string()];
    for (idx, (t_name, cols)) in pruned.iter().enumerate() {
        let col_strs: Vec<String> = cols
            .iter()
            .map(|c| {
                let mut base = format!("{} ({})", c.name, c.data_type);
                if !c.sample_values.is_empty() {
                    let samples: Vec<String> = c
                        .sample_values
                        .iter()
                        .take(4)
                        .map(|s| format!("'{s}'"))
                        .collect();
                    base.push_str(&format!(" [e.g. {}]", samples.join(", ")));
                }
                base
            })
            .collect();
        lines.push(format!("{}. {}: {}", idx + 1, t_name, col_strs.join(", ")));
    }
    lines.join("\n")
}

pub fn compile_hop1_gbnf() -> String {
    r#"# Hop 1 GBNF Grammar: execute_duckdb_query
# Enforces valid JSON tool call and read-only SELECT / WITH prefix

root ::= ws "{" ws "\"tool\"" ws ":" ws "\"execute_duckdb_query\"" ws "," ws "\"arguments\"" ws ":" ws arguments ws "}" ws

arguments ::= "{" ws "\"explanation\"" ws ":" ws string ws "," ws "\"sql\"" ws ":" ws sql-string ws "}"

sql-string ::= "\"" sql-prefix sql-char* "\""
sql-prefix ::= ("SELECT" | "select" | "WITH" | "with") " "
sql-char ::= [^"\\\x7F\x00-\x1F] | "\\" (["\\bfnrt] | "u" [0-9a-fA-F]{4})

string ::= "\"" char* "\""
char ::= [^"\\\x7F\x00-\x1F] | "\\" (["\\bfnrt] | "u" [0-9a-fA-F]{4})

ws ::= [ \t\n\r]*
"#
    .to_string()
}

pub fn compile_hop2_gbnf(columns: &[String]) -> String {
    let col_rule = if columns.is_empty() {
        "string".to_string()
    } else {
        let mut seen = BTreeSet::new();
        let mut literals = Vec::new();
        for c in columns {
            if !c.is_empty() && seen.insert(c.clone()) {
                let escaped = c.replace('\\', "\\\\").replace('"', "\\\"");
                literals.push(format!("\"\\\"{escaped}\\\"\""));
            }
        }
        if literals.is_empty() {
            "string".to_string()
        } else {
            literals.join(" | ")
        }
    };

    format!(
        r#"# Hop 2 GBNF Grammar: render_workspace_ui
# Dynamically constrains component schemas and DuckDB output column bindings

root ::= ws "{{" ws "\"tool\"" ws ":" ws "\"render_workspace_ui\"" ws "," ws "\"arguments\"" ws ":" ws arguments ws "}}" ws

arguments ::= "{{" ws "\"title\"" ws ":" ws string ws "," ws "\"narrative_summary\"" ws ":" ws string ws "," ws "\"components\"" ws ":" ws component-list ws "}}"

component-list ::= "[" ws component (ws "," ws component){{0,3}} ws "]"

component ::= kpi-grid | time-series-chart | category-bar-chart | budget-variance-chart | data-table | filter-bar

kpi-grid ::= "{{" ws "\"component\"" ws ":" ws "\"KPIGrid\"" ws "," ws "\"metrics\"" ws ":" ws "[" ws kpi-metric (ws "," ws kpi-metric){{0,3}} ws "]" ws "}}"
kpi-metric ::= "{{" ws "\"label\"" ws ":" ws string ws "," ws "\"value_column\"" ws ":" ws column-name ws "," ws "\"value_format\"" ws ":" ws value-format (ws "," ws "\"delta_column\"" ws ":" ws column-name)? ws "}}"

time-series-chart ::= "{{" ws "\"component\"" ws ":" ws "\"TimeSeriesChart\"" ws "," ws "\"chart_variant\"" ws ":" ws ts-variant ws "," ws "\"x_column\"" ws ":" ws column-name ws "," ws "\"y_columns\"" ws ":" ws col-list-1-3 (ws "," ws "\"series_column\"" ws ":" ws column-name)? ws "," ws "\"value_format\"" ws ":" ws value-format ws "}}"
ts-variant ::= "\"line\"" | "\"area\"" | "\"stacked_bar\"" | "\"bar\""

category-bar-chart ::= "{{" ws "\"component\"" ws ":" ws "\"CategoryBarChart\"" ws "," ws "\"chart_variant\"" ws ":" ws cat-variant ws "," ws "\"category_column\"" ws ":" ws column-name ws "," ws "\"value_columns\"" ws ":" ws col-list-1-3 (ws "," ws "\"series_column\"" ws ":" ws column-name)? ws "," ws "\"value_format\"" ws ":" ws value-format ws "}}"
cat-variant ::= "\"horizontal\"" | "\"vertical\"" | "\"grouped\"" | "\"stacked\""

budget-variance-chart ::= "{{" ws "\"component\"" ws ":" ws "\"BudgetVarianceChart\"" ws "," ws "\"category_column\"" ws ":" ws column-name ws "," ws "\"actual_column\"" ws ":" ws column-name ws "," ws "\"budget_column\"" ws ":" ws column-name (ws "," ws "\"variance_column\"" ws ":" ws column-name)? ws "," ws "\"value_format\"" ws ":" ws value-format ws "}}"

data-table ::= "{{" ws "\"component\"" ws ":" ws "\"DataTable\"" ws "," ws "\"columns\"" ws ":" ws col-list-any (ws "," ws "\"default_sort\"" ws ":" ws sort-spec)? ws "}}"
sort-spec ::= "{{" ws "\"column\"" ws ":" ws column-name ws "," ws "\"direction\"" ws ":" ws ("\"asc\"" | "\"desc\"") ws "}}"

filter-bar ::= "{{" ws "\"component\"" ws ":" ws "\"FilterBar\"" ws "," ws "\"controls\"" ws ":" ws "[" ws filter-control (ws "," ws filter-control){{0,3}} ws "]" ws "}}"
filter-control ::= "{{" ws "\"column\"" ws ":" ws column-name ws "," ws "\"control_type\"" ws ":" ws control-type ws "," ws "\"label\"" ws ":" ws string ws "}}"
control-type ::= "\"date_range\"" | "\"multi_select\"" | "\"single_select\"" | "\"numeric_range\"" | "\"search\""

value-format ::= "\"currency\"" | "\"percent\"" | "\"integer\"" | "\"decimal\"" | "\"raw\""

col-list-1-3 ::= "[" ws column-name (ws "," ws column-name){{0,2}} ws "]"
col-list-any ::= "[" ws column-name (ws "," ws column-name)* ws "]"

column-name ::= {col_rule}

string ::= "\"" char* "\""
char ::= [^"\\\x7F\x00-\x1F] | "\\" (["\\bfnrt] | "u" [0-9a-fA-F]{{4}})

ws ::= [ \t\n\r]*
"#
    )
}
