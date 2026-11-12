import React, { useMemo } from "react";
import { CategoryBarChartProps } from "../../schemas/workspace-ui";
import { detectColumnIsRatio, formatMetricValue } from "../../lib/formatters";

interface ComponentProps {
  spec: CategoryBarChartProps;
  rows: Record<string, unknown>[];
}

const BAR_COLORS = ["#38bdf8", "#a78bfa", "#34d399", "#fbbf24", "#f472b6"];

export const CategoryBarChart: React.FC<ComponentProps> = ({ spec, rows }) => {
  const { categories, seriesKeys, maxVal, isRatioBySeries } = useMemo(() => {
    const primaryValCol = spec.value_columns[0];
    const catOrder: string[] = [];
    const catSeen = new Set<string>();
    const serOrder: string[] = [];
    const serSeen = new Set<string>();

    if (!spec.series_column) {
      for (const vc of spec.value_columns) {
        if (!serSeen.has(vc)) {
          serSeen.add(vc);
          serOrder.push(vc);
        }
      }
    }

    const matrix = new Map<string, Map<string, number>>();
    for (const r of rows) {
      const cat = String(r[spec.category_column] ?? "Unspecified");
      if (!catSeen.has(cat)) {
        catSeen.add(cat);
        catOrder.push(cat);
      }
      let sMap = matrix.get(cat);
      if (!sMap) {
        sMap = new Map<string, number>();
        matrix.set(cat, sMap);
      }

      if (spec.series_column) {
        const sKey = String(r[spec.series_column] ?? "Default");
        if (!serSeen.has(sKey)) {
          serSeen.add(sKey);
          serOrder.push(sKey);
        }
        const v = Number(r[primaryValCol] ?? 0);
        if (Number.isFinite(v)) {
          sMap.set(sKey, (sMap.get(sKey) ?? 0) + v);
        }
      } else {
        for (const vc of spec.value_columns) {
          const v = Number(r[vc] ?? 0);
          if (Number.isFinite(v)) {
            sMap.set(vc, (sMap.get(vc) ?? 0) + v);
          }
        }
      }
    }

    const items = catOrder.map((cat) => {
      const sMap = matrix.get(cat) ?? new Map<string, number>();
      const values = serOrder.map((sKey) => ({
        key: sKey,
        value: sMap.get(sKey) ?? 0,
      }));
      const total = values.reduce((acc, item) => acc + Math.max(0, item.value), 0);
      return { cat, values, total };
    });

    let computedMax = 1;
    for (const item of items) {
      if (spec.chart_variant === "stacked") {
        if (item.total > computedMax) computedMax = item.total;
      } else {
        for (const v of item.values) {
          if (Math.abs(v.value) > computedMax) computedMax = Math.abs(v.value);
        }
      }
    }

    const ratioFlags: Record<string, boolean> = {};
    for (const sKey of serOrder) {
      const colVals = items.map(
        (it) => it.values.find((v) => v.key === sKey)?.value ?? 0
      );
      ratioFlags[sKey] = detectColumnIsRatio(colVals);
    }

    return {
      categories: items,
      seriesKeys: serOrder,
      maxVal: computedMax,
      isRatioBySeries: ratioFlags,
    };
  }, [rows, spec.category_column, spec.value_columns, spec.series_column, spec.chart_variant]);

  const isVertical = spec.chart_variant === "vertical";
  const isStacked = spec.chart_variant === "stacked";

  return (
    <section
      className="workspace-panel"
      aria-label={`Comparison by ${spec.category_column}`}
      data-testid="category-bar-chart"
    >
      <header className="panel-header">
        <div>
          <h3 className="panel-title">Comparison by {spec.category_column}</h3>
          <span className="panel-subtitle">
            Comparing {spec.value_columns.join(", ")}
            {spec.series_column ? ` across ${spec.series_column}` : ""}
          </span>
        </div>
        <div className="legend-row">
          {seriesKeys.map((key, idx) => (
            <span key={key} className="legend-pill">
              <span
                className="legend-dot"
                style={{ backgroundColor: BAR_COLORS[idx % BAR_COLORS.length] }}
              />
              {key}
            </span>
          ))}
        </div>
      </header>

      {isVertical ? (
        <div className="timeseries-grid">
          {categories.map((item) => (
            <div key={item.cat} className="ts-column">
              <div className="ts-bars-area">
                <div className="ts-grouped-bars">
                  {item.values.map((v, cIdx) => {
                    const heightPct = Math.min(
                      100,
                      Math.max(4, (Math.max(0, v.value) / maxVal) * 100)
                    );
                    const formatted = formatMetricValue(
                      v.value,
                      spec.value_format,
                      isRatioBySeries[v.key]
                    );
                    return (
                      <div
                        key={v.key}
                        className="ts-single-bar"
                        tabIndex={0}
                        role="img"
                        aria-label={`${item.cat} • ${v.key}: ${formatted}`}
                        title={`${item.cat} • ${v.key}: ${formatted}`}
                        style={{
                          height: `${heightPct}%`,
                          backgroundColor: BAR_COLORS[cIdx % BAR_COLORS.length],
                        }}
                      />
                    );
                  })}
                </div>
              </div>
              <span className="ts-x-label">{item.cat}</span>
            </div>
          ))}
        </div>
      ) : (
        <div
          className="category-bars-list"
          data-variant={spec.chart_variant}
        >
          {categories.map((item, rIdx) => (
            <div key={`${item.cat}-${rIdx}`} className="cat-row">
              <div className="cat-row-header">
                <span className="cat-label">{item.cat}</span>
                <span className="cat-values">
                  {item.values
                    .map(
                      (v) =>
                        `${v.key}: ${formatMetricValue(
                          v.value,
                          spec.value_format,
                          isRatioBySeries[v.key]
                        )}`
                    )
                    .join(" | ")}
                </span>
              </div>
              {isStacked ? (
                <div
                  className="cat-track-bg"
                  style={{ display: "flex", overflow: "hidden" }}
                >
                  {item.values.map((v, cIdx) => {
                    const pct = Math.min(
                      100,
                      Math.max(0, (Math.max(0, v.value) / maxVal) * 100)
                    );
                    return (
                      <div
                        key={v.key}
                        className="cat-track-fill"
                        style={{
                          width: `${pct}%`,
                          backgroundColor: BAR_COLORS[cIdx % BAR_COLORS.length],
                        }}
                      />
                    );
                  })}
                </div>
              ) : (
                <div className="cat-tracks">
                  {item.values.map((v, cIdx) => {
                    const pct = Math.min(
                      100,
                      Math.max(2, (Math.max(0, v.value) / maxVal) * 100)
                    );
                    return (
                      <div key={v.key} className="cat-track-bg">
                        <div
                          className="cat-track-fill"
                          style={{
                            width: `${pct}%`,
                            backgroundColor:
                              BAR_COLORS[cIdx % BAR_COLORS.length],
                          }}
                        />
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  );
};
