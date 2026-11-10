import React from "react";
import { CategoryBarChartProps } from "../../schemas/workspace-ui";
import { detectColumnIsRatio, formatMetricValue } from "../../lib/formatters";

interface ComponentProps {
  spec: CategoryBarChartProps;
  rows: Record<string, unknown>[];
}

const BAR_COLORS = ["#38bdf8", "#a78bfa", "#34d399"];

export const CategoryBarChart: React.FC<ComponentProps> = ({ spec, rows }) => {
  const ratioByCol = Object.fromEntries(
    spec.value_columns.map((col) => [
      col,
      detectColumnIsRatio(rows.map((r) => r[col])),
    ])
  );
  const maxVal = Math.max(
    1,
    ...rows.flatMap((r) =>
      spec.value_columns.map((col) => Math.abs(Number(r[col] ?? 0)))
    )
  );

  return (
    <section
      className="workspace-panel"
      aria-label={`Category Breakdown: ${spec.category_column}`}
      data-testid="category-bar-chart"
    >
      <header className="panel-header">
        <div>
          <h3 className="panel-title">
            Category Breakdown ({spec.chart_variant})
          </h3>
          <span className="panel-subtitle">
            Category: <code>{spec.category_column}</code> • Values:{" "}
            <code>{spec.value_columns.join(", ")}</code>
          </span>
        </div>
        <div className="legend-row">
          {spec.value_columns.map((col, idx) => (
            <span key={col} className="legend-pill">
              <span
                className="legend-dot"
                style={{ backgroundColor: BAR_COLORS[idx % BAR_COLORS.length] }}
              />
              {col}
            </span>
          ))}
        </div>
      </header>

      <div className="category-bars-list">
        {rows.map((row, rIdx) => {
          const catLabel = String(row[spec.category_column] ?? `Row ${rIdx + 1}`);
          return (
            <div key={`${catLabel}-${rIdx}`} className="cat-row">
              <div className="cat-row-header">
                <span className="cat-label">{catLabel}</span>
                <span className="cat-values">
                  {spec.value_columns
                    .map(
                      (col) =>
                        `${col}: ${formatMetricValue(row[col], spec.value_format, ratioByCol[col])}`
                    )
                    .join(" | ")}
                </span>
              </div>
              <div className="cat-tracks">
                {spec.value_columns.map((col, cIdx) => {
                  const num = Math.max(0, Number(row[col] ?? 0));
                  const pct = Math.min(100, Math.max(2, (num / maxVal) * 100));
                  return (
                    <div key={col} className="cat-track-bg">
                      <div
                        className="cat-track-fill"
                        style={{
                          width: `${pct}%`,
                          backgroundColor: BAR_COLORS[cIdx % BAR_COLORS.length],
                        }}
                      />
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
};
