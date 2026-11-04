#!/usr/bin/env python3
"""
Data Quality Tests for Stage 1 dlt Pipelines

Tests both Aeries and Excel import pipelines to ensure:
- Parquet files are created
- Data schemas are correct
- Required fields are populated
- Data quality meets standards
"""

import os
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "pipelines"))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from aeries_dlt_pipeline import run_aeries_pipeline
from excel_imports_dlt_pipeline import run_excel_imports_pipeline

# Default filesystem mode: dlt writes under <bucket>/<dataset_name>/<layout>;
# run_aeries_pipeline uses dataset "aeries_stage1" and layout
# "{table_name}/load_date={curr_date}/{load_id}.{file_id}.{ext}".
# Opt-in STAGE1_TABLE_FORMAT=iceberg switches to Iceberg tables with true
# primary-key merge (see TestIcebergMerge).
AERIES_DATASET = "aeries_stage1"


DLT_PIPELINES_DIR_ENV = "DLT_PIPELINES_DIR"
STAGE1_PATH_ENV = "STAGE1_PATH"


@pytest.fixture(scope="module")
def isolated_stage1(tmp_path_factory):
    """Point dlt state and the Stage 1 bucket at a throwaway directory.

    dlt persists pipeline state in ~/.dlt/pipelines/<name> by default, and the
    pipelines read the bucket location from STAGE1_PATH. Left at their defaults,
    a run on a warm machine resumes from a previous run's state and writes to
    whatever bucket it recorded then — which is why these tests used to fail
    with "Missing load_date partition for raw_students" on a clean worktree.
    Pinning both makes the run self-contained, so the tests read exactly the
    files they just wrote.
    """
    root = tmp_path_factory.mktemp("stage1")
    previous = {key: os.environ.get(key) for key in (DLT_PIPELINES_DIR_ENV, STAGE1_PATH_ENV)}
    os.environ[DLT_PIPELINES_DIR_ENV] = str(root / "pipelines")
    os.environ[STAGE1_PATH_ENV] = str(root / "stage1")
    try:
        yield root / "stage1"
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@pytest.fixture(scope="module")
def stage1_path(isolated_stage1):
    """Get Stage 1 data directory (isolated per test session)"""
    return isolated_stage1


def latest_load_dir(stage1_path: Path, table: str) -> Path | None:
    """Most recent load_date=* partition dir for a dlt-managed Aeries table.

    Globbing instead of computing today's date avoids local-vs-UTC drift in
    dlt's {curr_date} placeholder.
    """
    base = stage1_path / "transactional" / "aeries" / AERIES_DATASET / table
    if not base.exists():
        return None
    load_dirs = sorted(base.glob("load_date=*"))
    return load_dirs[-1] if load_dirs else None


def latest_parquet(stage1_path: Path, table: str) -> Path | None:
    """Most recent Parquet file for a dlt-managed Aeries table."""
    load_dir = latest_load_dir(stage1_path, table)
    if load_dir is None:
        return None
    files = sorted(load_dir.glob("*.parquet"))
    return files[-1] if files else None


@pytest.fixture(scope="module")
def aeries_pipeline_run(isolated_stage1):
    """Run Aeries pipeline once for all tests"""
    return run_aeries_pipeline(destination_type="filesystem", test_mode=True)


@pytest.fixture(scope="module")
def excel_pipeline_run(isolated_stage1):
    """Run Excel pipeline once for all tests"""
    return run_excel_imports_pipeline(destination_type="filesystem")


class TestAeriesPipeline:
    """Tests for Aeries SIS dlt pipeline"""

    def test_pipeline_completed_successfully(self, aeries_pipeline_run):
        """Verify pipeline ran without errors"""
        assert aeries_pipeline_run is not None
        assert len(aeries_pipeline_run.loads_ids) > 0
        assert not aeries_pipeline_run.has_failed_jobs

    def test_parquet_files_created(self, stage1_path):
        """Verify Parquet files exist for all Aeries tables"""
        expected_tables = [
            "raw_students",
            "raw_attendance",
            "raw_academic_records",
            "raw_discipline",
            "raw_enrollment",
        ]

        for table in expected_tables:
            load_dir = latest_load_dir(stage1_path, table)
            assert load_dir is not None, f"Missing load_date partition for {table}"

            parquet_files = list(load_dir.glob("*.parquet"))
            assert len(parquet_files) > 0, f"No Parquet files in {load_dir}"

    def test_students_data_quality(self, stage1_path):
        """Validate students data quality"""
        parquet_file = latest_parquet(stage1_path, "raw_students")

        if parquet_file is None:
            pytest.skip("Students Parquet file not found")

        df = pd.read_parquet(parquet_file)

        assert len(df) > 0, "Students table is empty"
        assert "student_id" in df.columns, "Missing student_id column"
        assert df["student_id"].notna().all(), "Found null student_ids"
        assert df["student_id"].is_unique, "Duplicate student_ids found"

    def test_attendance_data_quality(self, stage1_path):
        """Validate attendance data quality"""
        parquet_file = latest_parquet(stage1_path, "raw_attendance")

        if parquet_file is None:
            pytest.skip("Attendance Parquet file not found")

        df = pd.read_parquet(parquet_file)

        assert len(df) > 0, "Attendance table is empty"
        assert "attendance_id" in df.columns, "Missing attendance_id"
        assert "student_id" in df.columns, "Missing student_id"
        assert df["attendance_id"].notna().all(), "Found null attendance_ids"
        assert df["student_id"].notna().all(), "Found null student_ids"

    def test_academic_records_data_quality(self, stage1_path):
        """Validate academic records data quality"""
        parquet_file = latest_parquet(stage1_path, "raw_academic_records")

        if parquet_file is None:
            pytest.skip("Academic records Parquet file not found")

        df = pd.read_parquet(parquet_file)

        assert len(df) > 0, "Academic records table is empty"
        assert "record_id" in df.columns, "Missing record_id"
        assert "student_id" in df.columns, "Missing student_id"
        assert df["record_id"].notna().all(), "Found null record_ids"

    def test_record_counts_reasonable(self, stage1_path):
        """Verify record counts are within expected ranges"""
        students_file = latest_parquet(stage1_path, "raw_students")
        if students_file is not None:
            df_students = pd.read_parquet(students_file)
            assert (
                1000 <= len(df_students) <= 10000
            ), f"Unexpected student count: {len(df_students)}"

        attendance_file = latest_parquet(stage1_path, "raw_attendance")
        if attendance_file is not None:
            df_attendance = pd.read_parquet(attendance_file)
            assert (
                10000 <= len(df_attendance) <= 1000000
            ), f"Unexpected attendance count: {len(df_attendance)}"


