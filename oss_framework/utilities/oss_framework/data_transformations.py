"""
OSS Framework: Data Transformation Utilities

This module provides common data transformation functions for education analytics:
- JSON flattening
- Data aggregation
- Pseudonymization
- Schema validation
- Feature engineering
"""

import json
import hashlib
import pandas as pd
from typing import Any, Dict, List, Optional, Tuple, Union
import logging

logger = logging.getLogger(__name__)


class DataTransformer:
    """Core data transformation utilities"""

    def __init__(self, metadata_manager=None):
        self.metadata_manager = metadata_manager

    @staticmethod
    def handle_missing_values(df: pd.DataFrame, strategy: str = "drop") -> pd.DataFrame:
        """Handle missing values in a DataFrame.

        Args:
            df: Input DataFrame.
            strategy: 'drop' to remove rows with any nulls,
                      'forward_fill' to forward-fill nulls.

        Returns:
            DataFrame with missing values handled.
        """
        if strategy == "drop":
            return df.dropna()
        elif strategy == "forward_fill":
            return df.ffill()
        else:
            raise ValueError(f"Unknown missing-value strategy: {strategy}")

    @staticmethod
    def normalize_numeric(
        df: pd.DataFrame,
        columns: Optional[List[str]] = None,
        target_min: float = 0,
        target_max: float = 1,
    ) -> pd.DataFrame:
        """Min-max normalize numeric columns."""
        result = df.copy()
        cols = columns or result.select_dtypes(include=[np.number]).columns.tolist()
        for col in cols:
            col_min = result[col].min()
            col_max = result[col].max()
            if col_max > col_min:
                result[col] = (result[col] - col_min) / (col_max - col_min)
                result[col] = result[col] * (target_max - target_min) + target_min
            else:
                result[col] = target_min
        return result

    def validate_schema(self, df: pd.DataFrame, entity: str = "") -> Dict[str, Any]:
        """Validate DataFrame schema against metadata. Delegates to SchemaValidator."""
        if self.metadata_manager is None:
            return {"valid": True, "errors": {}}
        validator = SchemaValidator()
        return validator.validate_schema(df, self.metadata_manager.metadata, entity)

    @staticmethod
    def flatten_json(
        json_obj: Union[Dict[str, Any], List[Dict[str, Any]]],
        parent_key: str = "",
        sep: str = "_",
    ) -> Union[Dict[str, Any], "pd.DataFrame"]:
        """Flatten nested JSON to single-level dict.

        Accepts a single dict or a list of dicts."""
        if isinstance(json_obj, list):
            return pd.DataFrame([
                DataTransformer.flatten_json(item, parent_key, sep)
                for item in json_obj
            ])
        items: List[tuple] = []
        for k, v in json_obj.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(
                    DataTransformer.flatten_json(v, new_key, sep=sep).items()
                )
            else:
                items.append((new_key, v))
        return dict(items)

    @staticmethod
    def flatten_dataframe(df: pd.DataFrame, json_columns: List[str]) -> pd.DataFrame:
        """
        Flatten JSON columns in a DataFrame

        Args:
            df: Input DataFrame
            json_columns: List of column names containing JSON strings

        Returns:
            DataFrame with flattened JSON columns
        """
        df_copy = df.copy()

        for col in json_columns:
            if col not in df_copy.columns:
                logger.warning(f"Column {col} not found in DataFrame")
                continue

            # Parse JSON strings to objects
            json_data = df_copy[col].apply(
                lambda x: json.loads(x) if isinstance(x, str) else x
            )

            # Flatten each JSON object
            flattened = json_data.apply(DataTransformer.flatten_json)

            # Convert to DataFrame
            flattened_df = pd.json_normalize(flattened)

            # Add prefix to flattened columns
            flattened_df.columns = [f"{col}_{c}" for c in flattened_df.columns]

            # Combine with original DataFrame
            df_copy = pd.concat([df_copy, flattened_df], axis=1)
            df_copy = df_copy.drop(col, axis=1)

        return df_copy

    @staticmethod
    def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
        """
        Normalize DataFrame column names to snake_case

        Example: 'StudentID' -> 'student_id', 'First Name' -> 'first_name'

        Args:
            df: Input DataFrame

        Returns:
            DataFrame with normalized column names
        """
        df_copy = df.copy()
        df_copy.columns = [
            col.lower().replace(" ", "_").replace("-", "_").replace(".", "_")
            for col in df_copy.columns
        ]
        return df_copy


