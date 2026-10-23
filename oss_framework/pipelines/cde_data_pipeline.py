#!/usr/bin/env python3
"""
CDE Data Pipeline - California Department of Education Data Ingestion

This pipeline loads CDE downloadable data files (all 24 catalog domains) into
DuckDB / filesystem for downstream dbt transformations.

Features:
- Glob-based file discovery (no hardcoded filenames) across all CDE domains
- Three file types: tab-delimited .txt, multi-sheet .xlsx, caret-delimited .zip (SBAC)
- BOM stripping (\ufeff) on first column header
- Schema-drift tolerant: union by column name across years, missing cols -> None
- Suppression handling: ``*`` and empty strings -> None
- Per-domain dlt resources + selective --domain CLI loading
- Row-count logging per file
- Backward-compatible ``load_chronic_absenteeism`` entry point

See ``data/cde_raw/DATA_CATALOG.md`` for the full domain catalogue and quirks.
"""

import io
import logging
import os
import zipfile
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

import dlt
import polars as pl
from dlt.common.pipeline import LoadInfo
from dlt.sources import DltResource

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Domain catalogue
# ---------------------------------------------------------------------------
# Each entry maps a domain key to its discovery + parsing configuration.
#   glob   : glob pattern relative to data_dir (all files are flat in data/raw/)
#   type   : "txt" (tab-delimited), "xlsx" (Excel), or "zip" (caret-delimited)
#   sheet  : substring matched against xlsx sheet names to find the data sheet
#            (None -> last sheet)
#   delim  : field delimiter for txt/zip ("\\t" default)
#   desc   : human-readable description
DOMAIN_CONFIG: dict[str, dict[str, Any]] = {
    "chronic_absenteeism": {
        "glob": "chronicabsenteeism*.txt",
        "type": "txt",
        "desc": "Chronic absenteeism rates (Style A)",
    },
    "absenteeism_reason": {
        "glob": "absenteeismreason*.txt",
        "type": "txt",
        "desc": "Absenteeism by reason (Style A)",
    },
    "cumulative_enrollment": {
        "glob": "cenroll*.txt",
        "type": "txt",
        "desc": "Cumulative enrollment (Style A, joined column names)",
    },
    "census_enrollment_rates": {
        "glob": "censusenrollratesdownload*.txt",
        "type": "txt",
        "desc": "Census enrollment rates (Style B)",
    },
    "chronic_absenteeism_dashboard": {
        "glob": "chronicdownload*.txt",
        "type": "txt",
        "desc": "Chronic absenteeism dashboard accountability (Style B)",
    },
    "suspension": {
        "glob": "suspension*.txt",
        "type": "txt",
        "desc": "Suspension counts/rates (Style A)",
    },
    "suspension_dashboard": {
        "glob": "suspdownload*.txt",
        "type": "txt",
        "desc": "Suspension dashboard accountability (Style B)",
    },
    "expulsion": {
        "glob": "expulsion*.txt",
        "type": "txt",
        "desc": "Expulsion counts/rates (Style A)",
    },
    "ela_dashboard": {
        "glob": "eladownload*.txt",
        "type": "txt",
        "desc": "ELA assessment dashboard (Style B)",
    },
    "elpac_dashboard": {
        "glob": "elpidownload*.txt",
        "type": "txt",
        "desc": "ELPAC English-learner proficiency dashboard (Style B)",
    },
    "sbac_caaspp": {
        "glob": "sb_ca*_all_csv_v1.zip",
        "type": "zip",
        "delim": "^",
        "desc": "SBAC/CAASPP assessment (caret-delimited inside zip)",
    },
    "homeless_enrollment": {
        "glob": "hse*.txt",
        "type": "txt",
        "desc": "Homeless student enrollment (Style A)",
    },
    "frpm": {
        "glob": "frpm*.xlsx",
        "type": "xlsx",
        "sheet": "School-Level",
        "desc": "Free/Reduced Price Meals (Excel, header at R2)",
    },
    "upc": {
        "glob": "cupc*.xlsx",
        "type": "xlsx",
        "sheet": "School-Level",
        "desc": "Unduplicated Pupil Count (Excel, header at R2)",
    },
    "restraint_seclusion": {
        "glob": "rsddata*.xlsx",
        "type": "xlsx",
        "sheet": None,
        "desc": "Restraint & seclusion (Excel, header at R2/R3)",
    },
    "school_directory": {
        "glob": "schldir.txt",
        "type": "txt",
        "desc": "School directory (Style C, PII)",
    },
    "cbedsora": {
        "glob": "cbedsora*.txt",
        "type": "txt",
        "desc": "CBEDS staff demographics, 'a'/'b' file pairs (Style C)",
    },
    "enrollment_by_grade": {
        "glob": "enrbygrade*.txt",
        "type": "txt",
        "desc": "Enrollment by grade (Style C)",
    },
    "enrollment_by_subgroup": {
        "glob": "enrbysubgrp*.txt",
        "type": "txt",
        "desc": "Enrollment by demographic subgroup (Style C)",
    },
    "class_assignment": {
        "glob": "classassign*.txt",
        "type": "txt",
        "desc": "Class assignment (Style C)",
    },
    "teacher_misassignment": {
        "glob": "teachermisassign*.txt",
        "type": "txt",
        "desc": "Teacher misassignment (Style C)",
    },
    "teacher_out_of_field": {
        "glob": "teacheroutoffield*.txt",
        "type": "txt",
        "desc": "Teacher out-of-field (Style C)",
    },
    "teacher_prep": {
        "glob": "teacherprep*.txt",
        "type": "txt",
        "desc": "Teacher preparation (Style C, 113 cols)",
    },
}

