import React, { useMemo, useState } from "react";
import { FilterBarProps, FilterMutation } from "../../schemas/workspace-ui";

interface ComponentProps {
  spec: FilterBarProps;
  baseRows: Record<string, unknown>[];
  onApplyFilters: (filters: FilterMutation[]) => void;
  filterLatencyMs?: number | null;
}

export const FilterBar: React.FC<ComponentProps> = ({
  spec,
  baseRows,
  onApplyFilters,
  filterLatencyMs,
}) => {
  const [filterMap, setFilterMap] = useState<Record<string, FilterMutation>>({});

  // Compute distinct options and min/max bounds per column from baseRows
  const columnMeta = useMemo(() => {
    const meta: Record<
      string,
      { distinct: string[]; minNum: number; maxNum: number }
    > = {};
    for (const ctrl of spec.controls) {
      const vals = baseRows
        .map((r) => r[ctrl.column])
        .filter((v) => v !== null && v !== undefined && v !== "");
      const distinct = Array.from(new Set(vals.map((v) => String(v)))).sort();
      const nums = vals.map(Number).filter((n) => Number.isFinite(n));
      meta[ctrl.column] = {
        distinct,
        minNum: nums.length > 0 ? Math.min(...nums) : 0,
        maxNum: nums.length > 0 ? Math.max(...nums) : 1000,
      };
    }
    return meta;
  }, [spec.controls, baseRows]);

  const updateControl = (col: string, nextMutation: FilterMutation | null) => {
    const updated = { ...filterMap };
    if (!nextMutation) {
      delete updated[col];
    } else {
      updated[col] = nextMutation;
    }
    setFilterMap(updated);
    onApplyFilters(Object.values(updated));
  };

  const resetAll = () => {
    setFilterMap({});
    onApplyFilters([]);
  };

  return (
    <section
      className="workspace-panel filter-bar-panel"
      aria-label="Interactive Query Filters"
      data-testid="filter-bar"
    >
      <div className="filter-bar-header">
        <div className="filter-bar-title-group">
          <span className="filter-badge">Zero-LLM Parameterized CTE</span>
          <span className="panel-subtitle">
            Mutates <code>WITH _base AS (...)</code> in DuckDB without re-running the SLM
            {filterLatencyMs !== null && filterLatencyMs !== undefined ? (
              <> • Last filter: <strong>{filterLatencyMs}ms</strong></>
            ) : null}
          </span>
        </div>
        {Object.keys(filterMap).length > 0 && (
          <button type="button" className="btn-reset" onClick={resetAll}>
            Reset Filters
          </button>
        )}
      </div>

      <div className="filter-controls-grid">
        {spec.controls.map((ctrl) => {
          const meta = columnMeta[ctrl.column] ?? {
            distinct: [],
            minNum: 0,
            maxNum: 100,
          };
          const current = filterMap[ctrl.column];

          if (ctrl.control_type === "multi_select") {
            const selected = new Set((current?.values ?? []).map(String));
            return (
              <div key={ctrl.column} className="filter-control-box">
                <label className="filter-label">{ctrl.label}</label>
                <div className="pill-toggle-row">
                  {meta.distinct.slice(0, 8).map((opt) => {
                    const isActive = selected.has(opt);
                    return (
                      <button
                        key={opt}
                        type="button"
                        className={`filter-pill ${isActive ? "filter-pill-active" : ""}`}
                        onClick={() => {
                          const nextSet = new Set(selected);
                          if (nextSet.has(opt)) {
                            nextSet.delete(opt);
                          } else {
                            nextSet.add(opt);
                          }
                          const arr = Array.from(nextSet);
                          updateControl(
                            ctrl.column,
                            arr.length > 0
                              ? {
                                  column: ctrl.column,
                                  control_type: "multi_select",
                                  values: arr,
                                }
                              : null
                          );
                        }}
                      >
                        {opt}
                      </button>
                    );
                  })}
                </div>
              </div>
            );
          }

          if (ctrl.control_type === "date_range") {
            const minDate = String(current?.min ?? meta.distinct[0] ?? "");
            const maxDate = String(
              current?.max ?? meta.distinct[meta.distinct.length - 1] ?? ""
            );
            return (
              <div key={ctrl.column} className="filter-control-box">
                <label className="filter-label">{ctrl.label}</label>
                <div className="range-select-row">
                  <select
                    aria-label={`${ctrl.label} Start`}
                    className="filter-select"
                    value={minDate}
                    onChange={(e) =>
                      updateControl(ctrl.column, {
                        column: ctrl.column,
                        control_type: "date_range",
                        min: e.target.value,
                        max: maxDate,
                      })
                    }
                  >
                    {meta.distinct.map((d) => (
                      <option key={`min-${d}`} value={d}>
                        From: {d}
                      </option>
                    ))}
                  </select>
                  <select
                    aria-label={`${ctrl.label} End`}
                    className="filter-select"
                    value={maxDate}
                    onChange={(e) =>
                      updateControl(ctrl.column, {
                        column: ctrl.column,
                        control_type: "date_range",
                        min: minDate,
                        max: e.target.value,
                      })
                    }
                  >
                    {meta.distinct.map((d) => (
                      <option key={`max-${d}`} value={d}>
                        To: {d}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            );
          }

          if (ctrl.control_type === "numeric_range") {
            const currentMin =
              current?.min !== undefined ? Number(current.min) : meta.minNum;
            return (
              <div key={ctrl.column} className="filter-control-box">
                <label className="filter-label">
                  {ctrl.label} (Min: {currentMin.toFixed(0)})
                </label>
                <input
                  type="range"
                  aria-label={ctrl.label}
                  min={Math.floor(meta.minNum)}
                  max={Math.ceil(meta.maxNum)}
                  value={currentMin}
                  onChange={(e) =>
                    updateControl(ctrl.column, {
                      column: ctrl.column,
                      control_type: "numeric_range",
                      min: Number(e.target.value),
                      max: meta.maxNum,
                    })
                  }
                />
              </div>
            );
          }

          return (
            <div key={ctrl.column} className="filter-control-box">
              <label className="filter-label">{ctrl.label}</label>
              <input
                type="search"
                aria-label={ctrl.label}
                className="table-search-input"
                placeholder={`Filter ${ctrl.column}...`}
                value={current?.query ?? ""}
                onChange={(e) => {
                  const val = e.target.value;
                  updateControl(
                    ctrl.column,
                    val.trim()
                      ? {
                          column: ctrl.column,
                          control_type: "search",
                          query: val,
                        }
                      : null
                  );
                }}
              />
            </div>
          );
        })}
      </div>
    </section>
  );
};
