#!/usr/bin/env python3
"""Generate Stage 1 Parquet sample data.

This produces Stage 1 Parquet files under STAGE1_PATH and is intended to
validate the Stage1->DuckDB views->dbt workflow without requiring live Aeries
connectivity.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import duckdb

from config import STAGE1_PATH


@dataclass(frozen=True)
class Stage1Paths:
    base: Path
    load_date: str

    def entity_dir(self, entity: str) -> Path:
        return (
            self.base
            / "transactional"
            / "aeries"
            / entity
            / f"load_date={self.load_date}"
        )


def _copy_query_to_parquet(
    con: duckdb.DuckDBPyConnection, query: str, out_file: Path
) -> None:
    out_file.parent.mkdir(parents=True, exist_ok=True)
    con.execute(
        "COPY (" + query + ") TO ? (FORMAT PARQUET)",
        [str(out_file)],
    )


def generate_stage1_parquet(
    stage1_path: Path | None = None, load_date: str | None = None
) -> dict:
    stage1 = Path(stage1_path or STAGE1_PATH).resolve()
    ld = load_date or date.today().isoformat()
    paths = Stage1Paths(base=Path(stage1), load_date=ld)

    con = duckdb.connect(":memory:")
    try:
        # Students
        students_query = """
        SELECT
            'STU' || LPAD(CAST(id AS VARCHAR), 4, '0') AS student_id,
            'Student' AS first_name,
            'Name' || id AS last_name,
            CAST(DATE '2010-01-01' + (INTERVAL '1' DAY) * id AS DATE) AS date_of_birth,
            CASE WHEN id % 2 = 0 THEN 'M' ELSE 'F' END AS gender,
            CASE id % 5
                WHEN 0 THEN 'Hispanic'
                WHEN 1 THEN 'White'
                WHEN 2 THEN 'Asian'
                WHEN 3 THEN 'Black'
                ELSE 'Other'
            END AS ethnicity,
            CASE WHEN id % 4 = 0 THEN true ELSE false END AS free_reduced_lunch,
            CASE WHEN id % 10 = 0 THEN true ELSE false END AS ell_status,
            CASE WHEN id % 20 = 0 THEN true ELSE false END AS special_education,
            CASE WHEN id % 25 = 0 THEN true ELSE false END AS section_504,
            CASE WHEN id % 50 = 0 THEN true ELSE false END AS homeless,
            CASE WHEN id % 60 = 0 THEN true ELSE false END AS foster_care,
            'SCH' || (id % 3 + 1) AS school_id,
            (id % 12) + 1 AS grade_level,
            CAST(DATE '2024-08-01' + (INTERVAL '1' DAY) * (id % 30) AS DATE) AS enrollment_date,
            CAST(NULL AS DATE) AS withdrawal_date,
            CASE WHEN id % 7 = 0 THEN 'SPANISH' ELSE 'ENGLISH' END AS home_language,
            CAST(TIMESTAMP '2025-01-01 00:00:00' + (INTERVAL '1' SECOND) * id AS TIMESTAMP) AS created_at,
            CAST(TIMESTAMP '2025-01-01 00:00:00' + (INTERVAL '1' SECOND) * id AS TIMESTAMP) AS updated_at
        FROM (SELECT * FROM RANGE(1, 1701) AS r(id))
        """
        _copy_query_to_parquet(
            con,
            students_query,
            paths.entity_dir("raw_students") / "part-000.parquet",
        )

        # Attendance
        attendance_query = """
        SELECT
            'ATT' || LPAD(CAST(id AS VARCHAR), 8, '0') AS attendance_id,
            'STU' || LPAD(CAST((id % 1700) + 1 AS VARCHAR), 4, '0') AS student_id,
            'SCH' || ((id % 1700) % 3 + 1) AS school_id,
            CAST(DATE '2025-01-01' + (INTERVAL '1' DAY) * ((id - 1) / 1700) AS DATE) AS attendance_date,
            CASE WHEN id % 20 = 0 THEN 'Absent' ELSE 'Present' END AS attendance_status,
            CASE WHEN id % 20 = 0 THEN 'SICK' ELSE NULL END AS absence_reason,
            CASE WHEN id % 20 = 0 THEN false ELSE true END AS present_flag,
            CASE WHEN id % 20 = 0 THEN true ELSE false END AS absent_flag,
            CASE WHEN id % 33 = 0 THEN true ELSE false END AS tardy_flag,
            CASE WHEN id % 40 = 0 THEN true ELSE false END AS excused_flag,
            CASE WHEN id % 45 = 0 THEN true ELSE false END AS unexcused_flag,
            CAST(TIMESTAMP '2025-01-01 00:00:00' + (INTERVAL '1' SECOND) * id AS TIMESTAMP) AS created_at
        FROM (SELECT * FROM RANGE(1, 45001) AS r(id))
        """
        _copy_query_to_parquet(
            con,
            attendance_query,
            paths.entity_dir("raw_attendance") / "part-000.parquet",
        )

        # Academic records
        academic_query = """
        SELECT
            'GRD' || LPAD(CAST(id AS VARCHAR), 8, '0') AS record_id,
            'STU' || LPAD(CAST((id % 1700) + 1 AS VARCHAR), 4, '0') AS student_id,
            'SCH' || ((id % 1700) % 3 + 1) AS school_id,
            'CRS' || ((id % 50) + 1) AS course_id,
            'SEC' || ((id % 100) + 1) AS section_id,
            'TCH' || ((id % 25) + 1) AS teacher_id,
            CASE WHEN id % 100 < 10 THEN 'F'
                 WHEN id % 100 < 25 THEN 'D'
                 WHEN id % 100 < 50 THEN 'C'
                 WHEN id % 100 < 75 THEN 'B'
                 ELSE 'A' END AS grade,
            CAST(50 + (id % 50) AS DECIMAL(5,2)) AS score,
            'Q1' AS term,
            '2024-2025' AS school_year,
            CAST(TIMESTAMP '2025-01-01 00:00:00' + (INTERVAL '1' SECOND) * id AS TIMESTAMP) AS created_at
        FROM (SELECT * FROM RANGE(1, 200001) AS r(id))
        """
        _copy_query_to_parquet(
            con,
            academic_query,
            paths.entity_dir("raw_academic_records") / "part-000.parquet",
        )

        # Discipline
        discipline_query = """
        SELECT
            'DIS' || LPAD(CAST(id AS VARCHAR), 6, '0') AS incident_id,
            'STU' || LPAD(CAST((id % 1700) + 1 AS VARCHAR), 4, '0') AS student_id,
            'SCH' || ((id % 1700) % 3 + 1) AS school_id,
            CAST(DATE '2025-01-01' + (INTERVAL '1' DAY) * ((id - 1) / 50) AS DATE) AS incident_date,
            CASE id % 5
                WHEN 0 THEN 'Tardy'
                WHEN 1 THEN 'Behavior'
                WHEN 2 THEN 'Class Disruption'
                ELSE 'Other'
            END AS incident_type,
            CASE id % 3
                WHEN 0 THEN 'Low'
                WHEN 1 THEN 'Medium'
                ELSE 'High'
            END AS severity,
            CASE WHEN id % 7 = 0 THEN 'Parent Contact' ELSE 'Warning' END AS resolution,
            CASE WHEN id % 11 = 0 THEN 1 WHEN id % 17 = 0 THEN 2 ELSE 0 END AS suspension_days,
            CAST(TIMESTAMP '2025-01-01 00:00:00' + (INTERVAL '1' SECOND) * id AS TIMESTAMP) AS created_at
        FROM (SELECT * FROM RANGE(1, 2001) AS r(id))
        """
        _copy_query_to_parquet(
            con,
            discipline_query,
            paths.entity_dir("raw_discipline") / "part-000.parquet",
        )

        # Enrollment
        enrollment_query = """
        SELECT
            'ENR' || LPAD(CAST(id AS VARCHAR), 6, '0') AS enrollment_id,
            'STU' || LPAD(CAST(id AS VARCHAR), 4, '0') AS student_id,
            'SCH' || (id % 3 + 1) AS school_id,
            '2024-2025' AS school_year,
            CAST(DATE '2024-08-01' + (INTERVAL '1' DAY) * ((id - 1) / 1700) AS DATE) AS enrollment_date,
            CAST(NULL AS DATE) AS withdrawal_date,
            (id % 12) + 1 AS grade_level,
            'ACTIVE' AS enrollment_status,
            CAST(TIMESTAMP '2025-01-01 00:00:00' + (INTERVAL '1' SECOND) * id AS TIMESTAMP) AS created_at
        FROM (SELECT * FROM RANGE(1, 1701) AS r(id))
        """
        _copy_query_to_parquet(
            con,
            enrollment_query,
            paths.entity_dir("raw_enrollment") / "part-000.parquet",
        )

        return {
            "stage1_path": str(stage1),
            "load_date": ld,
            "entities": {
                "raw_students": str(paths.entity_dir("raw_students")),
                "raw_attendance": str(paths.entity_dir("raw_attendance")),
                "raw_academic_records": str(paths.entity_dir("raw_academic_records")),
                "raw_discipline": str(paths.entity_dir("raw_discipline")),
                "raw_enrollment": str(paths.entity_dir("raw_enrollment")),
            },
        }
    finally:
        con.close()


if __name__ == "__main__":
    result = generate_stage1_parquet()
    print("✅ Stage 1 Parquet generated")
    print(f"  - stage1_path: {result['stage1_path']}")
    print(f"  - load_date: {result['load_date']}")
    for k, v in result["entities"].items():
        print(f"  - {k}: {v}")
