import React, { useEffect, useId, useMemo, useState } from "react";
import {
  ColumnDef,
  flexRender,
  getCoreRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  SortingState,
  useReactTable,
} from "@tanstack/react-table";
import { DataTableProps } from "../../schemas/workspace-ui";

interface ComponentProps {
  spec: DataTableProps;
  rows: Record<string, unknown>[];
}

const CORE_ROW_MODEL = getCoreRowModel();
const SORTED_ROW_MODEL = getSortedRowModel();
const PAGINATION_ROW_MODEL = getPaginationRowModel();

function escapeCsvCell(val: unknown): string {
  if (val === null || val === undefined) {
    return '""';
  }
  if (typeof val === "number" || typeof val === "boolean") {
    return `"${String(val)}"`;
  }
  let raw = String(val);
  if (/^[=+\-@]/.test(raw)) {
    raw = `'${raw}`;
  }
  return `"${raw.replace(/"/g, '""')}"`;
}

export function buildCsvContent(
  columns: string[],
  rows: Record<string, unknown>[]
): string {
  const header = columns
    .map((c) => `"${String(c).replace(/"/g, '""')}"`)
    .join(",");
  const lines = rows.map((r) =>
    columns.map((c) => escapeCsvCell(r[c])).join(",")
  );
  return [header, ...lines].join("\n");
}

export const DataTable: React.FC<ComponentProps> = ({ spec, rows }) => {
  const captionId = useId();
  const [searchQuery, setSearchQuery] = useState("");
  const [sorting, setSorting] = useState<SortingState>(() =>
    spec.default_sort
      ? [{ id: spec.default_sort.column, desc: spec.default_sort.direction === "desc" }]
      : []
  );

  useEffect(() => {
    setSearchQuery("");
    setSorting(
      spec.default_sort
        ? [{ id: spec.default_sort.column, desc: spec.default_sort.direction === "desc" }]
        : []
    );
  }, [spec]);

  const filteredRows = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter((row) =>
      spec.columns.some((col) =>
        String(row[col] ?? "")
          .toLowerCase()
          .includes(q)
      )
    );
  }, [rows, spec.columns, searchQuery]);

  const columns = useMemo<ColumnDef<Record<string, unknown>>[]>(
    () =>
      spec.columns.map((colName) => ({
        id: colName,
        accessorFn: (row) => row[colName],
        header: colName,
        cell: (info) => {
          const val = info.getValue();
          if (typeof val === "number") {
            return Number.isInteger(val) ? val.toLocaleString() : val.toFixed(2);
          }
          return String(val ?? "—");
        },
      })),
    [spec.columns]
  );

  const table = useReactTable({
    data: filteredRows,
    columns,
    initialState: {
      pagination: { pageSize: 100 },
    },
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: CORE_ROW_MODEL,
    getSortedRowModel: SORTED_ROW_MODEL,
    getPaginationRowModel: PAGINATION_ROW_MODEL,
  });

  const tableCssVars = useMemo(() => {
    const vars: Record<string, string> = {};
    spec.columns.forEach((col, i) => {
      vars[`--label-${i + 1}`] = `"${col}"`;
    });
    return vars as React.CSSProperties;
  }, [spec.columns]);

  const exportCsv = () => {
    const csv = buildCsvContent(spec.columns, filteredRows);
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "school_data_export.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  const visibleRows = table.getRowModel().rows;

  return (
    <section className="workspace-panel" data-testid="data-table">
      <header className="panel-header">
        <div>
          <h3 className="panel-title">
            Detailed Results ({filteredRows.length.toLocaleString()} rows)
          </h3>
          <span className="panel-subtitle">
            Showing columns: {spec.columns.join(", ")}
          </span>
        </div>
        <div className="table-toolbar">
          <input
            type="search"
            className="table-search-input"
            placeholder="Search rows…"
            aria-label="Filter table rows"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          <button type="button" className="btn-secondary" onClick={exportCsv}>
            Download CSV
          </button>
        </div>
      </header>

      <div
        tabIndex={0}
        role="region"
        aria-labelledby={captionId}
        className="table-wrapper"
      >
        <table style={tableCssVars}>
          <caption id={captionId} className="sr-only">
            Results table with columns {spec.columns.join(", ")}
          </caption>
          <thead>
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => {
                  const sortDir = header.column.getIsSorted();
                  return (
                    <th
                      key={header.id}
                      scope="col"
                      aria-sort={
                        sortDir === "asc"
                          ? "ascending"
                          : sortDir === "desc"
                          ? "descending"
                          : "none"
                      }
                      className="sortable-th"
                    >
                      <button
                        type="button"
                        className="sort-header-btn"
                        onClick={header.column.getToggleSortingHandler()}
                      >
                        <span>
                          {flexRender(
                            header.column.columnDef.header,
                            header.getContext()
                          )}
                        </span>
                        <span aria-hidden="true">
                          {sortDir === "asc" ? " ▲" : sortDir === "desc" ? " ▼" : ""}
                        </span>
                      </button>
                    </th>
                  );
                })}
              </tr>
            ))}
          </thead>
          <tbody>
            {visibleRows.length === 0 ? (
              <tr>
                <td colSpan={spec.columns.length} className="empty-table-cell">
                  <span>No matching records found.</span>{" "}
                  {searchQuery.trim() !== "" && (
                    <button
                      type="button"
                      className="btn-secondary"
                      onClick={() => setSearchQuery("")}
                    >
                      Clear search
                    </button>
                  )}
                </td>
              </tr>
            ) : (
              visibleRows.map((row) => (
                <tr key={row.id}>
                  {row.getVisibleCells().map((cell, cellIdx) => {
                    const colId = cell.column.id;
                    const rendered = flexRender(
                      cell.column.columnDef.cell,
                      cell.getContext()
                    );
                    if (cellIdx === 0) {
                      return (
                        <th key={cell.id} scope="row">
                          {rendered}
                        </th>
                      );
                    }
                    return (
                      <td key={cell.id} data-label={colId}>
                        {rendered}
                      </td>
                    );
                  })}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
};