# Ordered list of domain keys (used for iteration + --domain=help)
ALL_DOMAINS: list[str] = list(DOMAIN_CONFIG.keys())


def _strip_bom(name: str) -> str:
    """Strip a leading UTF-8 BOM from a column name.

    Files are read with ``encoding='latin1'``, so the UTF-8 BOM bytes
    (``EF BB BF``) decode to the literal string ``ï»¿`` rather than the
    ``\\ufeff`` codepoint. Strip both forms so the union loader treats
    the first column consistently across files regardless of which year
    introduced a BOM.
    """
    if not name:
        return name
    for prefix in ("\ufeff", "ï»¿"):
        if name.startswith(prefix):
            return name[len(prefix) :]
    return name


def _clean_value(value: Any) -> Any:
    """Normalise a raw cell value: ``*`` and empty strings -> None."""
    if value is None:
        return None
    if isinstance(value, str):
        v = value.replace("\r", "").strip()
        if v == "" or v == "*":
            return None
        return v
    return value


def _clean_frame(lf: pl.LazyFrame) -> pl.LazyFrame:
    """Vectorised equivalent of ``_clean_value`` across every Utf8 column.

    Strips whitespace/``\\r`` and maps suppression markers (``*``) and empty
    strings to null.
    """
    schema = lf.collect_schema()
    exprs = [
        pl.col(name).str.strip_chars().replace("", None).replace("*", None).alias(name)
        for name, dtype in schema.items()
        if dtype == pl.Utf8
    ]
    return lf.with_columns(exprs) if exprs else lf


def _strip_bom_columns(lf: pl.LazyFrame) -> pl.LazyFrame:
    """Rename columns whose names carry a leading UTF-8 BOM."""
    renames = {
        name: _strip_bom(name) for name in lf.collect_schema().names() if _strip_bom(name) != name
    }
    return lf.rename(renames) if renames else lf