class EngagementAggregator:
    """Education-specific aggregation utilities"""

    @staticmethod
    def aggregate_engagement(
        df: pd.DataFrame,
        student_col: str = "student_id",
        timestamp_col: str = "event_timestamp",
        period: str = "month",
    ) -> pd.DataFrame:
        """
        Aggregate engagement events by student and time period

        Args:
            df: DataFrame with engagement events
            student_col: Column name for student identifier
            timestamp_col: Column name for event timestamp
            period: Time period ('day', 'week', 'month', 'quarter', 'year')

        Returns:
            Aggregated engagement metrics
        """
        df_copy = df.copy()

        # Convert timestamp to datetime if not already
        if not pd.api.types.is_datetime64_any_dtype(df_copy[timestamp_col]):
            df_copy[timestamp_col] = pd.to_datetime(df_copy[timestamp_col])

        # Create period column
        period_map = {
            "day": "%Y-%m-%d",
            "week": "%Y-W%U",
            "month": "%Y-%m",
            "quarter": "%Y-Q%q",
            "year": "%Y",
        }

        if period not in period_map:
            raise ValueError(f"Period must be one of {list(period_map.keys())}")

        df_copy["period"] = df_copy[timestamp_col].dt.strftime(period_map[period])

        # Aggregate
        agg_dict = {
            "event_id": "count",  # Number of events
            "duration_minutes": ["sum", "mean"]
            if "duration_minutes" in df.columns
            else "count",
        }

        result = (
            df_copy.groupby([student_col, "period"])
            .agg(
                event_count=("event_id", "count"),
                avg_duration_minutes=("duration_minutes", "mean")
                if "duration_minutes" in df.columns
                else "count",
            )
            .reset_index()
        )

        return result

    @staticmethod
    def calculate_attendance_rate(
        attendance_df: pd.DataFrame,
        student_col: str = "student_id",
        present_col: str = "is_present",
        date_col: str = "date",
    ) -> pd.DataFrame:
        """
        Calculate attendance rate per student per period

        Args:
            attendance_df: DataFrame with attendance records
            student_col: Student identifier column
            present_col: Boolean column indicating presence
            date_col: Date column for grouping

        Returns:
            DataFrame with attendance rates
        """
        if not pd.api.types.is_datetime64_any_dtype(attendance_df[date_col]):
            attendance_df = attendance_df.copy()
            attendance_df[date_col] = pd.to_datetime(attendance_df[date_col])

        result = (
            attendance_df.groupby(student_col)
            .agg(
                total_days=("date", "nunique"),
                days_present=(present_col, "sum"),
                days_absent=(present_col, lambda x: (~x).sum()),
            )
            .reset_index()
        )

        result["attendance_rate"] = (
            result["days_present"] / result["total_days"]
        ).round(3)
        result["chronically_absent"] = (
            result["attendance_rate"] < 0.9
        )  # <90% attendance

        return result

    @staticmethod
    def calculate_course_completion(
        df: pd.DataFrame,
        student_col: str = "student_id",
        course_col: str = "course_id",
        completed_col: str = "is_completed",
    ) -> pd.DataFrame:
        """
        Calculate course completion metrics per student

        Args:
            df: Course enrollment DataFrame
            student_col: Student identifier column
            course_col: Course identifier column
            completed_col: Boolean column indicating completion

        Returns:
            DataFrame with completion rates
        """
        result = (
            df.groupby(student_col)
            .agg(
                total_courses=(course_col, "nunique"),
                completed_courses=(completed_col, "sum"),
            )
            .reset_index()
        )

        result["completion_rate"] = (
            result["completed_courses"] / result["total_courses"]
        ).round(3)
        result["courses_in_progress"] = (
            result["total_courses"] - result["completed_courses"]
        )

        return result


