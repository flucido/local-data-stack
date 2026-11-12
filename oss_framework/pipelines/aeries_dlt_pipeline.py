#!/usr/bin/env python3
"""
SIS dlt Pipeline — Stage 1 Data Ingestion.

This pipeline uses a pluggable SIS connector (configured via the SIS_CONNECTOR
environment variable) to extract student data and load it into Stage 1
(Parquet files) following the medallion architecture.

Features:
- Test mode: Uses synthetic data when real credentials unavailable
- Production mode: Connects to the configured SIS API
- Incremental loading: Tracks state for efficient updates
- Parquet output: Writes to stage1/transactional/
"""

import os
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

import dlt
import duckdb
from dlt.common.pipeline import LoadInfo
from dlt.sources import DltResource

from oss_framework.connectors import get_sis_connector
from oss_framework.connectors.mappings.aeries_to_canonical import STUDENT_STAGE1_ALLOWLIST
from oss_framework.pipelines.dlt_state import pipeline_kwargs


def filter_student_record(record: dict[str, Any]) -> dict[str, Any]:
    """Filter a student record through the canonical Stage 1 allowlist."""
    return {
        k: v
        for k, v in record.items()
        if k in STUDENT_STAGE1_ALLOWLIST
        and not k.startswith(("MailingAddress", "ResidenceAddress"))
        and k not in {"HomePhone", "StudentMobilePhone", "StateStudentID", "OldStudentID"}
    }


RAW_TABLES = (
    "raw_students",
    "raw_attendance",
    "raw_academic_records",
    "raw_discipline",
    "raw_enrollment",
)


def sync_stage1_raw_views_to_duckdb(
    db_path: str | Path,
    dataset_name: str,
    destination_type: str,
    stage1_path: str | Path | None = None,
) -> list[str]:
    """Ensure main.raw_* views exist in DuckDB over Stage 1 dlt tables or Parquet files."""
    db_file = Path(db_path)
    db_file.parent.mkdir(parents=True, exist_ok=True)
    synced: list[str] = []

    con = duckdb.connect(str(db_file))
    try:
        quoted_ds = f'"{dataset_name.replace(chr(34), chr(34) * 2)}"'
        con.execute(f"CREATE SCHEMA IF NOT EXISTS {quoted_ds}")

        for tbl in RAW_TABLES:
            quoted_tbl = f'"{tbl.replace(chr(34), chr(34) * 2)}"'
            if destination_type == "filesystem":
                s1_root = Path(stage1_path or "./oss_framework/data/stage1").resolve()
                table_dir = s1_root / "transactional" / "aeries" / dataset_name / tbl
                parquet_files = sorted(table_dir.rglob("*.parquet")) if table_dir.exists() else []
                if not parquet_files:
                    continue
                escaped_files = ", ".join(
                    "'" + str(p).replace("'", "''") + "'" for p in parquet_files
                )
                con.execute(
                    f"CREATE OR REPLACE TABLE {quoted_ds}.{quoted_tbl} AS "
                    f"SELECT * FROM read_parquet([{escaped_files}], union_by_name=true)"
                )

            existing_base = con.execute(
                """
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_schema = 'main'
                  AND table_name = ?
                  AND table_type = 'BASE TABLE'
                """,
                [tbl],
            ).fetchone()[0]
            if existing_base:
                con.execute(f"DROP TABLE IF EXISTS main.{quoted_tbl}")

            has_source = con.execute(
                """
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_schema = ?
                  AND table_name = ?
                """,
                [dataset_name, tbl],
            ).fetchone()[0]
            if has_source:
                con.execute(
                    f"CREATE OR REPLACE VIEW main.{quoted_tbl} AS "
                    f"SELECT * FROM {quoted_ds}.{quoted_tbl}"
                )
                synced.append(tbl)
    finally:
        con.close()

    return synced


