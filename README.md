# local-data-stack

`local-data-stack` is an open-source, local-first analytics framework for education data. It combines Python orchestration, DuckDB, Delta/Parquet staging, dbt transformations, and Rill dashboards so contributors can explore the architecture without depending on cloud services or private student records.

## Public release guarantees

- The intended `public-release` state is a clean-slate public snapshot with no private student records, local databases, or real credentials committed.
- `oss_framework/data/` contains only empty placeholders plus a 5-row synthetic Parquet sample for schema exploration.
- dbt and Rill resolve DuckDB paths from environment variables instead of hardcoded workstation paths.
- The repository excludes local Parquet, DuckDB, and `.env` files by default.

## Repository layout

```text
local-data-stack/
├── .env.example                  # Safe configuration template
├── oss_framework/
│   ├── data/
│   │   ├── sample_data/          # Synthetic 5-row Parquet sample
│   │   ├── stage1/.gitkeep
│   │   ├── stage2/.gitkeep
│   │   └── stage3/.gitkeep
│   ├── dbt/                      # DuckDB dbt project
│   ├── pipelines/                # Ingestion pipeline definitions
│   ├── scripts/                  # Orchestration helpers
│   └── tests/                    # Python tests
├── rill_project/                 # Rill dashboards and connector config
├── scripts/                      # Root orchestration entrypoints
└── src/                          # Supporting Python modules
```

## Architecture overview

```text
Aeries API / CSV exports
         ↓
Stage 1: Delta/Parquet landing zone (oss_framework/data/stage1)
         ↓
Stage 2: DuckDB + dbt transformations (oss_framework/data/analytics.duckdb)
         ↓
Stage 3: Analytics marts / exported dashboard inputs
         ↓
Rill dashboards (rill_project/)
```

The committed sample data is synthetic and anonymized. It is present only to demonstrate expected column names and lightweight local testing patterns.

### Dashboard layer: California School Dashboard alignment

The Rill dashboard layer is aligned with the **California School Dashboard**,
the CDE's integrated accountability and continuous improvement system. Four
state indicators are exposed, each sourced directly from the CDE's
pre-computed Dashboard downloadable data files:

| Indicator | Source file | Grades | Status measure | Goal direction |
|---|---|---|---|---|
| Chronic Absenteeism | `chronicdownloadYYYY.txt` | TK–8 | Chronic absenteeism rate (%) | Lower is better |
| Suspension Rate | `suspdownloadYYYY.txt` | TK–12 | Suspension rate (%) | Lower is better |
| Academic — ELA | `eladownloadYYYY.txt` | 3–8, 11 | Avg Distance from Standard | Higher is better |
| English Learner Progress (ELPI) | `elpidownloadYYYY.txt` | 1–12 | ELPI status rate (%) | Higher is better |

Each indicator carries the CDE-pre-computed **Status** (current year),
**Change** (year-over-year difference), and **Performance Color** (Red → Orange
→ Yellow → Green → Blue) straight from the state's 5×5 Status×Change grid.
The CDE has already done the 5×5 placement work — we surface it rather than
re-deriving it.

**Grain**: school × academic_year × student_group × aggregate_level (School
or District). Student groups include race/ethnicity (AA, AI, AS, FI, HI, MR,
PI, WH), program subgroups (EL, LTEL, SED, SWD, HOM, FOS), and All Students.

**Directory structure**:

```text
rill_project/
├── rill.yaml              # Project config (OLAP engine: duckdb)
├── metrics/               # Metrics view YAML (type: metrics_view) — one per indicator
├── dashboards/            # Explore dashboard YAML (type: explore) — one per indicator
├── models/                # SQL model definitions (read parquet)
├── data/                  # Exported parquet files (gitignored)
├── alerts/                # Alert definitions
└── apis/                  # Custom API definitions
```

**Data pipeline**: dbt export views (`oss_framework/dbt/models/exports/rill_cde_*.sql`)
clean and type-cast the CDE Dashboard raw tables, then `scripts/export_to_rill.py`
exports them to parquet for Rill to consume. The Style B student-group codes
(ALL, AA, HI, EL, SWD, etc.) are mapped to human-readable labels via the
`cde_dashboard_groups.sql` dbt macro.

**No timeseries**: academic_year is a plain dimension (not a continuous
timeseries). Dashboards use `comparison_mode: dimension` with
`comparison_dimension: academic_year` to deliver the year-over-year comparison
that's central to the CA Dashboard's Status × Change model.

For the full CDE methodology (5×5 colored tables, cut scores, three-by-five
small-n methodology, n-size gates, automatic Orange assignment rules), see the
[2025 Dashboard Technical Guide](https://www.cde.ca.gov/ta/ac/cm/dashboardguide.asp).

## Quick start

### 1. Install Python dependencies

```bash
pip install -e '.[dev]'
```

### 2. Create your local environment file

```bash
cp .env.example .env
# edit .env with your own Aeries credentials or local source settings
```

### 3. Prepare empty local storage

The repository already includes placeholder directories under `oss_framework/data/`. Your local DuckDB database will be created on demand at the path defined by `DUCKDB_DATABASE_PATH`.

### 4. Run dbt against DuckDB

```bash
cd oss_framework/dbt
dbt deps
DBT_PROFILES_DIR=. dbt parse
DBT_PROFILES_DIR=. dbt build
```

### 5. Launch Rill

```bash
cd rill_project
rill start
```

If you keep the default `.env.example` paths, Rill will open the DuckDB file at `../oss_framework/data/analytics.duckdb`.

## Synthetic sample data

A sample file is included at `oss_framework/data/sample_data/synthetic_student_metrics.parquet`.

It contains 5 anonymized rows with columns commonly used by downstream modeling and dashboard examples:

- `student_id`
- `student_alias`
- `academic_year`
- `school_id`
- `grade_level`
- `race_ethnicity`
- `ell_status`
- `special_education_status`
- `frl_status`
- `attendance_rate`
- `gpa`
- `discipline_incidents`

## Validation commands

```bash
python -m pytest oss_framework/tests/test_public_release_sanitization.py -q --no-cov
python scripts/contracts/contract_tests.py
python -m ruff check oss_framework
python -m black --check oss_framework
```

The full repository suite still has pre-existing issues unrelated to the public-release sanitization work, so the focused release test above is the canonical safeguard added in this change.

## License

- Code: [MIT License](LICENSE)
- Documentation: [CC BY 4.0](LICENSE)