# ---------------------------------------------------------------------------
# Core loader
# ---------------------------------------------------------------------------
class CDEDataLoader:
    """Loader for California Department of Education data files."""

    def __init__(self, data_dir: str = ""):
        # Default to repo-relative "data/raw/" per the data catalogue.
        self.data_dir = data_dir or os.getenv("CDE_DATA_PATH", "data/raw")

    # -- generic file readers ---------------------------------------------

    def _read_tsv_frame(self, file_path: str, delimiter: str = "\t") -> pl.LazyFrame | None:
        """Scan a delimited text file into a Polars LazyFrame.

        All columns are pinned to Utf8 (CDE files ship string-typed counts and
        codes with leading zeros). Handles BOM on the first header name and
        suppression markers (``*`` / empty -> None) vectorised.
        """
        try:
            lf = pl.scan_csv(
                file_path,
                separator=delimiter,
                encoding="utf8-lossy",
                infer_schema_length=0,
                truncate_ragged_lines=True,
            )
        except FileNotFoundError:
            logger.warning("File not found: %s", file_path)
            return None
        except Exception as e:  # noqa: BLE001 - surface, don't crash the batch
            logger.error("Error reading %s: %s", file_path, e)
            return None
        return _clean_frame(_strip_bom_columns(lf))

    def _read_tsv_file(self, file_path: str, delimiter: str = "\t") -> Iterator[dict[str, Any]]:
        """Read a delimited text file and yield rows as dictionaries."""
        lf = self._read_tsv_frame(file_path, delimiter=delimiter)
        if lf is None:
            return
        df = lf.collect()
        yield from df.iter_rows(named=True)

    def _read_xlsx_file(
        self, file_path: str, sheet_substr: str | None = None
    ) -> Iterator[dict[str, Any]]:
        """Read an Excel data file, yielding rows as dictionaries.

        CDE Excel files put title/metadata rows above the real header on the
        data sheet. We locate the data sheet (by substring or last sheet) and
        auto-detect the header row (first row with >=3 populated cells),
        then emit the data rows that follow.
        """
        try:
            import openpyxl  # local import; heavy dependency
        except ImportError:  # pragma: no cover
            logger.error("openpyxl is required to read .xlsx CDE files")
            return

        try:
            wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        except Exception as e:  # noqa: BLE001
            logger.error("Error opening %s: %s", file_path, e)
            return

        # Resolve the data sheet.
        ws = None
        if sheet_substr:
            for name in wb.sheetnames:
                if sheet_substr.lower() in name.lower():
                    ws = wb[name]
                    break
        if ws is None:
            ws = wb[wb.sheetnames[-1]]  # fall back to last sheet

        rows_iter = ws.iter_rows(values_only=True)

        # Auto-detect header row: first row (within the first ~5) that has >=3
        # non-None cells. This skips title blocks (1 cell) and the suppression
        # note row in rsddata2425.
        header: list[str] = []
        header_found = False
        for _ in range(5):
            try:
                row = next(rows_iter)
            except StopIteration:
                break
            populated = [c for c in row if c is not None]
            if not header_found and len(populated) >= 3:
                header = [
                    _strip_bom(str(c)) if c is not None else f"col_{i}" for i, c in enumerate(row)
                ]
                header_found = True
                break
        if not header_found:
            logger.warning("No header row detected in %s", file_path)
            wb.close()
            return

        for row in rows_iter:
            if row is None or all(c is None for c in row):
                continue
            yield {header[i]: _clean_value(row[i]) for i in range(min(len(header), len(row)))}
        wb.close()

    def _read_zip_frame(self, file_path: str, delimiter: str = "^") -> pl.LazyFrame | None:
        """Read a caret-delimited data file inside a .zip (SBAC/CAASPP).

        Picks the full ``all_csv_v1.txt`` member when present, otherwise the
        first ``.txt`` member. Handles BOM + suppression markers vectorised.
        """
        try:
            with zipfile.ZipFile(file_path) as zf:
                members = [m for m in zf.namelist() if m.lower().endswith(".txt")]
                if not members:
                    logger.warning("No .txt member inside %s", file_path)
                    return None
                target = next((m for m in members if "all_csv_v1" in m.lower()), members[0])
                raw = zf.read(target)
            df = pl.read_csv(
                io.BytesIO(raw),
                separator=delimiter,
                encoding="utf8-lossy",
                infer_schema_length=0,
                truncate_ragged_lines=True,
            )
        except FileNotFoundError:
            logger.warning("File not found: %s", file_path)
            return None
        except Exception as e:  # noqa: BLE001
            logger.error("Error reading zip %s: %s", file_path, e)
            return None
        return _clean_frame(_strip_bom_columns(df.lazy()))

    def _read_zip_file(self, file_path: str, delimiter: str = "^") -> Iterator[dict[str, Any]]:
        """Read a caret-delimited file inside a .zip and yield row dicts."""
        lf = self._read_zip_frame(file_path, delimiter=delimiter)
        if lf is None:
            return
        df = lf.collect()
        yield from df.iter_rows(named=True)

    # -- file discovery ---------------------------------------------------

    def _discover_files(self, pattern: str) -> list[Path]:
        """Return sorted list of files matching ``pattern`` under data_dir."""
        base = Path(self.data_dir)
        if not base.exists():
            logger.warning("Data directory does not exist: %s", base)
            return []
        files = sorted(base.glob(pattern))
        # Exclude obvious non-data duplicates (e.g. 'schldir (1).txt').
        files = [f for f in files if "(" not in f.name]
        return files

    def _reader_for(self, file_path: Path, cfg: dict[str, Any]) -> Iterator[dict[str, Any]]:
        """Dispatch to the right reader based on file type."""
        ftype = cfg.get("type", "txt")
        if ftype == "txt":
            return self._read_tsv_file(str(file_path), delimiter=cfg.get("delim", "\t"))
        if ftype == "xlsx":
            return self._read_xlsx_file(str(file_path), sheet_substr=cfg.get("sheet"))
        if ftype == "zip":
            return self._read_zip_file(str(file_path), delimiter=cfg.get("delim", "^"))
        raise ValueError(f"Unknown file type '{ftype}' for {file_path}")

    def _frame_for(self, file_path: Path, cfg: dict[str, Any]) -> pl.LazyFrame | None:
        """Dispatch to the right Polars frame reader based on file type.

        ``xlsx`` files keep the openpyxl reader (title rows above the header
        need row-wise detection) and are lifted into a lazy frame afterwards.
        """
        ftype = cfg.get("type", "txt")
        if ftype == "txt":
            return self._read_tsv_frame(str(file_path), delimiter=cfg.get("delim", "\t"))
        if ftype == "zip":
            return self._read_zip_frame(str(file_path), delimiter=cfg.get("delim", "^"))
        if ftype == "xlsx":
            rows = list(self._read_xlsx_file(str(file_path), sheet_substr=cfg.get("sheet")))
            if not rows:
                return None
            return pl.from_dicts(rows, infer_schema_length=10_000).lazy()
        raise ValueError(f"Unknown file type '{ftype}' for {file_path}")

    # -- schema-drift-tolerant union loader -------------------------------

    def _load_domain(self, domain_key: str) -> Iterator[dict[str, Any]]:
        """Load all files for a domain, unioning columns across years.

        Uses Polars ``concat(how="diagonal_relaxed")`` for schema-drift
        tolerance: columns are unioned by name across yearly files and
        columns missing from a given year are filled with null — no manual
        header-scan pass required.
        """
        cfg = DOMAIN_CONFIG[domain_key]
        files = self._discover_files(cfg["glob"])
        if not files:
            logger.info("No files matched %s for domain '%s'", cfg["glob"], domain_key)
            return

        frames: list[pl.LazyFrame] = []
        for file_path in files:
            lf = self._frame_for(file_path, cfg)
            if lf is None:
                continue
            lf = lf.with_columns(
                pl.lit(datetime.now().isoformat()).alias("_loaded_at"),
                pl.lit(file_path.name).alias("_source_file"),
                pl.lit(domain_key).alias("_domain"),
            )
            frames.append(lf)

        if not frames:
            logger.warning("No readable files for domain '%s'", domain_key)
            return

        unioned = pl.concat(frames, how="diagonal_relaxed")
        logger.info(
            "Domain '%s': %d files, %d union columns",
            domain_key,
            len(frames),
            len(unioned.collect_schema().names()),
        )

        df = unioned.collect()
        logger.info("  loaded %s rows from %d files", f"{df.height:,}", len(frames))
        yield from df.iter_rows(named=True)

    # -- per-domain public loaders ---------------------------------------

    def load_chronic_absenteeism(
        self, academic_year: str | None = None
    ) -> Iterator[dict[str, Any]]:
        """Load chronic absenteeism data (backward compatible).

        Args:
            academic_year: 2-digit year suffix (e.g. "24" for 2023-24), or
                None to load all available years.
        Yields:
            Chronic absenteeism records with ``_loaded_at``/``_source_file``.
        """
        if academic_year:
            pattern = f"chronicabsenteeism{academic_year}*.txt"
        else:
            pattern = "chronicabsenteeism*.txt"

        files = self._discover_files(pattern)
        for file_path in files:
            logger.info("Loading %s ...", file_path.name)
            row_count = 0
            for row in self._read_tsv_file(str(file_path)):
                row["_loaded_at"] = datetime.now().isoformat()
                row["_source_file"] = file_path.name
                yield row
                row_count += 1
            logger.info("  loaded %s rows from %s", f"{row_count:,}", file_path.name)

    # Generic per-domain loaders (one method per catalogue domain).
    def load_absenteeism_reason(self) -> Iterator[dict[str, Any]]:
        yield from self._load_domain("absenteeism_reason")

    def load_cumulative_enrollment(self) -> Iterator[dict[str, Any]]:
        yield from self._load_domain("cumulative_enrollment")

    def load_census_enrollment_rates(self) -> Iterator[dict[str, Any]]:
        yield from self._load_domain("census_enrollment_rates")

    def load_chronic_absenteeism_dashboard(self) -> Iterator[dict[str, Any]]:
        yield from self._load_domain("chronic_absenteeism_dashboard")

    def load_suspension(self) -> Iterator[dict[str, Any]]:
        yield from self._load_domain("suspension")

    def load_suspension_dashboard(self) -> Iterator[dict[str, Any]]:
        yield from self._load_domain("suspension_dashboard")

    def load_expulsion(self) -> Iterator[dict[str, Any]]:
        yield from self._load_domain("expulsion")

    def load_ela_dashboard(self) -> Iterator[dict[str, Any]]:
        yield from self._load_domain("ela_dashboard")

    def load_elpac_dashboard(self) -> Iterator[dict[str, Any]]:
        yield from self._load_domain("elpac_dashboard")

    def load_sbac_caaspp(self) -> Iterator[dict[str, Any]]:
        yield from self._load_domain("sbac_caaspp")

    def load_homeless_enrollment(self) -> Iterator[dict[str, Any]]:
        yield from self._load_domain("homeless_enrollment")

    def load_frpm(self) -> Iterator[dict[str, Any]]:
        yield from self._load_domain("frpm")

    def load_upc(self) -> Iterator[dict[str, Any]]:
        yield from self._load_domain("upc")

    def load_restraint_seclusion(self) -> Iterator[dict[str, Any]]:
        yield from self._load_domain("restraint_seclusion")

    def load_school_directory(self) -> Iterator[dict[str, Any]]:
        yield from self._load_domain("school_directory")

    def load_cbedsora(self) -> Iterator[dict[str, Any]]:
        yield from self._load_domain("cbedsora")

    def load_enrollment_by_grade(self) -> Iterator[dict[str, Any]]:
        yield from self._load_domain("enrollment_by_grade")

    def load_enrollment_by_subgroup(self) -> Iterator[dict[str, Any]]:
        yield from self._load_domain("enrollment_by_subgroup")

    def load_class_assignment(self) -> Iterator[dict[str, Any]]:
        yield from self._load_domain("class_assignment")

    def load_teacher_misassignment(self) -> Iterator[dict[str, Any]]:
        yield from self._load_domain("teacher_misassignment")

    def load_teacher_out_of_field(self) -> Iterator[dict[str, Any]]:
        yield from self._load_domain("teacher_out_of_field")

    def load_teacher_prep(self) -> Iterator[dict[str, Any]]:
        yield from self._load_domain("teacher_prep")


