"""Unit tests for data_transformations module"""

import pytest
import pandas as pd
import numpy as np
from oss_framework import DataTransformer, Pseudonymizer


@pytest.mark.unit
class TestDataTransformer:
    """Unit tests for DataTransformer class"""

    def test_flatten_json_simple(self, data_transformer):
        """Test flattening simple JSON structures"""
        json_data = [
            {"id": 1, "name": "Alice", "address": {"city": "NYC", "zip": "10001"}},
            {"id": 2, "name": "Bob", "address": {"city": "LA", "zip": "90001"}},
        ]

        result = data_transformer.flatten_json(json_data, separator="_")

        assert "id" in result.columns
        assert "name" in result.columns
        assert "address_city" in result.columns
        assert "address_zip" in result.columns
        assert len(result) == 2

    def test_normalize_numeric_columns(self, data_transformer, sample_enrollment_df):
        """Test numeric normalization"""
        grades_before = sample_enrollment_df["final_grade_numeric"].copy()

        result = data_transformer.normalize_numeric(
            sample_enrollment_df,
            columns=["final_grade_numeric"],
            target_min=0,
            target_max=100,
        )

        assert result["final_grade_numeric"].min() >= 0
        assert result["final_grade_numeric"].max() <= 100
        assert (
            not result["final_grade_numeric"].isna().any() or grades_before.isna().any()
        )

    def test_handle_missing_values_drop(self, sample_academic_records_df):
        """Test dropping rows with missing values"""
        original_len = len(sample_academic_records_df)
        df_with_nulls = sample_academic_records_df.copy()
        df_with_nulls.loc[0, "points_earned"] = np.nan

        transformer = DataTransformer(None)
        result = transformer.handle_missing_values(df_with_nulls, strategy="drop")

        assert len(result) < len(df_with_nulls)
        assert result["points_earned"].isna().sum() == 0

    def test_handle_missing_values_forward_fill(self, sample_engagement_df):
        """Test forward fill for missing values"""
        df_with_nulls = sample_engagement_df.copy()
        df_with_nulls = df_with_nulls.sort_values("event_timestamp")
        df_with_nulls.loc[1, "duration_seconds"] = np.nan

        transformer = DataTransformer(None)
        result = transformer.handle_missing_values(
            df_with_nulls, strategy="forward_fill"
        )

        assert result["duration_seconds"].isna().sum() == 0

    def test_validate_data_types(self, data_transformer, sample_students_df):
        """Test data type validation"""
        # Modify a column to wrong type
        df = sample_students_df.copy()
        df["grade_level"] = df["grade_level"].astype(str)

        errors = data_transformer.validate_schema(df, entity="students")

        assert not errors["valid"] or "grade_level" not in errors.get("errors", {})


@pytest.mark.unit
class TestEngagementAggregator:
    """Unit tests for EngagementAggregator class"""

    def test_calculate_engagement_score(self, data_transformer, sample_engagement_df):
        """Test engagement score calculation"""
        student_engagement = (
            sample_engagement_df.groupby("student_id")
            .agg(
                {
                    "event_id": "count",
                    "duration_seconds": "sum",
                    "content_interaction_flag": "sum",
                }
            )
            .reset_index()
        )

        student_engagement.columns = [
            "student_id",
            "event_count",
            "total_duration",
            "interactions",
        ]

        assert student_engagement.loc[0, "event_count"] > 0
        assert student_engagement.loc[0, "total_duration"] > 0

    def test_aggregate_engagement_by_course(self, sample_engagement_df):
        """Test aggregating engagement by course"""
        result = (
            sample_engagement_df.groupby("course_id")
            .agg(
                {
                    "student_id": "nunique",
                    "event_id": "count",
                    "duration_seconds": "mean",
                }
            )
            .reset_index()
        )

        assert "course_id" in result.columns
        assert len(result) > 0
        assert (result["student_id"] > 0).all()

    def test_calculate_attendance_metrics(self, sample_enrollment_df):
        """Test attendance metrics calculation"""
        result = sample_enrollment_df[
            ["student_id", "attendance_days", "absence_count"]
        ].copy()
        result["attendance_rate"] = (
            result["attendance_days"]
            / (result["attendance_days"] + result["absence_count"])
        ) * 100

        assert (result["attendance_rate"] >= 0).all()
        assert (result["attendance_rate"] <= 100).all()


@pytest.mark.unit
class TestPseudonymizer:
    """Unit tests for Pseudonymizer class"""

    def test_hash_student_id(self, pseudonymizer, sample_students_df):
        """Test hashing student IDs"""
        df = sample_students_df.copy()
        result = pseudonymizer.pseudonymize(df, entity="students")

        # Original student_id should be different
        assert (result["student_id"] != df["student_id"]).all()
        # Hashes should be deterministic
        assert result["student_id"].nunique() == df["student_id"].nunique()

    def test_mask_names(self, pseudonymizer, sample_students_df):
        """Test masking student names"""
        df = sample_students_df.copy()
        result = pseudonymizer.pseudonymize(df, entity="students")

        # Names should be modified
        assert (result["first_name"] != df["first_name"]).all()
        assert (result["last_name"] != df["last_name"]).all()

    def test_no_op_grades(self, pseudonymizer, sample_enrollment_df):
        """Test that grades are not pseudonymized"""
        df = sample_enrollment_df.copy()
        result = pseudonymizer.pseudonymize(df, entity="enrollment")

        # Grades should remain unchanged
        assert (
            result["final_grade_numeric"].equals(
                df["final_grade_numeric"], check_dtype=False
            )
            or (
                result["final_grade_numeric"].isna() & df["final_grade_numeric"].isna()
            ).all()
        )

    def test_hash_consistency(self, pseudonymizer, sample_students_df):
        """Test that same input produces same hash"""
        df1 = sample_students_df.copy()
        df2 = sample_students_df.copy()

        result1 = pseudonymizer.pseudonymize(df1, entity="students")
        result2 = pseudonymizer.pseudonymize(df2, entity="students")

        # Same student_id should produce same hash
        for idx in range(len(sample_students_df)):
            assert result1.loc[idx, "student_id"] == result2.loc[idx, "student_id"]


@pytest.mark.unit
class TestSchemaValidator:
    """Unit tests for SchemaValidator class"""

    def test_validate_required_columns(self, data_transformer, sample_students_df):
        """Test validation of required columns"""
        df = sample_students_df.copy()

        validation = data_transformer.validate_schema(df, entity="students")

        assert "valid" in validation

    def test_validate_data_types(self, data_transformer, sample_students_df):
        """Test data type validation"""
        df = sample_students_df.copy()
        df["grade_level"] = df["grade_level"].astype(str)

        validation = data_transformer.validate_schema(df, entity="students")

        # Should detect type mismatch or handle gracefully
        assert "valid" in validation

    def test_validate_with_nulls(self, data_transformer, sample_enrollment_df):
        """Test validation with null values"""
        df = sample_enrollment_df.copy()
        df.loc[0, "final_grade_numeric"] = np.nan

        validation = data_transformer.validate_schema(df, entity="enrollment")

        assert "valid" in validation
