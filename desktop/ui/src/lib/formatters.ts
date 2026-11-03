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

export function formatMetricValue(value: unknown, format: ValueFormat = "raw"): string {
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
      // Handle both 0..1 ratios and 0..100 percentages gracefully
      const pct = Math.abs(num) <= 1.0 && num !== 0 ? num * 100 : num;
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
