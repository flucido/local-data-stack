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

  it("supports FilterBar single_select, decimal dual-bound numeric_range, debounce, date clamping, aria-pressed, and Show all", () => {
    vi.useFakeTimers();
    try {
      const onApplyFilters = vi.fn();
      const baseRows = Array.from({ length: 10 }, (_, i) => ({
        school_name: `School ${String(i + 1).padStart(2, "0")}`,
        academic_year: i < 5 ? "2022-2023" : "2024-2025",
        avg_gpa: Number((2.15 + i * 0.15).toFixed(2)),
        grade_band: i % 2 === 0 ? "Middle" : "High",
      }));

      const payload = RenderWorkspaceUISchema.parse({
        tool: "render_workspace_ui",
        arguments: {
          title: "Filter Fidelity Suite",
          narrative_summary: "Tests all FilterBar controls.",
          components: [
            {
              component: "FilterBar",
              controls: [
                { column: "school_name", control_type: "multi_select", label: "Schools" },
                { column: "grade_band", control_type: "single_select", label: "Grade Band" },
                { column: "academic_year", control_type: "date_range", label: "School Year" },
                { column: "avg_gpa", control_type: "numeric_range", label: "GPA Range" },
              ],
            },
          ],
        },
      });

      render(
        <WorkspaceRenderer
          uiPayload={payload}
          rows={baseRows}
          baseRows={baseRows}
          onApplyFilters={onApplyFilters}
        />
      );

      // D2 + D3 + D11: aria-pressed, group labelledby, and Show all (10)
      const pill01 = screen.getByRole("button", { name: "School 01" });
      expect(pill01).toHaveAttribute("aria-pressed", "false");
      fireEvent.click(pill01);
      expect(pill01).toHaveAttribute("aria-pressed", "true");

      const showAllBtn = screen.getByRole("button", { name: /Show all \(10\)/i });
      fireEvent.click(showAllBtn);
      expect(screen.getByRole("button", { name: "School 10" })).toBeInTheDocument();

      // U10: single_select renders <select> with "All"
      const gradeSelect = screen.getByLabelText("Grade Band") as HTMLSelectElement;
      expect(gradeSelect.tagName).toBe("SELECT");
      fireEvent.change(gradeSelect, { target: { value: "High" } });
      expect(onApplyFilters).toHaveBeenLastCalledWith(
        expect.arrayContaining([
          { column: "grade_band", control_type: "single_select", value: "High" },
        ])
      );

      // U13: date_range clamps max when min > max
      const startSel = screen.getByLabelText("School Year Start") as HTMLSelectElement;
      const endSel = screen.getByLabelText("School Year End") as HTMLSelectElement;
      fireEvent.change(endSel, { target: { value: "2022-2023" } });
      fireEvent.change(startSel, { target: { value: "2024-2025" } });
      expect(onApplyFilters).toHaveBeenLastCalledWith(
        expect.arrayContaining([
          {
            column: "academic_year",
            control_type: "date_range",
            min: "2024-2025",
            max: "2024-2025",
          },
        ])
      );

      // U10 + U1: decimal numeric_range has Min & Max sliders with step=0.05 and 250ms debounce
      const minSlider = screen.getByLabelText("GPA Range Minimum") as HTMLInputElement;
      const maxSlider = screen.getByLabelText("GPA Range Maximum") as HTMLInputElement;
      expect(minSlider.step).toBe("0.05");
      expect(maxSlider.step).toBe("0.05");

      const callsBeforeSlider = onApplyFilters.mock.calls.length;
      fireEvent.change(minSlider, { target: { value: "2.5" } });
      expect(onApplyFilters.mock.calls.length).toBe(callsBeforeSlider);
      vi.advanceTimersByTime(260);
      expect(onApplyFilters.mock.calls.length).toBe(callsBeforeSlider + 1);
    } finally {
      vi.useRealTimers();
    }
  });

  it("enforces DataTable accessible sorting, empty state, CSV formula neutralization, SVG line/area TimeSeriesChart, CategoryBarChart pivoting, and KPIGrid adverse metric polarity", async () => {
    const { buildCsvContent } = await import("../components/registry/DataTable");

    // D23: Quote CSV headers and neutralize leading =, +, -, @ formula injection
    const csv = buildCsvContent(
      ["school_name", "formula_col"],
      [{ school_name: "Lincoln, High", formula_col: "=CMD|' /C calc'!A0" }]
    );
    expect(csv.split("\n")[0]).toBe('"school_name","formula_col"');
    expect(csv.split("\n")[1]).toContain("\"'=CMD|' /C calc'!A0\"");

    // D1 + D19: DataTable keyboard button sorting + aria-sort + empty state with Clear search
    const tablePayload = RenderWorkspaceUISchema.parse({
      tool: "render_workspace_ui",
      arguments: {
        title: "School Records",
        narrative_summary: "Sortable accessible table.",
        components: [
          {
            component: "DataTable",
            columns: ["school_name", "avg_gpa"],
            default_sort: { column: "avg_gpa", direction: "desc" },
          },
          {
            component: "TimeSeriesChart",
            chart_variant: "line",
            x_column: "academic_year",
            y_columns: ["avg_gpa"],
            value_format: "decimal",
          },
          {
            component: "CategoryBarChart",
            chart_variant: "stacked",
            category_column: "school_name",
            value_columns: ["avg_gpa"],
            series_column: "academic_year",
            value_format: "decimal",
          },
          {
            component: "KPIGrid",
            metrics: [
              {
                label: "Chronic Absenteeism Rate",
                value_column: "chronic_rate",
                value_format: "percent",
                delta_column: "chronic_delta",
              },
            ],
          },
        ],
      },
    });

    const rows = [
      {
        school_name: "Lincoln High",
        academic_year: "2023-2024",
        avg_gpa: 3.1,
        chronic_rate: 14.2,
        chronic_delta: 2.5,
      },
    ];

    const { container, unmount } = render(
      <WorkspaceRenderer
        uiPayload={tablePayload}
        rows={rows}
        baseRows={rows}
        onApplyFilters={vi.fn()}
      />
    );

    // D1: <th aria-sort="descending"> with inner <button>
    const gpaHeader = container.querySelector('th[aria-sort="descending"]');
    expect(gpaHeader).not.toBeNull();
    expect(gpaHeader?.querySelector("button")).not.toBeNull();

    // U11 + D4: TimeSeriesChart renders SVG polyline/path on "line" variant + sr-only table
    expect(container.querySelector("svg polyline, svg path")).not.toBeNull();
    expect(container.querySelector("table.sr-only")).not.toBeNull();

    // D15: Positive delta on Chronic Absenteeism Rate is adverse (.kpi-delta-neg)
    expect(container.querySelector(".kpi-delta-neg")).not.toBeNull();

    // D19: Filter table to 0 matches -> "No matching records found" + "Clear search"
    const searchInput = screen.getByLabelText(/Filter table rows|Search table/i);
    fireEvent.change(searchInput, { target: { value: "zzz_nomatch" } });
    expect(screen.getByText(/No matching records found/i)).toBeInTheDocument();
    const clearBtn = screen.getByRole("button", { name: /Clear search/i });
    fireEvent.click(clearBtn);
    expect(screen.queryByText(/No matching records found/i)).toBeNull();

    unmount();

    // D15: KPIGrid with rows=[] shows "No data"
    const emptyKpiPayload = RenderWorkspaceUISchema.parse({
      tool: "render_workspace_ui",
      arguments: {
        title: "Empty KPI",
        narrative_summary: "Empty check.",
        components: [
          {
            component: "KPIGrid",
            metrics: [{ label: "Attendance Rate", value_column: "att", value_format: "percent" }],
          },
        ],
      },
    });
    render(
      <WorkspaceRenderer
        uiPayload={emptyKpiPayload}
        rows={[]}
        baseRows={[]}
        onApplyFilters={vi.fn()}
      />
    );
    expect(screen.getByText("No data")).toBeInTheDocument();
  });

  it("renders educator-friendly copy, aria-pressed/expanded states, How this answer was computed disclosure, polite live region, Demo Mode indicator, and surfaces arrow:// fetch errors", async () => {
    const { fetchArrowDataset } = await import("../lib/arrow-client");
    const origFetch = globalThis.fetch;
    globalThis.fetch = vi.fn(async () => new Response("Not Found", { status: 404 })) as unknown as typeof fetch;
    try {
      await expect(fetchArrowDataset("q_missing_no_fallback")).rejects.toThrowError(/404|Failed to load/i);
    } finally {
      globalThis.fetch = origFetch;
    }

    const scenario = PRESET_SCENARIOS[0];
    window.sendRustRpc = vi.fn(async (req: Record<string, unknown>) => {
      if (req.cmd === "run_prompt") {
        return {
          status: "ok",
          mode: "deterministic_demo",
          question: "How is enrollment trending?",
          hop1_call: scenario.hop1Call,
          hop2_call: scenario.hop2Call,
          result_summary: scenario.summary,
          arrow_uri: `arrow://${scenario.summary.query_id}`,
          retries_used: 0,
          total_latency_ms: 8.4,
        };
      }
      return {
        status: "ok",
        result_summary: scenario.summary,
      };
    });

    // Provide valid Arrow stream for fetchArrowDataset when sendRustRpc is mocked
    const validBytes = encodeRowsToArrowIPC(scenario.seedRows);
    globalThis.fetch = vi.fn(
      async () => new Response(validBytes as unknown as BodyInit, { status: 200 })
    ) as unknown as typeof fetch;

    try {
      const { container } = render(<App />);

      // Wait for initial preset load
      const summaryHeading = await screen.findByText(/How this answer was computed/i);
      expect(summaryHeading).toBeInTheDocument();

      // D8/D9: No developer protocol jargon in main header
      expect(container.textContent).not.toContain("Tao + Wry");
      expect(container.textContent).not.toContain("Two-Hop GBNF");

      // D16: aria-pressed on active preset button & aria-expanded on details toggle
      const activePreset = container.querySelector('.scenario-btn[aria-pressed="true"]');
      expect(activePreset).not.toBeNull();
      const inspectorBtn = container.querySelector(".inspector-toggle");
      expect(inspectorBtn).toHaveAttribute("aria-expanded", "false");

      // D10: Polite live region present
      const liveRegion = container.querySelector('[role="status"][aria-live="polite"]');
      expect(liveRegion).not.toBeNull();

      // Demo Mode indicator when mode === "deterministic_demo"
      const textarea = document.getElementById("ask-question") as HTMLTextAreaElement;
      fireEvent.change(textarea, { target: { value: "How is enrollment trending?" } });
      fireEvent.submit(textarea.closest("form")!);
      expect(await screen.findByText(/Demo Mode/i)).toBeInTheDocument();
    } finally {
      globalThis.fetch = origFetch;
    }
  });
});
