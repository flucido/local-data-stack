import { z } from "zod";

export const ValueFormatSchema = z.enum(["currency", "percent", "integer", "decimal", "raw"]);
export type ValueFormat = z.infer<typeof ValueFormatSchema>;

export const FilterControlTypeSchema = z.enum([
  "date_range",
  "multi_select",
  "single_select",
  "numeric_range",
  "search",
]);
export type FilterControlType = z.infer<typeof FilterControlTypeSchema>;

export const TimeSeriesVariantSchema = z.enum(["line", "area", "stacked_bar", "bar"]);
export const CategoryBarVariantSchema = z.enum(["horizontal", "vertical", "grouped", "stacked"]);
export const SortDirectionSchema = z.enum(["asc", "desc"]);

export const KPIMetricSchema = z.object({
  label: z.string().min(1),
  value_column: z.string().min(1),
  value_format: ValueFormatSchema,
  delta_column: z.string().min(1).optional(),
});

export const KPIGridComponentSchema = z.object({
  component: z.literal("KPIGrid"),
  metrics: z.array(KPIMetricSchema).min(1).max(4),
});

export const TimeSeriesChartComponentSchema = z.object({
  component: z.literal("TimeSeriesChart"),
  chart_variant: TimeSeriesVariantSchema,
  x_column: z.string().min(1),
  y_columns: z.array(z.string().min(1)).min(1).max(3),
  series_column: z.string().min(1).optional(),
  value_format: ValueFormatSchema,
});

export const CategoryBarChartComponentSchema = z.object({
  component: z.literal("CategoryBarChart"),
  chart_variant: CategoryBarVariantSchema,
  category_column: z.string().min(1),
  value_columns: z.array(z.string().min(1)).min(1).max(3),
  series_column: z.string().min(1).optional(),
  value_format: ValueFormatSchema,
});

export const BudgetVarianceChartComponentSchema = z.object({
  component: z.literal("BudgetVarianceChart"),
  category_column: z.string().min(1),
  actual_column: z.string().min(1),
  budget_column: z.string().min(1),
  variance_column: z.string().min(1).optional(),
  value_format: ValueFormatSchema,
});

export const DataTableComponentSchema = z.object({
  component: z.literal("DataTable"),
  columns: z.array(z.string().min(1)).min(1),
  default_sort: z
    .object({
      column: z.string().min(1),
      direction: SortDirectionSchema,
    })
    .optional(),
});

export const FilterControlSchema = z.object({
  column: z.string().min(1),
  control_type: FilterControlTypeSchema,
  label: z.string().min(1),
});

export const FilterBarComponentSchema = z.object({
  component: z.literal("FilterBar"),
  controls: z.array(FilterControlSchema).min(1).max(4),
});

export const WorkspaceComponentSchema = z.discriminatedUnion("component", [
  KPIGridComponentSchema,
  TimeSeriesChartComponentSchema,
  CategoryBarChartComponentSchema,
  BudgetVarianceChartComponentSchema,
  DataTableComponentSchema,
  FilterBarComponentSchema,
]);

export type WorkspaceComponent = z.infer<typeof WorkspaceComponentSchema>;
export type KPIGridProps = z.infer<typeof KPIGridComponentSchema>;
export type TimeSeriesChartProps = z.infer<typeof TimeSeriesChartComponentSchema>;
export type CategoryBarChartProps = z.infer<typeof CategoryBarChartComponentSchema>;
export type BudgetVarianceChartProps = z.infer<typeof BudgetVarianceChartComponentSchema>;
export type DataTableProps = z.infer<typeof DataTableComponentSchema>;
export type FilterBarProps = z.infer<typeof FilterBarComponentSchema>;

export const RenderWorkspaceUISchema = z.object({
  tool: z.literal("render_workspace_ui"),
  arguments: z.object({
    title: z.string().min(1),
    narrative_summary: z.string().min(1),
    components: z.array(WorkspaceComponentSchema).min(1).max(4),
  }),
});

export type RenderWorkspaceUICall = z.infer<typeof RenderWorkspaceUISchema>;

export const ExecuteDuckDBQuerySchema = z.object({
  tool: z.literal("execute_duckdb_query"),
  arguments: z.object({
    explanation: z.string().min(1),
    sql: z
      .string()
      .min(1)
      .refine(
        (s) => {
          const trimmed = s.trimStart().toUpperCase();
          return trimmed.startsWith("SELECT") || trimmed.startsWith("WITH");
        },
        { message: "SQL must start with SELECT or WITH." }
      ),
  }),
});

