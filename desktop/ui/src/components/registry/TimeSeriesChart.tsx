import React from "react";
import { TimeSeriesChartProps } from "../../schemas/workspace-ui";
import { formatMetricValue } from "../../lib/formatters";

interface ComponentProps {
  spec: TimeSeriesChartProps;
  rows: Record<string, unknown>[];
}

const SERIES_PALETTE = [
  "#38bdf8",
  "#34d399",
  "#f472b6",
  "#fbbf24",
  "#a78bfa",
  "#fb7185",
];

export const TimeSeriesChart: React.FC<ComponentProps> = ({ spec, rows }) => {
  const xValues = Array.from(
    new Set(rows.map((r) => String(r[spec.x_column] ?? "")))
  ).filter(Boolean);

  const primaryY = spec.y_columns[0];
  const seriesNames = spec.series_column
    ? Array.from(new Set(rows.map((r) => String(r[spec.series_column!] ?? "")))).filter(Boolean)
    : spec.y_columns;

  // Compute totals per X period for scaling
  const periodBuckets = xValues.map((xVal) => {
    const matching = rows.filter((r) => String(r[spec.x_column] ?? "") === xVal);
    const seriesValues = seriesNames.map((sName, sIdx) => {
      let val = 0;
      if (spec.series_column) {
        const found = matching.find((r) => String(r[spec.series_column!] ?? "") === sName);
        val = Number(found?.[primaryY] ?? 0);
      } else {
        val = matching.reduce((acc, r) => acc + Number(r[sName] ?? 0), 0);
      }
      return {
        series: sName,
        value: Number.isFinite(val) ? val : 0,
        color: SERIES_PALETTE[sIdx % SERIES_PALETTE.length],
      };
    });
    const total = seriesValues.reduce((sum, item) => sum + item.value, 0);
    return { xVal, seriesValues, total };
  });

  const maxTotal = Math.max(
    1,
    ...periodBuckets.map((b) =>
      spec.chart_variant === "stacked_bar"
        ? b.total
        : Math.max(0, ...b.seriesValues.map((s) => s.value))
    )
  );

  return (
    <section className="workspace-panel" aria-label={`Time Series Chart: ${spec.x_column}`}>
      <header className="panel-header">
        <div>
          <h3 className="panel-title">Temporal Trend ({spec.chart_variant.replace("_", " ")})</h3>
          <span className="panel-subtitle">
            X: <code>{spec.x_column}</code> • Y: <code>{spec.y_columns.join(", ")}</code>
            {spec.series_column ? (
              <>
                {" "}
                • Series: <code>{spec.series_column}</code>
              </>
            ) : null}
          </span>
        </div>
        <div className="legend-row">
          {seriesNames.map((name, idx) => (
            <span key={name} className="legend-pill">
              <span
                className="legend-dot"
                style={{ backgroundColor: SERIES_PALETTE[idx % SERIES_PALETTE.length] }}
              />
              {name}
            </span>
          ))}
        </div>
      </header>

      <div className="timeseries-grid" data-testid="timeseries-chart">
        {periodBuckets.map((bucket) => (
          <div key={bucket.xVal} className="ts-column">
            <div className="ts-bars-area">
              {spec.chart_variant === "stacked_bar" ? (
                <div className="ts-stacked-bar">
                  {bucket.seriesValues.map((sv) => {
                    const heightPct = Math.max(2, (sv.value / maxTotal) * 100);
                    return (
                      <div
                        key={sv.series}
                        className="ts-bar-segment"
                        style={{
                          height: `${heightPct}%`,
                          backgroundColor: sv.color,
                        }}
                        title={`${bucket.xVal} • ${sv.series}: ${formatMetricValue(
                          sv.value,
                          spec.value_format
                        )}`}
                      />
                    );
                  })}
                </div>
              ) : (
                <div className="ts-grouped-bars">
                  {bucket.seriesValues.map((sv) => {
                    const heightPct = Math.max(4, (sv.value / maxTotal) * 100);
                    return (
                      <div
                        key={sv.series}
                        className="ts-single-bar"
                        style={{
                          height: `${heightPct}%`,
                          backgroundColor: sv.color,
                        }}
                        title={`${bucket.xVal} • ${sv.series}: ${formatMetricValue(
                          sv.value,
                          spec.value_format
                        )}`}
                      />
                    );
                  })}
                </div>
              )}
            </div>
            <span className="ts-total-label">
              {formatMetricValue(bucket.total, spec.value_format)}
            </span>
            <span className="ts-x-label">{bucket.xVal}</span>
          </div>
        ))}
      </div>
    </section>
  );
};
