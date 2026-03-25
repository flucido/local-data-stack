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
from pathlib import Path
import pytest
import pandas as pd
from datetime import date

sys.path.insert(0, str(Path(__file__).parent.parent / "pipelines"))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from aeries_dlt_pipeline import run_aeries_pipeline
from excel_imports_dlt_pipeline import run_excel_imports_pipeline


@pytest.fixture(scope="module")
def stage1_path():
    """Get Stage 1 data directory"""
    return Path(os.getenv("STAGE1_PATH", "./oss_framework/data/stage1"))


@pytest.fixture(scope="module")
def aeries_pipeline_run():
    """Run Aeries pipeline once for all tests"""
    return run_aeries_pipeline(destination_type="filesystem", test_mode=True)


@pytest.fixture(scope="module")
def excel_pipeline_run():
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
        aeries_dir = stage1_path / "transactional" / "aeries"
        today = date.today().isoformat()

        expected_tables = [
            "raw_students",
            "raw_attendance",
            "raw_academic_records",
            "raw_discipline",
            "raw_enrollment",
        ]

        for table in expected_tables:
            table_dir = aeries_dir / table / f"load_date={today}"
            assert table_dir.exists(), f"Missing directory: {table_dir}"

            parquet_files = list(table_dir.glob("*.parquet"))
            assert len(parquet_files) > 0, f"No Parquet files in {table_dir}"

    def test_students_data_quality(self, stage1_path):
        """Validate students data quality"""
        aeries_dir = stage1_path / "transactional" / "aeries"
        today = date.today().isoformat()
        parquet_file = (
            aeries_dir / "raw_students" / f"load_date={today}" / "part-000.parquet"
        )

        if not parquet_file.exists():
            pytest.skip("Students Parquet file not found")

        df = pd.read_parquet(parquet_file)

        assert len(df) > 0, "Students table is empty"
        assert "student_id" in df.columns, "Missing student_id column"
        assert df["student_id"].notna().all(), "Found null student_ids"
        assert df["student_id"].is_unique, "Duplicate student_ids found"

    def test_attendance_data_quality(self, stage1_path):
        """Validate attendance data quality"""
        aeries_dir = stage1_path / "transactional" / "aeries"
        today = date.today().isoformat()
        parquet_file = (
            aeries_dir / "raw_attendance" / f"load_date={today}" / "part-000.parquet"
        )

        if not parquet_file.exists():
            pytest.skip("Attendance Parquet file not found")

        df = pd.read_parquet(parquet_file)

        assert len(df) > 0, "Attendance table is empty"
        assert "attendance_id" in df.columns, "Missing attendance_id"
        assert "student_id" in df.columns, "Missing student_id"
        assert df["attendance_id"].notna().all(), "Found null attendance_ids"
        assert df["student_id"].notna().all(), "Found null student_ids"

    def test_academic_records_data_quality(self, stage1_path):
        """Validate academic records data quality"""
        aeries_dir = stage1_path / "transactional" / "aeries"
        today = date.today().isoformat()
        parquet_file = (
            aeries_dir
            / "raw_academic_records"
            / f"load_date={today}"
            / "part-000.parquet"
        )

        if not parquet_file.exists():
            pytest.skip("Academic records Parquet file not found")

        df = pd.read_parquet(parquet_file)

        assert len(df) > 0, "Academic records table is empty"
        assert "record_id" in df.columns, "Missing record_id"
        assert "student_id" in df.columns, "Missing student_id"
        assert df["record_id"].notna().all(), "Found null record_ids"

    def test_record_counts_reasonable(self, stage1_path):
        """Verify record counts are within expected ranges"""
        aeries_dir = stage1_path / "transactional" / "aeries"
        today = date.today().isoformat()

        students_file = (
            aeries_dir / "raw_students" / f"load_date={today}" / "part-000.parquet"
        )
        if students_file.exists():
            df_students = pd.read_parquet(students_file)
            assert 1000 <= len(df_students) <= 10000, (
                f"Unexpected student count: {len(df_students)}"
            )

        attendance_file = (
            aeries_dir / "raw_attendance" / f"load_date={today}" / "part-000.parquet"
        )
        if attendance_file.exists():
            df_attendance = pd.read_parquet(attendance_file)
            assert 10000 <= len(df_attendance) <= 1000000, (
                f"Unexpected attendance count: {len(df_attendance)}"
            )


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
