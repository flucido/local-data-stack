import { ValueFormat } from "../schemas/workspace-ui";

const currencyFormatter = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const integerFormatter = new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 0,
});

const decimalFormatter = new Intl.NumberFormat("en-US", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/**
 * Determine across an entire column of values whether a rate/percent column
 * is expressed as a 0..1 ratio (`max(|col|) <= 1.0`) or an already-scaled
 * 0..100 percentage (`max(|col|) > 1.0`).
 */
export function detectColumnIsRatio(values: unknown[]): boolean {
  let maxAbs = 0;
  let seenNumeric = false;
  for (const v of values) {
    if (v === null || v === undefined || v === "") continue;
    const n = typeof v === "number" ? v : Number(v);
    if (Number.isFinite(n)) {
      seenNumeric = true;
      const abs = Math.abs(n);
      if (abs > maxAbs) maxAbs = abs;
    }
  }
  return seenNumeric && maxAbs <= 1.0;
}

export function formatMetricValue(
  value: unknown,
  format: ValueFormat = "raw",
  isRatioScale?: boolean
): string {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  const num = typeof value === "number" ? value : Number(value);
  if (Number.isNaN(num)) {
    return String(value);
  }
  switch (format) {
    case "currency":
      return currencyFormatter.format(num);
    case "percent": {
      const shouldScale =
        isRatioScale !== undefined ? isRatioScale : Math.abs(num) <= 1.0 && num !== 0;
      const pct = shouldScale ? num * 100 : num;
      return `${decimalFormatter.format(pct)}%`;
    }
    case "integer":
      return integerFormatter.format(Math.round(num));
    case "decimal":
      return decimalFormatter.format(num);
    case "raw":
    default:
      return String(value);
  }
}
