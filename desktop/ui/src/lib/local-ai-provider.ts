import {
  DuckDBResultSummary,
  ExecuteDuckDBQueryCall,
  FilterMutation,
  RenderWorkspaceUICall,
} from "../schemas/workspace-ui";
import { DecodedArrowDataset, fetchArrowDataset } from "./arrow-client";

declare global {
  interface Window {
    ipc?: {
      postMessage: (msg: string) => void;
    };
    sendRustRpc?: (cmdObj: Record<string, unknown>) => Promise<Record<string, unknown>>;
  }
}

export interface TwoHopTurnState {
  id: string;
  domain: "education";
  prompt: string;
  hop1Call: ExecuteDuckDBQueryCall;
  resultSummary: DuckDBResultSummary;
  hop2Call: RenderWorkspaceUICall;
  dataset: DecodedArrowDataset;
  hop2Gbnf?: string;
  latencyMs: number;
  selfHealedRetries: number;
}

export interface PresetScenario {
  id: string;
  domain: "education";
  label: string;
  prompt: string;
  hop1Call: ExecuteDuckDBQueryCall;
  hop2Call: RenderWorkspaceUICall;
  seedRows: Record<string, unknown>[];
  summary: DuckDBResultSummary;
}

export const PRESET_SCENARIOS: PresetScenario[] = [
  {
    id: "edu_enrollment_trend",
    domain: "education",
    label: "Multi-Year School Enrollment",
    prompt: "Compare total student enrollment across schools from 2021-2022 through 2024-2025.",
    hop1Call: {
      tool: "execute_duckdb_query",
      arguments: {
        explanation: "Retrieve school-by-school enrollment counts across academic years from main_analytics.school_summary.",
        sql: "SELECT academic_year, school_name, total_students FROM main_analytics.school_summary ORDER BY academic_year ASC, total_students DESC",
      },
    },
    hop2Call: {
      tool: "render_workspace_ui",
      arguments: {
        title: "Multi-Year School Enrollment Trend",
        narrative_summary:
          "Lincoln High School (1,180–1,265 students) and Jefferson High School (1,050–1,145 students) show steady enrollment growth across the 2021-2022 through 2024-2025 cohorts.",
        components: [
          {
            component: "FilterBar",
            controls: [
              { column: "academic_year", control_type: "date_range", label: "Academic Year Range" },
              { column: "school_name", control_type: "multi_select", label: "School" },
            ],
          },
          {
            component: "TimeSeriesChart",
            chart_variant: "stacked_bar",
            x_column: "academic_year",
            y_columns: ["total_students"],
            series_column: "school_name",
            value_format: "integer",
          },
          {
            component: "DataTable",
            columns: ["academic_year", "school_name", "total_students"],
            default_sort: { column: "academic_year", direction: "desc" },
          },
        ],
      },
    },
    seedRows: [
      { academic_year: "2021-2022", school_name: "Lincoln High School", total_students: 1180 },
      { academic_year: "2021-2022", school_name: "Jefferson High School", total_students: 1050 },
      { academic_year: "2021-2022", school_name: "Roosevelt Middle School", total_students: 810 },
      { academic_year: "2021-2022", school_name: "Washington Elementary School", total_students: 590 },
      { academic_year: "2022-2023", school_name: "Lincoln High School", total_students: 1205 },
      { academic_year: "2022-2023", school_name: "Jefferson High School", total_students: 1080 },
      { academic_year: "2022-2023", school_name: "Roosevelt Middle School", total_students: 835 },
      { academic_year: "2022-2023", school_name: "Washington Elementary School", total_students: 605 },
      { academic_year: "2023-2024", school_name: "Lincoln High School", total_students: 1240 },
      { academic_year: "2023-2024", school_name: "Jefferson High School", total_students: 1120 },
      { academic_year: "2023-2024", school_name: "Roosevelt Middle School", total_students: 860 },
      { academic_year: "2023-2024", school_name: "Washington Elementary School", total_students: 620 },
      { academic_year: "2024-2025", school_name: "Lincoln High School", total_students: 1265 },
      { academic_year: "2024-2025", school_name: "Jefferson High School", total_students: 1145 },
      { academic_year: "2024-2025", school_name: "Roosevelt Middle School", total_students: 875 },
      { academic_year: "2024-2025", school_name: "Washington Elementary School", total_students: 635 },
    ],
    summary: {
      status: "ok",
      query_id: "q_edu_enrollment_01",
      row_count: 16,
      columns: [
        { name: "academic_year", type: "VARCHAR", distinct_count: 4, min: "2021-2022", max: "2024-2025" },
        {
          name: "school_name",
          type: "VARCHAR",
          distinct_count: 4,
          sample_values: ["Lincoln High School", "Jefferson High School", "Roosevelt Middle School"],
        },
        { name: "total_students", type: "BIGINT", distinct_count: 16, min: 590, max: 1265 },
      ],
      sample_rows: [
        ["2021-2022", "Lincoln High School", 1180],
        ["2021-2022", "Jefferson High School", 1050],
        ["2021-2022", "Roosevelt Middle School", 810],
      ],
    },
  },
  {
    id: "edu_equity_by_race",
    domain: "education",
    label: "Equity Outcomes by Race",
    prompt: "Compare student counts, average GPA, and attendance rates by racial subgroup in 2023-2024.",
    hop1Call: {
      tool: "execute_duckdb_query",
      arguments: {
        explanation: "Retrieve 2023-2024 racial subgroup enrollment, average GPA, attendance rate, and incident counts from main_analytics.equity_by_race.",
        sql: "SELECT primary_race, student_count, avg_gpa, avg_attendance_rate, incident_count FROM main_analytics.equity_by_race WHERE academic_year = '2023-2024' ORDER BY student_count DESC",
      },
    },
    hop2Call: {
      tool: "render_workspace_ui",
      arguments: {
        title: "2023-2024 Equity Outcomes by Racial Subgroup",
        narrative_summary:
          "Hispanic/Latino (1,650 students) and White (980 students) comprise the largest cohorts, while GPA and attendance rates vary across racial subgroups.",
        components: [
          {
            component: "FilterBar",
            controls: [
              { column: "primary_race", control_type: "multi_select", label: "Racial Subgroup" },
              { column: "avg_gpa", control_type: "numeric_range", label: "Average GPA" },
            ],
          },
          {
            component: "CategoryBarChart",
            chart_variant: "horizontal",
            category_column: "primary_race",
            value_columns: ["avg_gpa", "avg_attendance_rate"],
            value_format: "decimal",
          },
          {
            component: "DataTable",
            columns: ["primary_race", "student_count", "avg_gpa", "avg_attendance_rate", "incident_count"],
            default_sort: { column: "student_count", direction: "desc" },
          },
        ],
      },
    },
    seedRows: [
      { primary_race: "Hispanic/Latino", student_count: 1650, avg_gpa: 2.84, avg_attendance_rate: 0.915, incident_count: 168 },
      { primary_race: "White", student_count: 980, avg_gpa: 3.18, avg_attendance_rate: 0.942, incident_count: 72 },
      { primary_race: "Asian", student_count: 540, avg_gpa: 3.46, avg_attendance_rate: 0.964, incident_count: 18 },
      { primary_race: "Black/African American", student_count: 420, avg_gpa: 2.71, avg_attendance_rate: 0.892, incident_count: 64 },
      { primary_race: "Two or More Races", student_count: 250, avg_gpa: 3.08, avg_attendance_rate: 0.931, incident_count: 26 },
    ],
    summary: {
      status: "ok",
      query_id: "q_edu_equity_01",
      row_count: 5,
      columns: [
        { name: "primary_race", type: "VARCHAR", distinct_count: 5, sample_values: ["Hispanic/Latino", "White", "Asian"] },
        { name: "student_count", type: "BIGINT", distinct_count: 5, min: 250, max: 1650 },
        { name: "avg_gpa", type: "DOUBLE", distinct_count: 5, min: 2.71, max: 3.46 },
        { name: "avg_attendance_rate", type: "DOUBLE", distinct_count: 5, min: 0.892, max: 0.964 },
        { name: "incident_count", type: "BIGINT", distinct_count: 5, min: 18, max: 168 },
      ],
      sample_rows: [
        ["Hispanic/Latino", 1650, 2.84, 0.915, 168],
        ["White", 980, 3.18, 0.942, 72],
        ["Asian", 540, 3.46, 0.964, 18],
      ],
    },
  },
  {
    id: "edu_accountability_overview",
    domain: "education",
    label: "CDE Subgroup Accountability",
    prompt: "Compare suspension rates and chronic absenteeism rates by race/subgroup for 2023-24.",
    hop1Call: {
      tool: "execute_duckdb_query",
      arguments: {
        explanation:
          "Aggregate average suspension rate and chronic absenteeism rate by reporting_category_label in 2023-24 from mart_cde_school_accountability.",
        sql: "SELECT reporting_category_label, ROUND(AVG(su_suspension_rate_pct), 2) AS avg_suspension_rate, ROUND(AVG(ca_chronic_absent_rate_pct), 2) AS avg_chronic_absent_rate FROM main_analytics.mart_cde_school_accountability WHERE academic_year = '2023-24' AND reporting_category IN ('RA','RB','RH','RW','SED','EL','TA') GROUP BY reporting_category_label ORDER BY avg_chronic_absent_rate DESC",
      },
    },
    hop2Call: {
      tool: "render_workspace_ui",
      arguments: {
        title: "2023-24 District Accountability by Student Subgroup",
        narrative_summary:
          "Chronic absenteeism and suspension rates show pronounced disparities across student subgroups in the 2023-24 CDE accountability mart.",
        components: [
          {
            component: "FilterBar",
            controls: [
              { column: "reporting_category_label", control_type: "multi_select", label: "Student Subgroup" },
            ],
          },
          {
            component: "CategoryBarChart",
            chart_variant: "grouped",
            category_column: "reporting_category_label",
            value_columns: ["avg_chronic_absent_rate", "avg_suspension_rate"],
            value_format: "percent",
          },
          {
            component: "DataTable",
            columns: ["reporting_category_label", "avg_chronic_absent_rate", "avg_suspension_rate"],
            default_sort: { column: "avg_chronic_absent_rate", direction: "desc" },
          },
        ],
      },
    },
    seedRows: [
      { reporting_category_label: "Black / African American", avg_chronic_absent_rate: 28.4, avg_suspension_rate: 6.8 },
      { reporting_category_label: "Socioeconomically Disadvantaged", avg_chronic_absent_rate: 24.1, avg_suspension_rate: 4.9 },
      { reporting_category_label: "Hispanic / Latino", avg_chronic_absent_rate: 22.6, avg_suspension_rate: 4.2 },
      { reporting_category_label: "English Learners", avg_chronic_absent_rate: 21.8, avg_suspension_rate: 3.7 },
      { reporting_category_label: "All Students", avg_chronic_absent_rate: 18.5, avg_suspension_rate: 3.4 },
      { reporting_category_label: "White", avg_chronic_absent_rate: 14.2, avg_suspension_rate: 2.8 },
      { reporting_category_label: "Asian", avg_chronic_absent_rate: 8.6, avg_suspension_rate: 1.1 },
    ],
    summary: {
      status: "ok",
      query_id: "q_edu_subgroups",
      row_count: 7,
      columns: [
        { name: "reporting_category_label", type: "VARCHAR", distinct_count: 7, sample_values: ["All Students", "Hispanic / Latino"] },
        { name: "avg_chronic_absent_rate", type: "DOUBLE", distinct_count: 7, min: 8.6, max: 28.4 },
        { name: "avg_suspension_rate", type: "DOUBLE", distinct_count: 7, min: 1.1, max: 6.8 },
      ],
      sample_rows: [
        ["Black / African American", 28.4, 6.8],
        ["Socioeconomically Disadvantaged", 24.1, 4.9],
      ],
    },
  },
];