def _drop_derived_raw_views(db_path: str | Path) -> list[str]:
    """Drop the derived main.raw_* views (sync recreates them at end of run).

    DuckDB refuses to drop a base table that has dependent views, so dlt's
    refresh="drop_sources" on the aeries_stage1 landing tables requires the
    main.raw_* views to be dropped first. Views only — legacy main.raw_* base
    tables are handled by sync_stage1_raw_views_to_duckdb itself.
    """
    con = duckdb.connect(str(db_path))
    try:
        views = [
            row[0]
            for row in con.execute(
                """
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'main' AND table_type = 'VIEW'
                  AND starts_with(table_name, 'raw_')
                """
            ).fetchall()
        ]
        for view in views:
            quoted = '"' + view.replace('"', '""') + '"'
            con.execute(f"DROP VIEW main.{quoted}")
        return views
    finally:
        con.close()


# dlt source definition
@dlt.source(name="aeries")
def aeries_source(
    base_url: str | None = None,
    api_key: str | None = None,
    test_mode: bool | None = None,
) -> list[DltResource]:
    """
    dlt source for Aeries SIS data

    Args:
        base_url: Aeries API base URL
        api_key: Aeries API certificate/key
        test_mode: Force test mode (synthetic data)
    """

    if test_mode is None:
        test_mode = not api_key

    client = get_sis_connector(
        name="aeries",
        base_url=base_url or "",
        api_key=api_key or "",
        test_mode=test_mode,
    )

    @dlt.resource(
        name="raw_students",
        write_disposition="merge",
        primary_key=["student_id"],
        columns={"withdrawal_date": {"data_type": "text"}},
    )
    def students() -> Iterator[dict[str, Any]]:
        """Extract student data filtered through Stage 1 PII-minimized allowlist"""
        data = client.get_students()
        for record in data:
            clean = filter_student_record(record)
            clean["created_at"] = datetime.now().isoformat()
            clean["updated_at"] = datetime.now().isoformat()
            yield clean

    @dlt.resource(
        name="raw_attendance",
        write_disposition="merge",
        primary_key=["student_id", "school_id", "attendance_date"],
    )
    def attendance() -> Iterator[dict[str, Any]]:
        """Extract attendance data"""
        data = client.get_attendance()
        for record in data:
            record["created_at"] = datetime.now().isoformat()
            yield record

    @dlt.resource(name="raw_academic_records", write_disposition="merge", primary_key=["record_id"])
    def academic_records() -> Iterator[dict[str, Any]]:
        """Extract grade/academic records"""
        data = client.get_grades()
        for record in data:
            record["created_at"] = datetime.now().isoformat()
            yield record

    @dlt.resource(name="raw_discipline", write_disposition="merge", primary_key=["incident_id"])
    def discipline() -> Iterator[dict[str, Any]]:
        """Extract discipline incidents"""
        data = client.get_discipline()
        for record in data:
            record["created_at"] = datetime.now().isoformat()
            yield record

    @dlt.resource(
        name="raw_enrollment",
        write_disposition="merge",
        primary_key=["enrollment_id"],
        columns={"withdrawal_date": {"data_type": "text"}},
    )
    def enrollment() -> Iterator[dict[str, Any]]:
        """Extract enrollment data"""
        data = client.get_enrollment()
        for record in data:
            record["created_at"] = datetime.now().isoformat()
            yield record

    return [students, attendance, academic_records, discipline, enrollment]


