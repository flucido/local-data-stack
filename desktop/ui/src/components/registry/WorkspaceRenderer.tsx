import React from "react";
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

interface WorkspaceRendererProps {
  uiPayload: unknown;
  resultSummary?: DuckDBResultSummary;
  rows: Record<string, unknown>[];
  baseRows: Record<string, unknown>[];
  onApplyFilters: (filters: FilterMutation[]) => void;
  filterLatencyMs?: number | null;
}

export const WorkspaceRenderer: React.FC<WorkspaceRendererProps> = ({
  uiPayload,
  resultSummary,
  rows,
  baseRows,
  onApplyFilters,
  filterLatencyMs,
}) => {
  const parsed = RenderWorkspaceUISchema.safeParse(uiPayload);
  if (!parsed.success) {
    return (
      <div className="validation-error-banner" role="alert">
        <strong>Hop 2 UI Schema Validation Failed:</strong>
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

  const semanticCheck = validateWorkspaceUISemantics(parsed.data, resultSummary);
  const { title, narrative_summary, components } = parsed.data.arguments;
  const turnSignature = `${title}-${resultSummary?.query_id ?? baseRows.length}`;

  return (
    <div className="workspace-container" data-testid="workspace-renderer">
      <div className="workspace-summary-card">
        <div>
          <h2 className="workspace-title">{title}</h2>
          <p className="workspace-narrative">{narrative_summary}</p>
        </div>
        {!semanticCheck.valid && (
          <div className="semantic-warning">
            Semantic Notice: {semanticCheck.errors.join("; ")}
          </div>
        )}
      </div>

      <div className="workspace-panels-stack">
        {components.map((comp, idx) => {
          const key = `${turnSignature}-${comp.component}-${idx}`;
          switch (comp.component) {
            case "KPIGrid":
              return <KPIGrid key={key} spec={comp} rows={rows} />;
            case "TimeSeriesChart":
              return <TimeSeriesChart key={key} spec={comp} rows={rows} />;
            case "CategoryBarChart":
              return <CategoryBarChart key={key} spec={comp} rows={rows} />;
            case "BudgetVarianceChart":
              return <BudgetVarianceChart key={key} spec={comp} rows={rows} />;
            case "DataTable":
              return <DataTable key={key} spec={comp} rows={rows} />;
            case "FilterBar":
              return (
                <FilterBar
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
