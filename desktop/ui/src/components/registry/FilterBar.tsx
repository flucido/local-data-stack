import React, { useEffect, useId, useMemo, useRef, useState } from "react";
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
  const baseId = useId();
  const [filterMap, setFilterMap] = useState<Record<string, FilterMutation>>({});
  const [expandedCols, setExpandedCols] = useState<Record<string, boolean>>({});
  const pendingTimerRef = useRef<number | null>(null);

  useEffect(() => {
    setFilterMap({});
    setExpandedCols({});
    return () => {
      if (pendingTimerRef.current !== null) {
        window.clearTimeout(pendingTimerRef.current);
      }
    };
  }, [spec]);

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

  const updateControl = (
    col: string,
    nextMutation: FilterMutation | null,
    debounce = false
  ) => {
    const updated = { ...filterMap };
    if (!nextMutation) {
      delete updated[col];
    } else {
      updated[col] = nextMutation;
    }
    setFilterMap(updated);

    if (pendingTimerRef.current !== null) {
      window.clearTimeout(pendingTimerRef.current);
      pendingTimerRef.current = null;
    }

    const nextList = Object.values(updated);
    if (debounce) {
      pendingTimerRef.current = window.setTimeout(() => {
        pendingTimerRef.current = null;
        onApplyFilters(nextList);
      }, 250);
    } else {
      onApplyFilters(nextList);
    }
  };

  const resetAll = () => {
    if (pendingTimerRef.current !== null) {
      window.clearTimeout(pendingTimerRef.current);
      pendingTimerRef.current = null;
    }
    setFilterMap({});
    onApplyFilters([]);
  };

  return (
    <section
      className="workspace-panel filter-bar-panel"
      aria-label="Filter results"
      data-testid="filter-bar"
    >
      <div className="filter-bar-header">
        <div className="filter-bar-title-group">
          <span className="filter-badge">Quick Filters</span>
          <span className="panel-subtitle">
            Narrow the results below instantly without re-running your question
            {filterLatencyMs !== null && filterLatencyMs !== undefined ? (
              <> • Updated in <strong>{filterLatencyMs}ms</strong></>
            ) : null}
          </span>
        </div>
        {Object.keys(filterMap).length > 0 && (
          <button type="button" className="btn-reset" onClick={resetAll}>
            Clear all filters
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
          const labelId = `${baseId}-lbl-${ctrl.column}`;
          const inputId = `${baseId}-inp-${ctrl.column}`;

          if (ctrl.control_type === "multi_select") {
            const selected = new Set((current?.values ?? []).map(String));
            const isExpanded = Boolean(expandedCols[ctrl.column]);
            const visibleOptions = isExpanded
              ? meta.distinct
              : meta.distinct.slice(0, 8);

            return (
              <div key={ctrl.column} className="filter-control-box">
                <span id={labelId} className="filter-label">
                  {ctrl.label}
                </span>
                <div
                  role="group"
                  aria-labelledby={labelId}
                  className="pill-toggle-row"
                >
                  {visibleOptions.map((opt) => {
                    const isActive = selected.has(opt);
                    return (
                      <button
                        key={opt}
                        type="button"
                        aria-pressed={isActive}
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
                        {isActive ? `✓ ${opt}` : opt}
                      </button>
                    );
                  })}
                  {meta.distinct.length > 8 && (
                    <button
                      type="button"
                      className="filter-pill"
                      onClick={() =>
                        setExpandedCols((prev) => ({
                          ...prev,
                          [ctrl.column]: !isExpanded,
                        }))
                      }
                    >
                      {isExpanded
                        ? "Show fewer"
                        : `Show all (${meta.distinct.length})`}
                    </button>
                  )}
                </div>
              </div>
            );
          }

          if (ctrl.control_type === "single_select") {
            const selectedVal =
              current?.value !== undefined ? String(current.value) : "";
            return (
              <div key={ctrl.column} className="filter-control-box">
                <label htmlFor={inputId} className="filter-label">
                  {ctrl.label}
                </label>
                <select
                  id={inputId}
                  className="filter-select"
                  value={selectedVal}
                  onChange={(e) => {
                    const nextVal = e.target.value;
                    updateControl(
                      ctrl.column,
                      nextVal
                        ? {
                            column: ctrl.column,
                            control_type: "single_select",
                            value: nextVal,
                          }
                        : null
                    );
                  }}
                >
                  <option value="">All</option>
                  {meta.distinct.map((opt) => (
                    <option key={opt} value={opt}>
                      {opt}
                    </option>
                  ))}
                </select>
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
                <span id={labelId} className="filter-label">
                  {ctrl.label}
                </span>
                <div
                  role="group"
                  aria-labelledby={labelId}
                  className="range-select-row"
                >
                  <select
                    aria-label={`${ctrl.label} Start`}
                    className="filter-select"
                    value={minDate}
                    onChange={(e) => {
                      const nextMin = e.target.value;
                      const clampedMax = nextMin > maxDate ? nextMin : maxDate;
                      updateControl(ctrl.column, {
                        column: ctrl.column,
                        control_type: "date_range",
                        min: nextMin,
                        max: clampedMax,
                      });
                    }}
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
                    onChange={(e) => {
                      const nextMax = e.target.value;
                      const clampedMin = nextMax < minDate ? nextMax : minDate;
                      updateControl(ctrl.column, {
                        column: ctrl.column,
                        control_type: "date_range",
                        min: clampedMin,
                        max: nextMax,
                      });
                    }}
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
            const span = meta.maxNum - meta.minNum;
            const isDecimal =
              span <= 10 ||
              !Number.isInteger(meta.minNum) ||
              !Number.isInteger(meta.maxNum);
            const step = isDecimal ? 0.05 : 1;
            const currentMin =
              current?.min !== undefined ? Number(current.min) : meta.minNum;
            const currentMax =
              current?.max !== undefined ? Number(current.max) : meta.maxNum;
            const fmt = (n: number) => (isDecimal ? n.toFixed(2) : n.toFixed(0));

            return (
              <div key={ctrl.column} className="filter-control-box">
                <span id={labelId} className="filter-label">
                  {ctrl.label} ({fmt(currentMin)} – {fmt(currentMax)})
                </span>
                <div role="group" aria-labelledby={labelId} className="range-select-row">
                  <input
                    type="range"
                    aria-label={`${ctrl.label} Minimum`}
                    min={meta.minNum}
                    max={meta.maxNum}
                    step={step}
                    value={currentMin}
                    onChange={(e) => {
                      const nextMin = Number(e.target.value);
                      const nextMax = nextMin > currentMax ? nextMin : currentMax;
                      updateControl(
                        ctrl.column,
                        {
                          column: ctrl.column,
                          control_type: "numeric_range",
                          min: nextMin,
                          max: nextMax,
                        },
                        true
                      );
                    }}
                  />
                  <input
                    type="range"
                    aria-label={`${ctrl.label} Maximum`}
                    min={meta.minNum}
                    max={meta.maxNum}
                    step={step}
                    value={currentMax}
                    onChange={(e) => {
                      const nextMax = Number(e.target.value);
                      const nextMin = nextMax < currentMin ? nextMax : currentMin;
                      updateControl(
                        ctrl.column,
                        {
                          column: ctrl.column,
                          control_type: "numeric_range",
                          min: nextMin,
                          max: nextMax,
                        },
                        true
                      );
                    }}
                  />
                </div>
              </div>
            );
          }

          return (
            <div key={ctrl.column} className="filter-control-box">
              <label htmlFor={inputId} className="filter-label">
                {ctrl.label}
              </label>
              <input
                id={inputId}
                type="search"
                aria-label={ctrl.label}
                className="table-search-input"
                placeholder={`Search ${ctrl.label.toLowerCase()}…`}
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
                      : null,
                    true
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
