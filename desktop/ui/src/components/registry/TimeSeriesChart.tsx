import React, { useMemo } from "react";
import { TimeSeriesChartProps } from "../../schemas/workspace-ui";
import { detectColumnIsRatio, formatMetricValue } from "../../lib/formatters";

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
  const isRatioScale = useMemo(
    () =>
      detectColumnIsRatio(
        rows.flatMap((r) => spec.y_columns.map((col) => r[col]))
      ),
    [rows, spec.y_columns]
  );

  // Single-pass O(rows) aggregation inside useMemo
  const { seriesNames, periodBuckets, maxTotal } = useMemo(() => {
    const xOrder: string[] = [];
    const xSeen = new Set<string>();
    const sOrder: string[] = [];
    const sSeen = new Set<string>();
    const primaryY = spec.y_columns[0];

    const grouped = new Map<string, Map<string, number>>();

    if (!spec.series_column) {
      for (const yCol of spec.y_columns) {
        if (!sSeen.has(yCol)) {
          sSeen.add(yCol);
          sOrder.push(yCol);
        }
      }
    }

    for (const row of rows) {
      const xVal = String(row[spec.x_column] ?? "");
      if (!xVal) continue;
      if (!xSeen.has(xVal)) {
        xSeen.add(xVal);
        xOrder.push(xVal);
      }
      let bucketMap = grouped.get(xVal);
      if (!bucketMap) {
        bucketMap = new Map<string, number>();
        grouped.set(xVal, bucketMap);
      }

      if (spec.series_column) {
        const sName = String(row[spec.series_column] ?? "");
        if (!sName) continue;
        if (!sSeen.has(sName)) {
          sSeen.add(sName);
          sOrder.push(sName);
        }
        const v = Number(row[primaryY] ?? 0);
        if (Number.isFinite(v)) {
          bucketMap.set(sName, (bucketMap.get(sName) ?? 0) + v);
        }
      } else {
        for (const yCol of spec.y_columns) {
          const v = Number(row[yCol] ?? 0);
          if (Number.isFinite(v)) {
            bucketMap.set(yCol, (bucketMap.get(yCol) ?? 0) + v);
          }
        }
      }
    }

    const buckets = xOrder.map((xVal) => {
      const bMap = grouped.get(xVal) ?? new Map<string, number>();
      const seriesValues = sOrder.map((sName, sIdx) => ({
        series: sName,
        value: bMap.get(sName) ?? 0,
        color: SERIES_PALETTE[sIdx % SERIES_PALETTE.length],
      }));
      const total = seriesValues.reduce((sum, item) => sum + item.value, 0);
      return { xVal, seriesValues, total };
    });

    const computedMax = Math.max(
      1,
      ...buckets.map((b) =>
        spec.chart_variant === "stacked_bar"
          ? b.total
          : Math.max(0, ...b.seriesValues.map((s) => s.value))
      )
    );

    return {
      seriesNames: sOrder,
      periodBuckets: buckets,
      maxTotal: computedMax,
    };
  }, [rows, spec.x_column, spec.y_columns, spec.series_column, spec.chart_variant]);

  const isLineOrArea =
    spec.chart_variant === "line" || spec.chart_variant === "area";
  const showStackedTotals =
    spec.chart_variant === "stacked_bar" && spec.value_format !== "percent";

  return (
    <section
      className="workspace-panel"
      aria-label={`Trend over ${spec.x_column}`}
    >
      <header className="panel-header">
        <div>
          <h3 className="panel-title">Trends Over Time</h3>
          <span className="panel-subtitle">
            Showing {spec.y_columns.join(", ")} by {spec.x_column}
            {spec.series_column ? ` grouped by ${spec.series_column}` : ""}
          </span>
        </div>
        <div className="legend-row">
          {seriesNames.map((name, idx) => (
            <span key={name} className="legend-pill">
              <span
                className="legend-dot"
                style={{
                  backgroundColor: SERIES_PALETTE[idx % SERIES_PALETTE.length],
                }}
              />
              {name}
            </span>
          ))}
        </div>
      </header>

      {isLineOrArea ? (
        <div className="timeseries-svg-wrap" data-testid="timeseries-chart">
          <svg
            viewBox="0 0 600 200"
            width="100%"
            height="200"
            role="img"
            aria-label={`Trend chart for ${spec.y_columns.join(", ")}`}
          >
            {seriesNames.map((sName, sIdx) => {
              const color = SERIES_PALETTE[sIdx % SERIES_PALETTE.length];
              const count = Math.max(1, periodBuckets.length);
              const pts = periodBuckets.map((bucket, bIdx) => {
                const sv = bucket.seriesValues[sIdx]?.value ?? 0;
                const x =
                  count === 1 ? 300 : 40 + (bIdx / (count - 1)) * 520;
                const y = 175 - (Math.max(0, sv) / maxTotal) * 150;
                return { x, y, xVal: bucket.xVal, value: sv };
              });
              const polyPoints = pts.map((p) => `${p.x},${p.y}`).join(" ");
              const areaPath =
                pts.length > 0
                  ? `M ${pts[0].x},175 L ${pts
                      .map((p) => `${p.x},${p.y}`)
                      .join(" L ")} L ${pts[pts.length - 1].x},175 Z`
                  : "";

              return (
                <g key={sName}>
                  {spec.chart_variant === "area" && areaPath && (
                    <path d={areaPath} fill={color} fillOpacity={0.18} />
                  )}
                  <polyline
                    fill="none"
                    stroke={color}
                    strokeWidth={2.5}
                    points={polyPoints}
                  />
                  {pts.map((pt) => {
                    const formatted = formatMetricValue(
                      pt.value,
                      spec.value_format,
                      isRatioScale
                    );
                    const label = `${pt.xVal} • ${sName}: ${formatted}`;
                    return (
                      <circle
                        key={`${sName}-${pt.xVal}`}
                        cx={pt.x}
                        cy={pt.y}
                        r={4.5}
                        fill={color}
                        tabIndex={0}
                        aria-label={label}
                      >
                        <title>{label}</title>
                      </circle>
                    );
                  })}
                </g>
              );
            })}
          </svg>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              paddingInline: "1.5rem",
            }}
          >
            {periodBuckets.map((b) => (
              <span key={b.xVal} className="ts-x-label">
                {b.xVal}
              </span>
            ))}
          </div>
        </div>
      ) : (
        <div className="timeseries-grid" data-testid="timeseries-chart">
          {periodBuckets.map((bucket) => (
            <div key={bucket.xVal} className="ts-column">
              <div className="ts-bars-area">
                {spec.chart_variant === "stacked_bar" ? (
                  <div className="ts-stacked-bar">
                    {bucket.seriesValues.map((sv) => {
                      const heightPct = Math.max(2, (sv.value / maxTotal) * 100);
                      const label = `${bucket.xVal} • ${sv.series}: ${formatMetricValue(
                        sv.value,
                        spec.value_format,
                        isRatioScale
                      )}`;
                      return (
                        <div
                          key={sv.series}
                          className="ts-bar-segment"
                          tabIndex={0}
                          role="img"
                          aria-label={label}
                          style={{
                            height: `${heightPct}%`,
                            backgroundColor: sv.color,
                          }}
                          title={label}
                        />
                      );
                    })}
                  </div>
                ) : (
                  <div className="ts-grouped-bars">
                    {bucket.seriesValues.map((sv) => {
                      const heightPct = Math.max(4, (sv.value / maxTotal) * 100);
                      const label = `${bucket.xVal} • ${sv.series}: ${formatMetricValue(
                        sv.value,
                        spec.value_format,
                        isRatioScale
                      )}`;
                      return (
                        <div
                          key={sv.series}
                          className="ts-single-bar"
                          tabIndex={0}
                          role="img"
                          aria-label={label}
                          style={{
                            height: `${heightPct}%`,
                            backgroundColor: sv.color,
                          }}
                          title={label}
                        />
                      );
                    })}
                  </div>
                )}
              </div>
              {showStackedTotals && (
                <span className="ts-total-label">
                  {formatMetricValue(bucket.total, spec.value_format, isRatioScale)}
                </span>
              )}
              <span className="ts-x-label">{bucket.xVal}</span>
            </div>
          ))}
        </div>
      )}

      <table className="sr-only">
        <caption>Aggregated time series values for {spec.x_column}</caption>
        <thead>
          <tr>
            <th scope="col">{spec.x_column}</th>
            {seriesNames.map((s) => (
              <th key={s} scope="col">
                {s}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {periodBuckets.map((bucket) => (
            <tr key={bucket.xVal}>
              <th scope="row">{bucket.xVal}</th>
              {bucket.seriesValues.map((sv) => (
                <td key={sv.series}>
                  {formatMetricValue(sv.value, spec.value_format, isRatioScale)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
};
