import React from "react";
import { KPIGridProps } from "../../schemas/workspace-ui";
import { detectColumnIsRatio, formatMetricValue } from "../../lib/formatters";

interface ComponentProps {
  spec: KPIGridProps;
  rows: Record<string, unknown>[];
}

export const KPIGrid: React.FC<ComponentProps> = ({ spec, rows }) => {
  const firstRow = rows[0] ?? {};

  return (
    <section className="workspace-panel" aria-label="Key Performance Indicators">
      <div className="kpi-grid">
        {spec.metrics.map((m, idx) => {
          const rawVal = firstRow[m.value_column];
          const isRatioScale = detectColumnIsRatio(rows.map((r) => r[m.value_column]));
          const deltaVal = m.delta_column ? Number(firstRow[m.delta_column]) : undefined;
          const hasDelta = deltaVal !== undefined && !Number.isNaN(deltaVal);
          const isPositive = hasDelta && deltaVal >= 0;

          return (
            <article key={`${m.value_column}-${idx}`} className="kpi-card">
              <span className="kpi-label">{m.label}</span>
              <strong className="kpi-value" data-testid={`kpi-value-${m.value_column}`}>
                {formatMetricValue(rawVal, m.value_format, isRatioScale)}
              </strong>
              <div className="kpi-footer">
                {hasDelta ? (
                  <span
                    className={`kpi-delta ${isPositive ? "kpi-delta-pos" : "kpi-delta-neg"}`}
                  >
                    {isPositive ? "+" : ""}
                    {deltaVal.toFixed(1)}%
                  </span>
                ) : (
                  <span className="kpi-col-badge">{m.value_column}</span>
                )}
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
};