export type ExecuteDuckDBQueryCall = z.infer<typeof ExecuteDuckDBQuerySchema>;

export const ColumnSummarySchema = z.object({
  name: z.string(),
  type: z.string(),
  distinct_count: z.number().int().nonnegative(),
  null_count: z.number().int().nonnegative().optional(),
  min: z.union([z.string(), z.number(), z.null()]).optional(),
  max: z.union([z.string(), z.number(), z.null()]).optional(),
  sample_values: z.array(z.unknown()).optional(),
});

export const DuckDBResultSummarySchema = z.object({
  status: z.literal("ok"),
  query_id: z.string(),
  row_count: z.number().int().nonnegative(),
  columns: z.array(ColumnSummarySchema),
  sample_rows: z.array(z.array(z.unknown())),
});

export type DuckDBResultSummary = z.infer<typeof DuckDBResultSummarySchema>;

export interface FilterMutation {
  column: string;
  control_type: FilterControlType;
  min?: string | number;
  max?: string | number;
  values?: Array<string | number>;
  value?: string | number;
  query?: string;
}

export function validateWorkspaceUISemantics(
  payload: unknown,
  resultSummary?: DuckDBResultSummary
): { valid: boolean; errors: string[] } {
  const parsed = RenderWorkspaceUISchema.safeParse(payload);
  if (!parsed.success) {
    return {
      valid: false,
      errors: parsed.error.issues.map((i) => `${i.path.join(".")}: ${i.message}`),
    };
  }

  const errors: string[] = [];
  const ui = parsed.data;
  const colMap = new Map(
    (resultSummary?.columns ?? []).map((c) => [c.name, c])
  );
  const rowCount = resultSummary?.row_count;

  const checkColExists = (col: string, ctx: string): boolean => {
    if (colMap.size > 0 && !colMap.has(col)) {
      errors.push(
        `${ctx}: referenced column '${col}' does not exist in query output columns [${Array.from(colMap.keys()).join(", ")}].`
      );
      return false;
    }
    return true;
  };

  for (let i = 0; i < ui.arguments.components.length; i++) {
    const comp = ui.arguments.components[i];
    const ctx = `components[${i}] (${comp.component})`;

    if (comp.component === "KPIGrid") {
      if (rowCount !== undefined && rowCount !== 1) {
        errors.push(`${ctx}: KPIGrid requires row_count === 1, got ${rowCount}.`);
      }
      for (const m of comp.metrics) {
        checkColExists(m.value_column, `${ctx}.value_column`);
        if (m.delta_column) {
          checkColExists(m.delta_column, `${ctx}.delta_column`);
        }
      }
    } else if (comp.component === "TimeSeriesChart") {
      if (rowCount !== undefined && rowCount < 2) {
        errors.push(`${ctx}: TimeSeriesChart requires row_count >= 2, got ${rowCount}.`);
      }
      checkColExists(comp.x_column, `${ctx}.x_column`);
      comp.y_columns.forEach((y) => checkColExists(y, `${ctx}.y_columns`));
      if (comp.series_column) {
        checkColExists(comp.series_column, `${ctx}.series_column`);
      }
    } else if (comp.component === "CategoryBarChart") {
      if (rowCount !== undefined && rowCount < 2) {
        errors.push(`${ctx}: CategoryBarChart requires row_count >= 2, got ${rowCount}.`);
      }
      checkColExists(comp.category_column, `${ctx}.category_column`);
      comp.value_columns.forEach((v) => checkColExists(v, `${ctx}.value_columns`));
      if (comp.series_column) {
        checkColExists(comp.series_column, `${ctx}.series_column`);
      }
    } else if (comp.component === "BudgetVarianceChart") {
      checkColExists(comp.category_column, `${ctx}.category_column`);
      checkColExists(comp.actual_column, `${ctx}.actual_column`);
      checkColExists(comp.budget_column, `${ctx}.budget_column`);
      if (comp.variance_column) {
        checkColExists(comp.variance_column, `${ctx}.variance_column`);
      }
    } else if (comp.component === "DataTable") {
      comp.columns.forEach((c) => checkColExists(c, `${ctx}.columns`));
      if (comp.default_sort) {
        checkColExists(comp.default_sort.column, `${ctx}.default_sort.column`);
      }
    } else if (comp.component === "FilterBar") {
      comp.controls.forEach((ctrl) => checkColExists(ctrl.column, `${ctx}.controls.column`));
    }
  }

  return { valid: errors.length === 0, errors };
}
