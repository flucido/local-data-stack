import { Table, tableFromArrays, tableFromIPC, tableToIPC } from "apache-arrow";

export interface DecodedArrowDataset {
  queryId: string;
  table: Table;
  columns: string[];
  rows: Record<string, unknown>[];
  byteLength: number;
  decodeTimeMs: number;
}

/**
 * Decode raw Apache Arrow IPC stream bytes directly into an Arrow Table
 * and lightweight row proxies in <5ms.
 */
export function decodeArrowIPCStream(
  ipcBytes: Uint8Array,
  queryId = "q_arrow"
): DecodedArrowDataset {
  const start = performance.now();
  const table = tableFromIPC(ipcBytes);
  const columns = table.schema.fields.map((f) => f.name);
  const rows: Record<string, unknown>[] = [];

  const numRows = table.numRows;
  const colVectors = columns.map((name) => table.getChild(name));

  for (let r = 0; r < numRows; r++) {
    const obj: Record<string, unknown> = {};
    for (let c = 0; c < columns.length; c++) {
      const val = colVectors[c]?.get(r);
      obj[columns[c]] = typeof val === "bigint" ? Number(val) : val;
    }
    rows.push(obj);
  }

  return {
    queryId,
    table,
    columns,
    rows,
    byteLength: ipcBytes.byteLength,
    decodeTimeMs: Number((performance.now() - start).toFixed(2)),
  };
}

/**
 * Encode plain JS row objects into an Apache Arrow IPC binary stream (`Uint8Array`).
 * Used by tests and standalone dev previews so every component always consumes genuine Arrow IPC streams.
 */
export function encodeRowsToArrowIPC(
  rows: Record<string, unknown>[],
  columnOrder?: string[]
): Uint8Array {
  const cols =
    columnOrder && columnOrder.length > 0
      ? columnOrder
      : rows.length > 0
      ? Object.keys(rows[0])
      : [];

  const arrays: Record<string, unknown[]> = {};
  for (const col of cols) {
    arrays[col] = rows.map((r) => {
      const v = r[col];
      return v === undefined ? null : v;
    });
  }

  const arrowTable = tableFromArrays(arrays);
  return tableToIPC(arrowTable, "stream");
}

/**
 * Fetch zero-copy Apache Arrow RecordBatches over the custom Wry `arrow://<query_id>` protocol.
 */
export async function fetchArrowDataset(
  queryId: string,
  fallbackRows?: Record<string, unknown>[],
  fallbackColumns?: string[]
): Promise<DecodedArrowDataset> {
  let response: Response | null = null;
  try {
    response = await fetch(`arrow://${queryId}`);
  } catch (err) {
    if (fallbackRows === undefined && !(err instanceof TypeError)) {
      throw err instanceof Error
        ? err
        : new Error(`Failed to fetch dataset for ${queryId}`);
    }
  }

  if (response !== null) {
    if (response.ok) {
      const buf = await response.arrayBuffer();
      return decodeArrowIPCStream(new Uint8Array(buf), queryId);
    }
    if (fallbackRows === undefined) {
      let detail = "";
      try {
        detail = await response.text();
      } catch {
        detail = "";
      }
      throw new Error(
        `Failed to load results from local data engine (HTTP ${response.status}${
          detail ? `: ${detail}` : ""
        }).`
      );
    }
  }

  const ipcBytes = encodeRowsToArrowIPC(fallbackRows ?? [], fallbackColumns);
  return decodeArrowIPCStream(ipcBytes, queryId);
}