# ---------------------------------------------------------------------------
# dlt source: one resource per domain
# ---------------------------------------------------------------------------
# Map domain key -> loader method name on CDEDataLoader.
_DOMAIN_METHODS: dict[str, str] = {
    "chronic_absenteeism": "load_chronic_absenteeism",
    "absenteeism_reason": "load_absenteeism_reason",
    "cumulative_enrollment": "load_cumulative_enrollment",
    "census_enrollment_rates": "load_census_enrollment_rates",
    "chronic_absenteeism_dashboard": "load_chronic_absenteeism_dashboard",
    "suspension": "load_suspension",
    "suspension_dashboard": "load_suspension_dashboard",
    "expulsion": "load_expulsion",
    "ela_dashboard": "load_ela_dashboard",
    "elpac_dashboard": "load_elpac_dashboard",
    "sbac_caaspp": "load_sbac_caaspp",
    "homeless_enrollment": "load_homeless_enrollment",
    "frpm": "load_frpm",
    "upc": "load_upc",
    "restraint_seclusion": "load_restraint_seclusion",
    "school_directory": "load_school_directory",
    "cbedsora": "load_cbedsora",
    "enrollment_by_grade": "load_enrollment_by_grade",
    "enrollment_by_subgroup": "load_enrollment_by_subgroup",
    "class_assignment": "load_class_assignment",
    "teacher_misassignment": "load_teacher_misassignment",
    "teacher_out_of_field": "load_teacher_out_of_field",
    "teacher_prep": "load_teacher_prep",
}