function isWryBridgeAvailable(): boolean {
  return typeof window !== "undefined" && typeof window.sendRustRpc === "function";
}

function applyClientFallbackFilters(
  rows: Record<string, unknown>[],
  filters: FilterMutation[]
): Record<string, unknown>[] {
  return rows.filter((row) => {
    for (const f of filters) {
      const cell = row[f.column];
      if (f.control_type === "date_range" || f.control_type === "numeric_range") {
        if (f.min !== undefined && f.min !== "" && cell !== undefined && cell !== null) {
          if (cell < f.min) return false;
        }
        if (f.max !== undefined && f.max !== "" && cell !== undefined && cell !== null) {
          if (cell > f.max) return false;
        }
      } else if (f.control_type === "multi_select") {
        if (f.values && f.values.length > 0) {
          if (!f.values.map(String).includes(String(cell))) return false;
        }
      } else if (f.control_type === "single_select") {
        if (f.value !== undefined && f.value !== "") {
          if (String(cell) !== String(f.value)) return false;
        }
      } else if (f.control_type === "search") {
        if (f.query && f.query.trim() !== "") {
          if (!String(cell ?? "").toLowerCase().includes(f.query.trim().toLowerCase())) {
            return false;
          }
        }
      }
    }
    return true;
  });
}

