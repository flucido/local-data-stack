import React, { useMemo } from "react";
import {
  DuckDBResultSummary,
  FilterMutation,
  RenderWorkspaceUISchema,
  validateWorkspaceUISemantics,
} from "../../schemas/workspace-ui";
import { KPIGrid } from "./KPIGrid";
import { TimeSeriesChart } from "./TimeSeriesChart";
import { CategoryBarChart } from "./CategoryBarChart";
import { BudgetVarianceChart } from "./BudgetVarianceChart";
import { DataTable } from "./DataTable";
import { FilterBar } from "./FilterBar";

const MemoKPIGrid = React.memo(KPIGrid);
const MemoTimeSeriesChart = React.memo(TimeSeriesChart);
const MemoCategoryBarChart = React.memo(CategoryBarChart);
const MemoBudgetVarianceChart = React.memo(BudgetVarianceChart);
const MemoDataTable = React.memo(DataTable);
const MemoFilterBar = React.memo(FilterBar);

interface WorkspaceRendererProps {
  uiPayload: unknown;
  resultSummary?: DuckDBResultSummary;
  explanation?: string;
  sql?: string;
  rows: Record<string, unknown>[];
  baseRows: Record<string, unknown>[];
  onApplyFilters: (filters: FilterMutation[]) => void;
  filterLatencyMs?: number | null;
}

const WorkspaceRendererInner: React.FC<WorkspaceRendererProps> = ({
  uiPayload,
  resultSummary,
  explanation,
  sql,
  rows,
  baseRows,
  onApplyFilters,
  filterLatencyMs,
}) => {
  const parsed = useMemo(
    () => RenderWorkspaceUISchema.safeParse(uiPayload),
    [uiPayload]
  );

  const semanticCheck = useMemo(
    () =>
      parsed.success
        ? validateWorkspaceUISemantics(parsed.data, resultSummary)
        : { valid: false, errors: [] },
    [parsed, resultSummary]
  );

  if (!parsed.success) {
    return (
      <div className="validation-error-banner" role="alert">
        <strong>Unable to display this answer layout:</strong>
        <ul>
          {parsed.error.issues.map((issue, idx) => (
            <li key={idx}>
              <code>{issue.path.join(".")}</code>: {issue.message}
            </li>
          ))}
        </ul>
      </div>
    );
  }

  const { title, narrative_summary, components } = parsed.data.arguments;
  const turnSignature = `${title}-${resultSummary?.query_id ?? baseRows.length}`;

  return (
    <div className="workspace-container" data-testid="workspace-renderer">
      <div className="workspace-summary-card">
        <div>
          <h2 className="workspace-title">{title}</h2>
          <p className="workspace-narrative">{narrative_summary}</p>
          {(explanation || sql) && (
            <details className="explanation-disclosure">
              <summary>How this answer was computed</summary>
              {explanation && (
                <p className="explanation-text">{explanation}</p>
              )}
              {sql && <pre className="inspector-code">{sql}</pre>}
            </details>
          )}
        </div>
        {!semanticCheck.valid && (
          <div className="semantic-warning">
            Layout note: {semanticCheck.errors.join("; ")}
          </div>
        )}
      </div>

      <div className="workspace-panels-stack">
        {components.map((comp, idx) => {
          const key = `${turnSignature}-${comp.component}-${idx}`;
          switch (comp.component) {
            case "KPIGrid":
              return <MemoKPIGrid key={key} spec={comp} rows={rows} />;
            case "TimeSeriesChart":
              return <MemoTimeSeriesChart key={key} spec={comp} rows={rows} />;
            case "CategoryBarChart":
              return <MemoCategoryBarChart key={key} spec={comp} rows={rows} />;
            case "BudgetVarianceChart":
              return (
                <MemoBudgetVarianceChart key={key} spec={comp} rows={rows} />
              );
            case "DataTable":
              return <MemoDataTable key={key} spec={comp} rows={rows} />;
            case "FilterBar":
              return (
                <MemoFilterBar
                  key={key}
                  spec={comp}
                  baseRows={baseRows}
                  onApplyFilters={onApplyFilters}
                  filterLatencyMs={filterLatencyMs}
                />
              );
            default:
              return null;
          }
        })}
      </div>
    </div>
  );
};

export const WorkspaceRenderer = React.memo(WorkspaceRendererInner);