class Pseudonymizer:
    """Privacy-preserving pseudonymization utilities"""

    def __init__(self, salt: Optional[str] = None):
        """
        Initialize pseudonymizer

        Args:
            salt: Optional salt for hashing (for consistency across runs)
        """
        self.salt = salt or "default_oss_framework_salt"

    def pseudonymize(self, df: pd.DataFrame, entity: str = "") -> pd.DataFrame:
        """Pseudonymize a DataFrame with auto-detected rules from column names.

        Entity-aware defaults:
        - student_id, permanent_id → hash (in-place, preserves column name)
        - first_name, last_name, address_* → mask
        - grade_level, final_grade*, gpa* → no-op
        """
        df_pseudo = df.copy()
        for col in df.columns:
            col_lower = col.lower()
            if col_lower in ("student_id", "permanent_id", "student_id_raw", "ssn"):
                df_pseudo[col] = df_pseudo[col].apply(
                    lambda v: self.hash_value(str(v))
                )
            elif any(
                name in col_lower
                for name in ("first_name", "last_name", "address", "phone", "email")
            ):
                df_pseudo[col] = df_pseudo[col].apply(
                    lambda v: self.mask_value(str(v))
                )
        return df_pseudo

    def hash_value(self, value: str, length: int = 16) -> str:
        """
        Hash a value using SHA-256

        Args:
            value: Value to hash
            length: Length of hash output (up to 64)

        Returns:
            Hashed value
        """
        value_str = str(value)
        hash_obj = hashlib.sha256((value_str + self.salt).encode())
        return hash_obj.hexdigest()[:length]

    def mask_value(
        self, value: str, mask_char: str = "*", visible_chars: int = 0
    ) -> str:
        """
        Mask a value (irreversible)

        Args:
            value: Value to mask
            mask_char: Character to use for masking
            visible_chars: Number of characters to keep visible at start

        Returns:
            Masked value
        """
        value_str = str(value)
        if visible_chars > 0:
            return value_str[:visible_chars] + mask_char * (
                len(value_str) - visible_chars
            )
        return mask_char * len(value_str)

    def pseudonymize_dataframe(
        self, df: pd.DataFrame, rules: Dict[str, str]
    ) -> Tuple[pd.DataFrame, Dict[str, pd.DataFrame]]:
        """
        Apply pseudonymization rules to DataFrame

        Args:
            df: Input DataFrame
            rules: Dictionary mapping column names to pseudonymization rules
                  {'student_id': 'hash', 'first_name': 'mask', 'grade_level': 'no-op'}

        Returns:
            Tuple of (pseudonymized DataFrame, lookup tables for hashes)
        """
        df_pseudo = df.copy()
        lookup_tables = {}

        for col, rule in rules.items():
            if col not in df_pseudo.columns:
                logger.warning(f"Column {col} not found in DataFrame, skipping")
                continue

            if rule == "hash":
                # Create lookup table
                unique_values = df_pseudo[col].unique()
                lookup_df = pd.DataFrame(
                    {
                        "original_value": unique_values,
                        "hashed_value": [self.hash_value(v) for v in unique_values],
                    }
                )
                lookup_tables[col] = lookup_df

                # Apply hash
                df_pseudo[f"{col}_hashed"] = df_pseudo[col].apply(self.hash_value)
                df_pseudo = df_pseudo.drop(col, axis=1)

            elif rule == "mask":
                # Irreversible masking
                df_pseudo[col] = df_pseudo[col].apply(self.mask_value)

            elif rule == "no-op":
                # Keep as-is
                pass
            else:
                logger.warning(f"Unknown pseudonymization rule: {rule}")

        return df_pseudo, lookup_tables


class SchemaValidator:
    """Data schema validation utilities"""

    @staticmethod
    def load_metadata_schema(csv_path: str) -> pd.DataFrame:
        """
        Load metadata schema from CSV file

        Expected format:
            Entity,Attribute,DataType,Pseudonymization,Description
            students,student_id,VARCHAR,hash,Student ID
            students,grade_level,INT,no-op,Grade level

        Args:
            csv_path: Path to metadata CSV file

        Returns:
            DataFrame with schema metadata
        """
        return pd.read_csv(csv_path)

    @staticmethod
    def validate_schema(
        df: pd.DataFrame, metadata: pd.DataFrame, entity_name: str
    ) -> Dict[str, Any]:
        """
        Validate DataFrame against metadata schema

        Args:
            df: DataFrame to validate
            metadata: Metadata schema (from load_metadata_schema)
            entity_name: Name of entity being validated

        Returns:
            Validation report with issues and warnings
        """
        report = {"valid": True, "entity": entity_name, "issues": [], "warnings": []}

        # Filter metadata for this entity
        entity_metadata = metadata[metadata["Entity"] == entity_name]

        if entity_metadata.empty:
            report["warnings"].append(f"No metadata found for entity: {entity_name}")
            return report

        # Check for missing columns
        required_columns = set(entity_metadata["Attribute"].values)
        actual_columns = set(df.columns)

        missing_columns = required_columns - actual_columns
        if missing_columns:
            report["valid"] = False
            report["issues"].append(f"Missing columns: {missing_columns}")

        extra_columns = actual_columns - required_columns
        if extra_columns:
            report["warnings"].append(f"Extra columns not in metadata: {extra_columns}")

        # Check for null values in required columns
        for col in required_columns & actual_columns:
            null_count = df[col].isnull().sum()
            if null_count > 0:
                null_pct = (null_count / len(df)) * 100
                report["warnings"].append(
                    f"Column {col} has {null_count} null values ({null_pct:.1f}%)"
                )

        return report

    @staticmethod
    def type_check(
        df: pd.DataFrame, metadata: pd.DataFrame, entity_name: str
    ) -> Dict[str, List[str]]:
        """
        Check DataFrame column types against metadata

        Args:
            df: DataFrame to check
            metadata: Metadata schema
            entity_name: Entity name

        Returns:
            Dictionary of type mismatches
        """
        entity_metadata = metadata[metadata["Entity"] == entity_name]
        mismatches = {}

        type_mapping = {
            "VARCHAR": ["object", "string"],
            "INT": ["int64", "int32"],
            "FLOAT": ["float64", "float32"],
            "DATE": ["datetime64[ns]"],
            "BOOLEAN": ["bool"],
        }

        for _, row in entity_metadata.iterrows():
            col = row["Attribute"]
            expected_type = row["DataType"]

            if col not in df.columns:
                continue

            actual_type = str(df[col].dtype)
            expected_types = type_mapping.get(expected_type, [])

            if not any(t in actual_type for t in expected_types):
                mismatches[col] = {"expected": expected_type, "actual": actual_type}

        return mismatches