# dlt table name per domain (cde_<domain>).
_DOMAIN_TABLES: dict[str, str] = {key: f"cde_{key}" for key in DOMAIN_CONFIG}


@dlt.source(name="cde")
def cde_source(
    data_dir: str | None = None,
    academic_year: str | None = None,
    domains: list[str] | None = None,
) -> list[DltResource]:
    """dlt source for California Department of Education data.

    Args:
        data_dir: Path to the CDE raw data directory (default ``data/raw``).
        academic_year: 2-digit year suffix for chronic absenteeism (kept for
            backward compatibility); None loads all years.
        domains: Optional list of domain keys to load. None loads all domains.
    """
    loader = CDEDataLoader(data_dir=data_dir or "")
    selected = domains or ALL_DOMAINS

    resources: list[DltResource] = []

    def _make_resource(method, table_name, academic_year_filter):
        """Build a dlt resource wrapping a loader method (closure factory)."""

        if academic_year_filter is not None:

            @dlt.resource(name=table_name, write_disposition="replace")
            def _r() -> Iterator[dict[str, Any]]:
                yield from method(academic_year=academic_year_filter)

        else:

            @dlt.resource(name=table_name, write_disposition="replace")
            def _r() -> Iterator[dict[str, Any]]:
                yield from method()

        return _r

    for domain_key in selected:
        if domain_key not in DOMAIN_CONFIG:
            logger.warning("Unknown domain '%s' - skipping", domain_key)
            continue

        table_name = _DOMAIN_TABLES[domain_key]
        method_name = _DOMAIN_METHODS[domain_key]
        method = getattr(loader, method_name)
        # Only chronic_absenteeism supports the academic_year filter.
        ay_filter = academic_year if domain_key == "chronic_absenteeism" else None
        resources.append(_make_resource(method, table_name, ay_filter))

    return resources


