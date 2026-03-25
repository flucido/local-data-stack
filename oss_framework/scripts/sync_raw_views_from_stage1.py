#!/usr/bin/env python3
"""Create DuckDB compatibility views for raw_* from Stage 1 Parquet."""

from __future__ import annotations

from pathlib import Path

import duckdb

from config import DUCKDB_DATABASE_PATH, STAGE1_PATH


RAW_ENTITIES = [
    "raw_students",
    "raw_attendance",
    "raw_academic_records",
    "raw_discipline",
    "raw_enrollment",
    "raw_aeries_programs",
    "raw_aeries_gpa",
]

# Mapping from raw_* entity names to their corresponding Aeries domain directories
DOMAIN_MAPPING = {
    "raw_students": "students",
    "raw_attendance": "attendance_transformed",
    "raw_academic_records": "grades_transformed",
    "raw_discipline": "discipline_transformed",
    "raw_enrollment": "enrollment",
    "raw_aeries_programs": "programs",
    "raw_aeries_gpa": "gpa",
}


def _base_table_exists(con: duckdb.DuckDBPyConnection, name: str) -> bool:
    row = con.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_schema = 'main'
          AND table_name = ?
          AND table_type = 'BASE TABLE'
        """,
        [name],
    ).fetchone()
    return bool(row and row[0] > 0)


def _view_exists(con: duckdb.DuckDBPyConnection, name: str) -> bool:
    row = con.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_schema = 'main'
          AND table_name = ?
          AND table_type = 'VIEW'
        """,
        [name],
    ).fetchone()
    return bool(row and row[0] > 0)


def sync_raw_views_from_stage1(
    db_path: str | Path | None = None,
    stage1_path: str | Path | None = None,
    rename_legacy_tables: bool = True,
) -> dict:
    """Create or replace raw_* views for AeRIES Parquet files.

    Handles year=YYYY-YYYY partitioning for all 7 domains.
    """
    db = str(db_path or DUCKDB_DATABASE_PATH)
    stage1 = Path(stage1_path or STAGE1_PATH).resolve()

    con = duckdb.connect(db)
    try:
        actions: list[str] = []
        for entity in RAW_ENTITIES:
            legacy = f"legacy_{entity}"

            if rename_legacy_tables and _base_table_exists(con, entity):
                # Avoid overwriting if a legacy table already exists
                if not _base_table_exists(con, legacy) and not _view_exists(con, legacy):
                    con.execute(f"ALTER TABLE {entity} RENAME TO {legacy}")
                    actions.append(f"renamed_table:{entity}->{legacy}")
                else:
                    actions.append(f"kept_table:{entity} (legacy exists)")

            # All domains now use year-based partitioning at stage1/aeries/{domain}/year=*/
            domain = DOMAIN_MAPPING.get(entity, entity.replace("raw_aeries_", ""))
            parquet_glob = stage1 / "aeries" / domain / "year=*" / "*.parquet"

            # DuckDB doesn't support prepared parameters for this DDL statement.
            parquet_glob_sql = str(parquet_glob).replace("'", "''")
            con.execute(
                f"CREATE OR REPLACE VIEW {entity} AS SELECT * FROM read_parquet('{parquet_glob_sql}')"
            )
            actions.append(f"view:{entity}<-{parquet_glob}")

        return {
            "db_path": db,
            "stage1_path": str(stage1),
            "actions": actions,
        }
    finally:
        con.close()


if __name__ == "__main__":
    result = sync_raw_views_from_stage1()
    print("✅ Synced raw_* views from Stage 1 Parquet")
    for a in result["actions"]:
        print(f"  - {a}")
