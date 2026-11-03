import React, { useId, useMemo, useState } from "react";
import {
  ColumnDef,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  SortingState,
  useReactTable,
} from "@tanstack/react-table";
import { DataTableProps } from "../../schemas/workspace-ui";

interface ComponentProps {
  spec: DataTableProps;
  rows: Record<string, unknown>[];
}

export const DataTable: React.FC<ComponentProps> = ({ spec, rows }) => {
  const captionId = useId();
  const [searchQuery, setSearchQuery] = useState("");
  const [sorting, setSorting] = useState<SortingState>(() =>
    spec.default_sort
      ? [{ id: spec.default_sort.column, desc: spec.default_sort.direction === "desc" }]
      : []
  );

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
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  // Expose CSS variables --label-1, --label-2, ... for @container (width < 600px) stacked layout
  const tableCssVars = useMemo(() => {
    const vars: Record<string, string> = {};
    spec.columns.forEach((col, i) => {
      vars[`--label-${i + 1}`] = `"${col}"`;
    });
    return vars as React.CSSProperties;
  }, [spec.columns]);

  const exportCsv = () => {
    const header = spec.columns.join(",");
    const lines = filteredRows.map((r) =>
      spec.columns
        .map((c) => `"${String(r[c] ?? "").replace(/"/g, '""')}"`)
        .join(",")
    );
    const csv = [header, ...lines].join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "arrow_export.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <section className="workspace-panel" data-testid="data-table">
      <header className="panel-header">
        <div>
          <h3 className="panel-title">
            Arrow Data Grid ({filteredRows.length.toLocaleString()} rows)
          </h3>
          <span className="panel-subtitle">
            Columns: <code>{spec.columns.join(", ")}</code>
          </span>
        </div>
        <div className="table-toolbar">
          <input
            type="search"
            className="table-search-input"
            placeholder="Filter rows..."
            aria-label="Filter table rows"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          <button type="button" className="btn-secondary" onClick={exportCsv}>
            Export CSV
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
            Analytical result table with columns {spec.columns.join(", ")}
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
                      onClick={header.column.getToggleSortingHandler()}
                      className="sortable-th"
                    >
                      {flexRender(
                        header.column.columnDef.header,
                        header.getContext()
                      )}
                      {sortDir === "asc" ? " ▲" : sortDir === "desc" ? " ▼" : ""}
                    </th>
                  );
                })}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row) => (
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
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
};