# ---------------------------------------------------------------------------
# Pipeline runner
# ---------------------------------------------------------------------------
def run_cde_pipeline(
    destination_type: str = "duckdb",
    dataset_name: str = "cde_raw",
    data_dir: str | None = None,
    academic_year: str | None = None,
    domains: list[str] | None = None,
) -> LoadInfo:
    """Run the CDE dlt pipeline.

    Args:
        destination_type: ``duckdb`` (default) or ``filesystem``.
        dataset_name: Name for the dataset.
        data_dir: Path to CDE raw data directory.
        academic_year: 2-digit year suffix for chronic absenteeism.
        domains: Optional list of domain keys to load (None = all).
    Returns:
        LoadInfo object with pipeline execution details.
    """
    if academic_year:
        logger.info("Loading CDE chronic absenteeism for year 20%s", academic_year)
    if domains:
        logger.info("Loading CDE domains: %s", ", ".join(domains))
    else:
        logger.info("Loading ALL available CDE domains (multi-year)")

    if destination_type == "duckdb":
        db_path = os.getenv("DUCKDB_DATABASE_PATH", "data/analytics.duckdb")
        db_path = os.path.abspath(db_path)
        pipeline = dlt.pipeline(
            pipeline_name="cde_to_duckdb",
            destination=dlt.destinations.duckdb(db_path),
            dataset_name=dataset_name,
        )
    else:
        stage1_path = os.getenv("STAGE1_PATH", "./oss_framework/data/stage1")
        pipeline = dlt.pipeline(
            pipeline_name="cde_to_stage1",
            destination=dlt.destinations.filesystem(bucket_url=f"{stage1_path}/transactional/cde"),
            dataset_name=dataset_name,
        )

    source = cde_source(data_dir=data_dir, academic_year=academic_year, domains=domains)
    info = pipeline.run(source)

    logger.info("Pipeline completed successfully")
    logger.info("  Pipeline: %s", info.pipeline.pipeline_name)
    logger.info("  Destination: %s", destination_type)
    logger.info("  Dataset: %s", dataset_name)
    logger.info("  Loads: %s", len(info.loads_ids))
    return info


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _parse_cli_args(argv: list[str]) -> dict[str, Any]:
    """Parse simple ``--key=value`` style CLI arguments."""
    opts: dict[str, Any] = {
        "destination": "duckdb",
        "academic_year": None,
        "data_dir": None,
        "domains": None,
    }
    for arg in argv:
        if arg.startswith("--year="):
            opts["academic_year"] = arg.split("=", 1)[1]
        elif arg.startswith("--data-dir="):
            opts["data_dir"] = arg.split("=", 1)[1]
        elif arg.startswith("--domain="):
            value = arg.split("=", 1)[1]
            if value == "all" or value == "":
                opts["domains"] = None
            else:
                opts["domains"] = [d.strip() for d in value.split(",") if d.strip()]
        elif arg == "--filesystem":
            opts["destination"] = "filesystem"
        elif arg in ("--help", "-h"):
            opts["help"] = True
    return opts


