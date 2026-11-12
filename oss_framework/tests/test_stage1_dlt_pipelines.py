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
DUCKDB_DATABASE_PATH_ENV = "DUCKDB_DATABASE_PATH"


@pytest.fixture(scope="module")
def isolated_stage1(tmp_path_factory):
    """Point dlt state, Stage 1 bucket, and DuckDB at a throwaway directory."""
    root = tmp_path_factory.mktemp("stage1")
    previous = {
        key: os.environ.get(key)
        for key in (DLT_PIPELINES_DIR_ENV, STAGE1_PATH_ENV, DUCKDB_DATABASE_PATH_ENV)
    }
    os.environ[DLT_PIPELINES_DIR_ENV] = str(root / "pipelines")
    os.environ[STAGE1_PATH_ENV] = str(root / "stage1")
    os.environ[DUCKDB_DATABASE_PATH_ENV] = str(root / "analytics.duckdb")
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


class TestDuckDbDestinationFullReload:
    """Orchestrated Stage 1 contract: duckdb destination + refresh="drop_sources".

    On the plain filesystem destination dlt degrades merge to append and the
    landing dir accumulates one file-set per load; sync_stage1_raw_views_to_duckdb
    materializes every accumulated file, so a rebuild over an existing warehouse
    multiplied each row by the number of historical loads (17x observed on
    2026-11-12). The orchestrated path must reload deterministically instead.
    """

    def test_reload_with_refresh_is_idempotent(self, tmp_path, monkeypatch):
        import duckdb
        from aeries_dlt_pipeline import run_aeries_pipeline

        class _StubClient:
            @staticmethod
            def get_students():
                return [
                    {
                        "student_id": f"S{i:03d}",
                        "first_name": "First",
                        "last_name": "Last",
                        "date_of_birth": "2015-01-01",
                        "grade_level": 3,
                        "school_id": "101",
                    }
                    for i in range(1, 8)
                ]

            @staticmethod
            def get_attendance():
                return []

            @staticmethod
            def get_grades():
                return []

            @staticmethod
            def get_discipline():
                return []

            @staticmethod
            def get_enrollment():
                return [
                    {
                        "student_id": f"S{i:03d}",
                        "school_id": "101",
                        "school_year": "2024-2025",
                        "enrollment_id": f"E{i:03d}",
                        "enrollment_status": "ACTIVE",
                    }
                    for i in range(1, 8)
                ]

        monkeypatch.setattr("aeries_dlt_pipeline.get_sis_connector", lambda **kwargs: _StubClient())
        monkeypatch.setenv("DUCKDB_DATABASE_PATH", str(tmp_path / "analytics.duckdb"))
        monkeypatch.setenv("DLT_PIPELINES_DIR", str(tmp_path / "pipelines"))

        for _attempt in (1, 2):
            info = run_aeries_pipeline(
                destination_type="duckdb", test_mode=True, refresh="drop_sources"
            )
            assert not info.has_failed_jobs

        con = duckdb.connect(str(tmp_path / "analytics.duckdb"), read_only=True)
        try:
            rows, distinct, loads = con.execute(
                """
                SELECT count(*), count(DISTINCT student_id), count(DISTINCT _dlt_load_id)
                FROM main.raw_students
                """
            ).fetchone()
        finally:
            con.close()
        assert (rows, distinct, loads) == (7, 7, 1)


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


class TestStage1ToStage2Contract:
    """Verify Stage 1 -> Stage 2 DuckDB raw_* views, test failure handling, and setup script safety."""

    def test_stage1_creates_main_raw_views_in_duckdb(self, aeries_pipeline_run):
        import duckdb

        db_path = Path(os.environ[DUCKDB_DATABASE_PATH_ENV])
        assert db_path.exists(), f"Expected DuckDB warehouse at {db_path}"

        con = duckdb.connect(str(db_path), read_only=True)
        try:
            for tbl in (
                "raw_students",
                "raw_attendance",
                "raw_academic_records",
                "raw_discipline",
                "raw_enrollment",
            ):
                count = con.execute(f"SELECT COUNT(*) FROM main.{tbl}").fetchone()[0]
                assert count > 0, f"Expected rows in main.{tbl}"
        finally:
            con.close()

    def test_run_pipeline_returns_false_when_dbt_tests_fail_by_default(self, monkeypatch):
        from scripts.run_pipeline import PipelineOrchestrator

        orch = PipelineOrchestrator()
        monkeypatch.setattr(orch, "stage1_ingestion", lambda: True)
        monkeypatch.setattr(orch, "stage2_refinement", lambda: True)
        monkeypatch.setattr(orch, "stage3_analytics", lambda: True)
        monkeypatch.setattr(orch, "stage4_export", lambda: True)
        monkeypatch.setattr(orch, "run_tests", lambda: False)

        assert orch.run_full_pipeline(skip_tests=False) is False
        assert orch.run_full_pipeline(skip_tests=False, allow_test_failures=True) is True

    def test_setup_week1_script_does_not_overwrite_tracked_modules(self):
        repo_root = Path(__file__).resolve().parents[2]
        setup_script = (
            repo_root / "oss_framework" / "scripts" / "setup_week1_automated.sh"
        ).read_text()
        assert 'cat > "$SCRIPTS_DIR/' not in setup_script
        assert ".venv" in setup_script
        assert 'pip install -e ".[dev,nl-query]"' in setup_script

    def test_blue_green_atomic_duckdb_build_and_swap(self, tmp_path, monkeypatch):
        from scripts.run_pipeline import PipelineOrchestrator

        prod_db = tmp_path / "analytics.duckdb"
        prod_db.write_bytes(b"prod_v1")

        orch = PipelineOrchestrator(db_path=prod_db)
        observed_env_paths: list[str] = []

        def fake_stage1() -> bool:
            observed_env_paths.append(orch.active_db_path_str())
            Path(orch.active_db_path_str()).write_bytes(b"building_v2")
            return True

        monkeypatch.setattr(orch, "stage1_ingestion", fake_stage1)
        monkeypatch.setattr(orch, "stage2_refinement", lambda: True)
        monkeypatch.setattr(orch, "stage3_analytics", lambda: True)
        monkeypatch.setattr(orch, "stage4_export", lambda: True)

        # Failed test run must NOT swap building -> prod
        monkeypatch.setattr(orch, "run_tests", lambda: False)
        assert orch.run_full_pipeline(skip_tests=False) is False
        assert prod_db.read_bytes() == b"prod_v1"

        # Passing run must build against the building db and atomically swap into prod_db.
        # Regression guard for the dbt-duckdb catalog-name derivation: the building
        # basename must contain exactly one dot so dbt's splitext-derived ref catalog
        # name matches DuckDB's own attached catalog name (which strips at the first
        # dot). "analytics.duckdb.building" breaks every compiled ref with:
        # Binder Error: Catalog "analytics.duckdb" does not exist!
        monkeypatch.setattr(orch, "run_tests", lambda: True)
        assert orch.run_full_pipeline(skip_tests=False) is True
        assert observed_env_paths[-1].endswith("analytics_building.duckdb")
        assert orch.building_db_path.name.count(".") == 1
        assert prod_db.read_bytes() == b"building_v2"
        assert not orch.building_db_path.exists()