class TestIcebergMerge:
    """Merge (upsert) semantics on the filesystem destination via Iceberg"""

    def test_reload_dedupes_on_primary_key(self, tmp_path):
        """Loading the same students twice must not duplicate rows.

        Proves write_disposition="merge" with primary_key=["student_id"]
        actually upserts on the Iceberg lake (the plain filesystem
        destination would silently append).
        """
        import uuid

        import dlt
        from aeries_dlt_pipeline import aeries_source

        def _run_students_load(pipeline):
            source = aeries_source(test_mode=True).with_resources("raw_students")
            for resource in source.resources.values():
                resource.apply_hints(table_format="iceberg")
            info = pipeline.run(source, loader_file_format="parquet")
            assert not info.has_failed_jobs
            return info

        # Same isolation as the module fixtures: keep state out of ~/.dlt.
        pipelines_dir = str(tmp_path / "pipelines")
        pipeline = dlt.pipeline(
            pipeline_name=f"iceberg_merge_{uuid.uuid4().hex[:8]}",
            pipelines_dir=pipelines_dir,
            destination=dlt.destinations.filesystem(
                bucket_url=str(tmp_path / "bucket"),
            ),
            dataset_name=AERIES_DATASET,
        )

        _run_students_load(pipeline)
        df1 = pipeline.dataset().raw_students.df()
        assert len(df1) == 1700

        # Second load of identical data — merge must dedupe, not append
        _run_students_load(pipeline)
        df2 = pipeline.dataset().raw_students.df()
        assert len(df2) == 1700, f"Merge did not dedupe: {len(df2)} rows after 2 loads"
        assert df2["student_id"].is_unique


class TestExcelImportsPipeline:
    """Tests for Excel imports dlt pipeline"""

    def test_pipeline_completed_successfully(self, excel_pipeline_run):
        """Verify pipeline ran without errors

        Note: If no Excel files are configured, loads_ids will be empty but
        the pipeline should still complete successfully (no failed jobs).
        """
        assert excel_pipeline_run is not None
        assert not excel_pipeline_run.has_failed_jobs
        # loads_ids may be empty if no Excel files are configured - this is OK

    def test_excel_directories_created(self, stage1_path):
        """Verify Excel import directories exist"""
        excel_dir = stage1_path / "reference" / "excel"
        assert excel_dir.exists(), f"Excel directory missing: {excel_dir}"

    def test_parquet_files_structure(self, stage1_path):
        """Verify Parquet structure for Excel imports"""
        excel_dir = stage1_path / "reference" / "excel"
        today = date.today().isoformat()

        expected_tables = ["raw_d_and_f", "raw_demographic", "raw_rfep"]

        for table in expected_tables:
            table_dir = excel_dir / table / f"load_date={today}"
            if table_dir.exists():
                parquet_files = list(table_dir.glob("*.parquet"))
                if len(parquet_files) > 0:
                    df = pd.read_parquet(parquet_files[0])
                    assert "created_at" in df.columns, f"Missing created_at in {table}"
                    assert "load_date" in df.columns, f"Missing load_date in {table}"


class TestIntegration:
    """Integration tests for complete Stage 1 pipeline"""

    def test_orchestrator_runs_successfully(self):
        """Test that orchestrator can run both pipelines"""
        from run_stage1_ingestion import run_stage1_ingestion

        try:
            run_stage1_ingestion()
        except SystemExit as e:
            if e.code == 1:
                pytest.fail("Orchestrator reported failures")
        except Exception as e:
            pytest.fail(f"Orchestrator raised exception: {e}")

    def test_stage1_directory_structure(self, stage1_path):
        """Verify complete Stage 1 directory structure"""
        assert stage1_path.exists(), "Stage 1 directory missing"

        transactional_dir = stage1_path / "transactional"
        reference_dir = stage1_path / "reference"

        assert transactional_dir.exists(), "Transactional directory missing"
        assert reference_dir.exists(), "Reference directory missing"

        aeries_dir = transactional_dir / "aeries"
        excel_dir = reference_dir / "excel"

        assert aeries_dir.exists(), "Aeries directory missing"
        assert excel_dir.exists(), "Excel directory missing"