def run_aeries_pipeline(
    destination_type: str = "filesystem",
    dataset_name: str = "aeries_stage1",
    test_mode: bool | None = None,
    table_format: str | None = None,
    refresh: str | None = None,
) -> LoadInfo:
    """
    Run the Aeries dlt pipeline

    Args:
        destination_type: "filesystem" (Parquet) or "duckdb"
        dataset_name: Name for the dataset
        test_mode: Force test mode with synthetic data
        table_format: For the filesystem destination, "iceberg" enables true
            primary-key merge (upsert) loads; default (None) writes immutable
            date-partitioned Parquet with append semantics. Also settable via
            the STAGE1_TABLE_FORMAT env var.
        refresh: Optional dlt refresh mode passed to pipeline.run (e.g.
            "drop_sources" for a deterministic full reload). Orchestrated full
            rebuilds should use destination_type="duckdb" + refresh: on the
            plain filesystem destination dlt degrades merge to append and the
            landing directory accumulates one file-set per load, which the
            sync step materializes wholesale — every rebuild would multiply
            the warehouse by the number of historical loads.
    """

    api_key = os.getenv("AERIES_API_KEY")
    base_url = os.getenv("AERIES_API_URL")

    if test_mode is None:
        test_mode = not api_key

    if test_mode:
        print("🧪 Running in TEST MODE with synthetic data")
    else:
        print("🔌 Running in PRODUCTION MODE with real Aeries API")

    # NOTE on write_disposition="merge": dlt only performs true merge loads on
    # database destinations (duckdb) or open table formats. On the filesystem
    # destination, pass table_format="iceberg" (or STAGE1_TABLE_FORMAT=iceberg)
    # for primary-key upserts; the default plain-Parquet mode falls back to
    # append (dlt logs a warning), keeping one immutable file per load.
    # Beware: dlt 1.22 executes Iceberg upserts in <=1000-row batches
    # (one commit per batch), so large tables (e.g. raw_attendance) are slow
    # to merge — prefer the duckdb destination for frequent large merges.
    table_format = table_format or os.getenv("STAGE1_TABLE_FORMAT")
    if destination_type == "filesystem":
        stage1_path = os.getenv("STAGE1_PATH", "./oss_framework/data/stage1")

        destination_kwargs = {"bucket_url": f"{stage1_path}/transactional/aeries"}
        if table_format != "iceberg":
            destination_kwargs["layout"] = (
                "{table_name}/load_date={curr_date}/{load_id}.{file_id}.{ext}"
            )

        pipeline = dlt.pipeline(
            pipeline_name="aeries_to_stage1",
            destination=dlt.destinations.filesystem(**destination_kwargs),
            dataset_name=dataset_name,
            **pipeline_kwargs(),
        )
        loader_file_format = "parquet"
    else:
        db_path = os.getenv("DUCKDB_DATABASE_PATH", "./oss_framework/data/analytics.duckdb")

        if refresh == "drop_sources":
            # The sync step derives main.raw_* views over the aeries_stage1
            # tables; DuckDB blocks dropping a table with dependent views, so
            # the derived views must go before dlt drops the landing tables.
            _drop_derived_raw_views(db_path)

        pipeline = dlt.pipeline(
            pipeline_name="aeries_to_duckdb",
            destination=dlt.destinations.duckdb(credentials=db_path),
            dataset_name=dataset_name,
            **pipeline_kwargs(),
        )
        loader_file_format = None

    source = aeries_source(base_url=base_url or "", api_key=api_key or "", test_mode=test_mode)
    if destination_type == "filesystem" and table_format == "iceberg":
        # Iceberg tables enable true primary-key merge (upsert) loads
        for resource in source.resources.values():
            resource.apply_hints(table_format="iceberg")
    info = pipeline.run(source, loader_file_format=loader_file_format, refresh=refresh)

    target_db = os.getenv("DUCKDB_DATABASE_PATH", "./oss_framework/data/analytics.duckdb")
    stage1_root = os.getenv("STAGE1_PATH", "./oss_framework/data/stage1")
    sync_stage1_raw_views_to_duckdb(
        db_path=target_db,
        dataset_name=dataset_name,
        destination_type=destination_type,
        stage1_path=stage1_root,
    )

    print("\n✅ Pipeline completed successfully")
    print(f"   Pipeline: {info.pipeline.pipeline_name}")
    print(f"   Destination: {destination_type}")
    print(f"   Dataset: {dataset_name}")
    print(f"   Loads: {len(info.loads_ids)}")

    return info


if __name__ == "__main__":
    import sys

    destination = sys.argv[1] if len(sys.argv) > 1 else "filesystem"
    test_mode = "--test" in sys.argv or "--test-mode" in sys.argv

    run_aeries_pipeline(
        destination_type=destination,
        test_mode=test_mode,
        refresh="drop_sources" if "--refresh" in sys.argv else None,
    )
