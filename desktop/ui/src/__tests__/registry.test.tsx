import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import {
  ExecuteDuckDBQuerySchema,
  RenderWorkspaceUISchema,
  validateWorkspaceUISemantics,
} from "../schemas/workspace-ui";
import { decodeArrowIPCStream, encodeRowsToArrowIPC } from "../lib/arrow-client";
import { PRESET_SCENARIOS, runPromptScenario } from "../lib/local-ai-provider";
import { App } from "../App";
import { WorkspaceRenderer } from "../components/registry/WorkspaceRenderer";

describe("Generative UI Canonical Registry & Arrow IPC Client", () => {
  afterEach(() => {
    // @ts-ignore ensure a mocked Wry bridge never leaks between tests
    delete window.sendRustRpc;
  });

  it("validates Hop 1 execute_duckdb_query and rejects mutating SQL", () => {
    const valid = ExecuteDuckDBQuerySchema.safeParse({
      tool: "execute_duckdb_query",
      arguments: {
        explanation: "Count students",
        sql: "SELECT COUNT(*) FROM main_core.dim_students",
      },
    });
    expect(valid.success).toBe(true);

    const invalid = ExecuteDuckDBQuerySchema.safeParse({
      tool: "execute_duckdb_query",
      arguments: {
        explanation: "Drop table",
        sql: "DROP TABLE main_core.dim_students",
      },
    });
    expect(invalid.success).toBe(false);
  });

  it("round-trips rows through Apache Arrow IPC binary stream via tableFromIPC", () => {
    const sampleRows = [
      { academic_year: "2023-2024", school_name: "Lincoln High School", avg_gpa: 2.92 },
      { academic_year: "2024-2025", school_name: "Roosevelt Middle School", avg_gpa: 3.09 },
    ];
    const ipcBytes = encodeRowsToArrowIPC(sampleRows, [
      "academic_year",
      "school_name",
      "avg_gpa",
    ]);
    expect(ipcBytes.byteLength).toBeGreaterThan(64);

    const decoded = decodeArrowIPCStream(ipcBytes, "q_test_ipc");
    expect(decoded.queryId).toBe("q_test_ipc");
    expect(decoded.columns).toEqual(["academic_year", "school_name", "avg_gpa"]);
    expect(decoded.rows).toHaveLength(2);
    expect(decoded.rows[0].school_name).toBe("Lincoln High School");
    expect(Number(decoded.rows[0].avg_gpa)).toBeCloseTo(2.92, 2);
  });

  it("enforces Hop 2 column binding integrity and KPIGrid row_count semantics", () => {
    const scenario = PRESET_SCENARIOS[0];
    const validRes = validateWorkspaceUISemantics(
      scenario.hop2Call,
      scenario.summary
    );
    expect(validRes.valid).toBe(true);

    const badColCall = structuredClone(scenario.hop2Call);
    if (badColCall.arguments.components[1].component === "TimeSeriesChart") {
      badColCall.arguments.components[1].y_columns = ["hallucinated_column"];
    }
    const badRes = validateWorkspaceUISemantics(badColCall, scenario.summary);
    expect(badRes.valid).toBe(false);
    expect(badRes.errors.join(" ")).toContain("hallucinated_column");
  });

  it("mounts FilterBar, TimeSeriesChart, BudgetVarianceChart, CategoryBarChart, KPIGrid, and DataTable", () => {
    const onApplyFilters = vi.fn();

    // 1. Render Multi-Year School Enrollment Trend (FilterBar + TimeSeriesChart + DataTable)
    const enrollmentScen = PRESET_SCENARIOS[0];
    const { unmount } = render(
      <WorkspaceRenderer
        uiPayload={enrollmentScen.hop2Call}
        resultSummary={enrollmentScen.summary}
        rows={enrollmentScen.seedRows}
        baseRows={enrollmentScen.seedRows}
        onApplyFilters={onApplyFilters}
        filterLatencyMs={4.2}
      />
    );
    expect(screen.getByTestId("filter-bar")).toBeInTheDocument();
    expect(screen.getByTestId("timeseries-chart")).toBeInTheDocument();
    expect(screen.getByTestId("data-table")).toBeInTheDocument();

    // Click a school pill in FilterBar and verify Zero-LLM callback fires
    const lincolnPill = screen.getByRole("button", { name: "Lincoln High School" });
    fireEvent.click(lincolnPill);
    expect(onApplyFilters).toHaveBeenCalledWith([
      {
        column: "school_name",
        control_type: "multi_select",
        values: ["Lincoln High School"],
      },
    ]);
    unmount();

    // 2. Render KPIGrid + CategoryBarChart on Equity Outcomes by Race
    const multiCompPayload = RenderWorkspaceUISchema.parse({
      tool: "render_workspace_ui",
      arguments: {
        title: "District Equity Overview",
        narrative_summary: "Subgroup GPA and attendance rate comparison.",
        components: [
          {
            component: "KPIGrid",
            metrics: [
              {
                label: "Subgroup Average GPA",
                value_column: "avg_gpa",
                value_format: "decimal",
                delta_column: "avg_attendance_rate",
              },
            ],
          },
          {
            component: "CategoryBarChart",
            chart_variant: "horizontal",
            category_column: "primary_race",
            value_columns: ["avg_gpa", "avg_attendance_rate"],
            value_format: "decimal",
          },
        ],
      },
    });

    const equityScen = PRESET_SCENARIOS[1];
    render(
      <WorkspaceRenderer
        uiPayload={multiCompPayload}
        rows={equityScen.seedRows}
        baseRows={equityScen.seedRows}
        onApplyFilters={onApplyFilters}
      />
    );
    expect(screen.getByTestId("kpi-value-avg_gpa")).toBeInTheDocument();
    expect(screen.getByTestId("category-bar-chart")).toBeInTheDocument();
  });

  it("maps a run_prompt trace into a TwoHopTurnState", async () => {
    const scenario = PRESET_SCENARIOS[0];
    window.sendRustRpc = vi.fn(async () => ({
      question: "What is enrollment?",
      hop1_call: scenario.hop1Call,
      hop2_call: scenario.hop2Call,
      result_summary: scenario.summary,
      arrow_uri: `arrow://${scenario.summary.query_id}`,
      retries_used: 0,
      total_latency_ms: 12.5,
    }));
    const state = await runPromptScenario("What is enrollment?");
    expect(state.prompt).toBe("What is enrollment?");
    expect(state.hop1Call.tool).toBe("execute_duckdb_query");
    expect(state.resultSummary.query_id).toBe(scenario.summary.query_id);
    expect(state.selfHealedRetries).toBe(0);
    expect(window.sendRustRpc).toHaveBeenCalledWith(
      expect.objectContaining({ cmd: "run_prompt", prompt: "What is enrollment?" })
    );
  });

  it("rejects empty prompt and missing bridge", async () => {
    await expect(runPromptScenario("   ")).rejects.toThrowError("Type a question");
    // @ts-ignore test cleanup of any leaked mock
    delete window.sendRustRpc;
    await expect(runPromptScenario("What is enrollment?")).rejects.toThrowError(
      "requires the native desktop host"
    );
  });

  it("renders the question input box in App", () => {
    render(<App />);
    expect(document.getElementById("ask-question")).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/Ask in plain English/)).toBeInTheDocument();
  });

  it("determines percent 0..1 vs 0..100 scale across the entire column rather than per cell", async () => {
    const { detectColumnIsRatio, formatMetricValue } = await import("../lib/formatters");
    const pctCol = [0.85, 4.2];
    const ratioCol = [0.85, 0.94];
    expect(detectColumnIsRatio(pctCol)).toBe(false);
    expect(detectColumnIsRatio(ratioCol)).toBe(true);
    expect(formatMetricValue(0.85, "percent", detectColumnIsRatio(pctCol))).toBe("0.85%");
    expect(formatMetricValue(0.85, "percent", detectColumnIsRatio(ratioCol))).toBe("85.00%");
  });
});
