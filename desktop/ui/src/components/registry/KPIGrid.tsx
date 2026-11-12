import React from "react";
import { KPIGridProps } from "../../schemas/workspace-ui";
import { detectColumnIsRatio, formatMetricValue } from "../../lib/formatters";

interface ComponentProps {
  spec: KPIGridProps;
  rows: Record<string, unknown>[];
}

const ADVERSE_KEYWORDS = ["chronic", "absent", "suspension", "incident", "risk"];

function isAdverseMetric(label: string, colName: string): boolean {
  const combined = `${label} ${colName}`.toLowerCase();
  return ADVERSE_KEYWORDS.some((kw) => combined.includes(kw));
}

export const KPIGrid: React.FC<ComponentProps> = ({ spec, rows }) => {
  if (rows.length === 0) {
    return (
      <section className="workspace-panel" aria-label="Key Highlights">
        <div className="kpi-grid">
          {spec.metrics.map((m, idx) => (
            <article key={`${m.value_column}-${idx}`} className="kpi-card">
              <span className="kpi-label">{m.label}</span>
              <strong className="kpi-value" data-testid={`kpi-value-${m.value_column}`}>
                No data
              </strong>
            </article>
          ))}
        </div>
      </section>
    );
  }

  const firstRow = rows[0] ?? {};

  return (
    <section className="workspace-panel" aria-label="Key Highlights">
      <div className="kpi-grid">
        {spec.metrics.map((m, idx) => {
          const rawVal = firstRow[m.value_column];
          const isRatioScale = detectColumnIsRatio(
            rows.map((r) => r[m.value_column])
          );
          const deltaVal = m.delta_column
            ? Number(firstRow[m.delta_column])
            : undefined;
          const hasDelta = deltaVal !== undefined && !Number.isNaN(deltaVal);
          const isIncrease = hasDelta && deltaVal >= 0;
          const adverse = isAdverseMetric(m.label, m.value_column);
          const isFavorable = adverse ? !isIncrease : isIncrease;

          return (
            <article key={`${m.value_column}-${idx}`} className="kpi-card">
              <span className="kpi-label">{m.label}</span>
              <strong
                className="kpi-value"
                data-testid={`kpi-value-${m.value_column}`}
              >
                {formatMetricValue(rawVal, m.value_format, isRatioScale)}
              </strong>
              <div className="kpi-footer">
                {hasDelta ? (
                  <span
                    className={`kpi-delta ${
                      isFavorable ? "kpi-delta-pos" : "kpi-delta-neg"
                    }`}
                  >
                    {isIncrease ? "+" : ""}
                    {deltaVal.toFixed(1)}%
                  </span>
                ) : null}
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
};
