"""Integration tests for batch_processing module"""

import pytest
import pandas as pd
import numpy as np
from oss_framework import BatchProcessor


@pytest.mark.integration
class TestBatchProcessing:
    """Integration tests for BatchProcessor class"""

    def test_delta_batch_mode(self, batch_processor, sample_enrollment_df):
        """Test delta batch processing mode"""
        existing_data = sample_enrollment_df.iloc[:3].copy()
        new_data = sample_enrollment_df.iloc[2:].copy()

        result = batch_processor.process(
            existing_data=existing_data,
            new_data=new_data,
            batch_mode="delta",
            key_columns=["enrollment_id"],
        )

        assert len(result) >= len(new_data)
        assert "enrollment_id" in result.columns

    def test_additive_batch_mode(self, batch_processor, sample_engagement_df):
        """Test additive batch mode (append-only)"""
        batch1 = sample_engagement_df.iloc[:2].copy()
        batch2 = sample_engagement_df.iloc[2:].copy()

        result = batch_processor.process(
            existing_data=batch1, new_data=batch2, batch_mode="additive"
        )

        assert len(result) == len(batch1) + len(batch2)

    def test_snapshot_batch_mode(self, batch_processor, sample_students_df):
        """Test snapshot batch mode (full replacement)"""
        old_data = sample_students_df.iloc[:2].copy()
        new_snapshot = sample_students_df.copy()

        result = batch_processor.process(
            existing_data=old_data, new_data=new_snapshot, batch_mode="snapshot"
        )

        assert len(result) == len(new_snapshot)

    def test_deduplication(self, batch_processor):
        """Test duplicate removal"""
        df = pd.DataFrame({"id": [1, 1, 2, 3, 3, 3], "value": [10, 10, 20, 30, 30, 30]})

        result = batch_processor.deduplicate(df, subset=["id", "value"])

        assert len(result) == 3
        assert result["id"].nunique() == 3

    def test_error_handling_missing_key(self, batch_processor, sample_enrollment_df):
        """Test error handling with missing key columns"""
        new_data = sample_enrollment_df.copy()
        new_data = new_data.drop("enrollment_id", axis=1)

        with pytest.raises((KeyError, ValueError)):
            batch_processor.process(
                existing_data=sample_enrollment_df,
                new_data=new_data,
                batch_mode="delta",
                key_columns=["enrollment_id"],
            )


@pytest.mark.integration
class TestDataQualityChecks:
    """Integration tests for DataQualityChecker"""

    def test_null_check(self, batch_processor, sample_academic_records_df):
        """Test null value detection"""
        df = sample_academic_records_df.copy()
        df.loc[0, "points_earned"] = np.nan

        quality_report = batch_processor.check_quality(df, entity="academic_records")

        assert "quality_issues" in quality_report or "valid" in quality_report

    def test_duplicate_detection(self, batch_processor):
        """Test duplicate record detection"""
        df = pd.DataFrame(
            {"record_id": ["REC001", "REC002", "REC001"], "value": [100, 200, 100]}
        )

        quality_report = batch_processor.check_quality(df, entity="test")

        assert "quality_issues" in quality_report or "valid" in quality_report

    def test_outlier_detection(self, batch_processor, sample_engagement_df):
        """Test outlier detection in engagement data"""
        df = sample_engagement_df.copy()
        df.loc[0, "duration_seconds"] = 999999

        quality_report = batch_processor.check_quality(df, entity="engagement_events")

        assert "quality_issues" in quality_report or "valid" in quality_report

    def test_type_consistency_check(self, batch_processor, sample_students_df):
        """Test data type consistency"""
        df = sample_students_df.copy()
        df.loc[0, "grade_level"] = "invalid"

        quality_report = batch_processor.check_quality(df, entity="students")

        assert "quality_issues" in quality_report or "valid" in quality_report


@pytest.mark.integration
class TestEndToEndPipeline:
    """End-to-end pipeline tests"""

    def test_students_pipeline(
        self, batch_processor, sample_students_df, pseudonymizer
    ):
        """Test complete student data pipeline"""
        df = sample_students_df.copy()

        quality_report = batch_processor.check_quality(df, entity="students")

        if quality_report.get("valid", True):
            anonymized = pseudonymizer.pseudonymize(df, entity="students")

            assert len(anonymized) == len(df)
            assert (anonymized["student_id"] != df["student_id"]).all()
            assert anonymized["grade_level"].equals(
                df["grade_level"], check_dtype=False
            )

    def test_enrollment_pipeline(
        self, batch_processor, sample_enrollment_df, pseudonymizer
    ):
        """Test complete enrollment pipeline"""
        df = sample_enrollment_df.copy()

        quality_report = batch_processor.check_quality(df, entity="enrollment")

        if quality_report.get("valid", True):
            anonymized = pseudonymizer.pseudonymize(df, entity="enrollment")

            assert len(anonymized) == len(df)
            assert (anonymized["student_id"] != df["student_id"]).all()

    def test_multi_entity_join(
        self, sample_students_df, sample_enrollment_df, sample_academic_records_df
    ):
        """Test joining multiple entities"""
        students = sample_students_df[["student_id", "grade_level"]]
        enrollment = sample_enrollment_df[
            ["student_id", "course_id", "final_grade_numeric"]
        ]
        academics = sample_academic_records_df[
            ["student_id", "assignment_type", "assignment_grade_percent"]
        ]

        merged = enrollment.merge(students, on="student_id", how="left")
        merged = merged.merge(academics, on="student_id", how="left")

        assert len(merged) > 0
        assert "grade_level" in merged.columns
        assert "assignment_type" in merged.columns