if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    args = _parse_cli_args(sys.argv[1:])

    if args.get("help"):
        print("CDE Data Pipeline")
        print("Usage: python cde_data_pipeline.py [options]")
        print("Options:")
        print("  --year=YY       Chronic absenteeism 2-digit year (e.g. 24)")
        print("  --data-dir=DIR  Path to CDE raw data (default: data/raw)")
        print("  --domain=LIST   Comma-separated domain keys (default: all)")
        print("  --filesystem    Write to filesystem (Parquet) instead of DuckDB")
        print("  --help          Show this help")
        print(f"\nAvailable domains ({len(ALL_DOMAINS)}):")
        for key in ALL_DOMAINS:
            print(f"  {key:32s} {DOMAIN_CONFIG[key]['desc']}")
        sys.exit(0)

    # Validate requested domains early.
    if args["domains"]:
        invalid = [d for d in args["domains"] if d not in DOMAIN_CONFIG]
        if invalid:
            print(f"❌ Unknown domain(s): {', '.join(invalid)}")
            print(f"Available: {', '.join(ALL_DOMAINS)}")
            sys.exit(1)

    run_cde_pipeline(
        destination_type=args["destination"],
        data_dir=args["data_dir"],
        academic_year=args["academic_year"],
        domains=args["domains"],
    )
