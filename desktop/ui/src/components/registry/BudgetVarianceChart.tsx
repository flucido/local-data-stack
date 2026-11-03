import React from "react";
import { BudgetVarianceChartProps } from "../../schemas/workspace-ui";
import { formatMetricValue } from "../../lib/formatters";

interface ComponentProps {
  spec: BudgetVarianceChartProps;
  rows: Record<string, unknown>[];
}

export const BudgetVarianceChart: React.FC<ComponentProps> = ({ spec, rows }) => {
  const maxBound = Math.max(
    1,
    ...rows.map((r) =>
      Math.max(
        Number(r[spec.actual_column] ?? 0),
        Number(r[spec.budget_column] ?? 0)
      )
    )
  );

  return (
    <section
      className="workspace-panel"
      aria-label="Budget vs Actual Variance"
      data-testid="budget-variance-chart"
    >
      <header className="panel-header">
        <div>
          <h3 className="panel-title">Actual vs. Target Budget Variance</h3>
          <span className="panel-subtitle">
            Actual: <code>{spec.actual_column}</code> vs. Target:{" "}
            <code>{spec.budget_column}</code>
          </span>
        </div>
        <div className="legend-row">
          <span className="legend-pill">
            <span className="legend-dot" style={{ backgroundColor: "#34d399" }} />
            On / Under Budget
          </span>
          <span className="legend-pill">
            <span className="legend-dot" style={{ backgroundColor: "#f87171" }} />
            Over Budget
          </span>
        </div>
      </header>

      <div className="variance-list">
        {rows.map((row, idx) => {
          const cat = String(row[spec.category_column] ?? `Item ${idx + 1}`);
          const actual = Number(row[spec.actual_column] ?? 0);
          const budget = Number(row[spec.budget_column] ?? 0);
          const diff =
            spec.variance_column && row[spec.variance_column] !== undefined
              ? Number(row[spec.variance_column])
              : actual - budget;
          const isOver = diff > 0.01;
          const actualPct = Math.min(100, Math.max(2, (actual / maxBound) * 100));
          const budgetPct = Math.min(100, Math.max(2, (budget / maxBound) * 100));

          return (
            <div key={`${cat}-${idx}`} className="variance-row">
              <div className="variance-meta">
                <span className="cat-label">{cat}</span>
                <div className="variance-numbers">
                  <span>
                    Actual: <strong>{formatMetricValue(actual, spec.value_format)}</strong>
                  </span>
                  <span>
                    Budget: <strong>{formatMetricValue(budget, spec.value_format)}</strong>
                  </span>
                  <span
                    className={`variance-badge ${
                      isOver ? "variance-over" : "variance-under"
                    }`}
                  >
                    {diff > 0 ? "+" : ""}
                    {formatMetricValue(diff, spec.value_format)}
                  </span>
                </div>
              </div>
              <div className="bullet-track">
                <div
                  className="bullet-actual"
                  style={{
                    width: `${actualPct}%`,
                    backgroundColor: isOver ? "#f87171" : "#34d399",
                  }}
                />
                <div
                  className="bullet-marker"
                  style={{ left: `${budgetPct}%` }}
                  title={`Budget Target: ${formatMetricValue(budget, spec.value_format)}`}
                />
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
};