export async function runPresetOrPromptScenario(
  scenario: PresetScenario
): Promise<TwoHopTurnState> {
  const start = performance.now();
  if (isWryBridgeAvailable() && window.sendRustRpc) {
    const resp = await window.sendRustRpc({
      cmd: "execute_duckdb_query",
      sql: scenario.hop1Call.arguments.sql,
      query_id: scenario.summary.query_id,
    });
    if (resp && resp.status === "ok" && resp.result_summary) {
      const summary = resp.result_summary as DuckDBResultSummary;
      const dataset = await fetchArrowDataset(summary.query_id, scenario.seedRows);
      return {
        id: scenario.id,
        domain: scenario.domain,
        prompt: scenario.prompt,
        hop1Call: scenario.hop1Call,
        resultSummary: summary,
        hop2Call: scenario.hop2Call,
        dataset,
        hop2Gbnf: typeof resp.hop2_gbnf === "string" ? resp.hop2_gbnf : undefined,
        latencyMs: Number((performance.now() - start).toFixed(1)),
        selfHealedRetries: 0,
      };
    }
  }

  const dataset = await fetchArrowDataset(
    scenario.summary.query_id,
    scenario.seedRows
  );
  return {
    id: scenario.id,
    domain: scenario.domain,
    prompt: scenario.prompt,
    hop1Call: scenario.hop1Call,
    resultSummary: scenario.summary,
    hop2Call: scenario.hop2Call,
    dataset,
    latencyMs: Number((performance.now() - start).toFixed(1)),
    selfHealedRetries: 0,
  };
}

export async function applyZeroLlmFilterBarMutation(
  currentState: TwoHopTurnState,
  baseSeedRows: Record<string, unknown>[],
  filters: FilterMutation[]
): Promise<{ dataset: DecodedArrowDataset; filterLatencyMs: number }> {
  const start = performance.now();
  if (isWryBridgeAvailable() && window.sendRustRpc) {
    const resp = await window.sendRustRpc({
      cmd: "apply_query_filters",
      query_id_or_sql: currentState.resultSummary.query_id,
      filters,
    });
    if (resp && resp.status === "ok" && resp.result_summary) {
      const summary = resp.result_summary as DuckDBResultSummary;
      const dataset = await fetchArrowDataset(summary.query_id);
      return {
        dataset,
        filterLatencyMs: Number((performance.now() - start).toFixed(2)),
      };
    }
  }

  const filteredRows = applyClientFallbackFilters(baseSeedRows, filters);
  const dataset = await fetchArrowDataset(
    `${currentState.resultSummary.query_id}_filtered`,
    filteredRows,
    currentState.dataset.columns
  );
  return {
    dataset,
    filterLatencyMs: Number((performance.now() - start).toFixed(2)),
  };
}
