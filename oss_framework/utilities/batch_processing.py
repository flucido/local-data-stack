"""
OSS Framework: Batch Processing Utilities

Supports three batch processing modes:
- Delta: Incremental (only changed records)
- Additive: Append-only (new events)
- Snapshot: Full replacement
"""

import logging
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


class BatchProcessor:
    """Handles different batch processing modes"""

    def __init__(self, mode: str = "delta"):
        """
        Initialize batch processor

        Args:
            mode: 'delta', 'additive', or 'snapshot'
        """
        if mode not in ["delta", "additive", "snapshot"]:
            raise ValueError(
                f"Invalid batch mode: {mode}. Must be 'delta', 'additive', or 'snapshot'"
            )
        self.mode = mode

    def process(
        self,
        new_data: pd.DataFrame,
        existing_data: pd.DataFrame | None = None,
        key_columns: list[str] = None,
        batch_mode: str | None = None,
    ) -> pd.DataFrame:
        """
        Process batch according to configured mode

        Args:
            new_data: New data to process
            existing_data: Existing data (required for delta and additive modes)
            key_columns: Columns to use for merge key (required for delta mode)
            batch_mode: Override the instance's default mode for this call

        Returns:
            Processed data ready for database load
        """
        mode = batch_mode or self.mode
        if mode == "delta":
            return self._delta_merge(new_data, existing_data, key_columns)
        elif mode == "additive":
            return self._additive_append(new_data, existing_data)
        else:  # snapshot
            return self._snapshot_replace(new_data)

    @staticmethod
    def deduplicate(df: pd.DataFrame, subset: list[str]) -> pd.DataFrame:
        """Remove duplicate rows based on subset columns."""
        return df.drop_duplicates(subset=subset)

    @staticmethod
    def check_quality(df: pd.DataFrame, entity: str = "") -> dict[str, Any]:
        """Run data quality checks and return a report."""
        report: dict[str, Any] = {
            "entity": entity,
            "checks": {},
            "valid": True,
            "quality_issues": [],
        }
        null_pct = DataQualityChecker.check_null_percentage(df)
        report["checks"]["null_percentage"] = null_pct
        dupes = DataQualityChecker.check_duplicates(df, df.columns.tolist())
        report["checks"]["duplicate_count"] = dupes
        return report

    @staticmethod
    def _delta_merge(
        new_data: pd.DataFrame, existing_data: pd.DataFrame, key_columns: list[str]
    ) -> pd.DataFrame:
        """
        Delta merge: Keep existing, upsert new, remove deleted

        Args:
            new_data: New data batch
            existing_data: Existing data in system
            key_columns: Columns that form unique key

        Returns:
            Merged data (existing + new + updates)
        """
        if key_columns is None or not key_columns:
            raise ValueError("key_columns required for delta merge")

        # Vectorised upsert via MultiIndex membership (index-alignment safe):
        # keep existing rows whose key is NOT in the new batch, then append
        # the entire new batch (inserts + updates win via keep="last").
        new_keys = pd.MultiIndex.from_frame(new_data[key_columns])
        existing_keys = pd.MultiIndex.from_frame(existing_data[key_columns])
        keep_mask = ~existing_keys.isin(new_keys)

        result = pd.concat(
            [existing_data.loc[keep_mask], new_data],
            ignore_index=True,
        )

        return result.drop_duplicates(subset=key_columns, keep="last")

    @staticmethod
    def _additive_append(
        new_data: pd.DataFrame, existing_data: pd.DataFrame | None = None
    ) -> pd.DataFrame:
        """
        Additive append: Only add new records (append-only log)

        Args:
            new_data: New events/records
            existing_data: Existing data (optional)

        Returns:
            Existing records followed by the new records (append-only)
        """
        # Append-only semantics: never modify or drop existing rows.
        if existing_data is None or existing_data.empty:
            return new_data
        return pd.concat([existing_data, new_data], ignore_index=True)

    @staticmethod
    def _snapshot_replace(new_data: pd.DataFrame) -> pd.DataFrame:
        """
        Snapshot replace: Full dataset replacement

        Args:
            new_data: Complete dataset snapshot

        Returns:
            Data ready for TRUNCATE + LOAD
        """
        return new_data


class DataQualityChecker:
    """Validates data quality during batch processing"""

    @staticmethod
    def check_row_count_anomaly(
        new_count: int, historical_counts: list[int], threshold_pct: float = 0.5
    ) -> bool:
        """
        Detect abnormal row count changes

        Args:
            new_count: Row count in new batch
            historical_counts: Recent historical row counts
            threshold_pct: Alert if change exceeds this percentage

        Returns:
            True if anomaly detected
        """
        if not historical_counts:
            return False

        avg_count = sum(historical_counts) / len(historical_counts)
        change_pct = abs(new_count - avg_count) / avg_count if avg_count > 0 else 0

        return change_pct > threshold_pct

    @staticmethod
    def check_null_percentage(df: pd.DataFrame, threshold_pct: float = 0.1) -> dict[str, float]:
        """
        Check for excessive nulls per column

        Args:
            df: DataFrame to check
            threshold_pct: Alert if nulls exceed this percentage

        Returns:
            Dictionary of columns exceeding threshold
        """
        problematic = {}

        for col in df.columns:
            null_pct = (df[col].isnull().sum() / len(df)) if len(df) > 0 else 0
            if null_pct > threshold_pct:
                problematic[col] = null_pct

        return problematic

    @staticmethod
    def check_duplicates(df: pd.DataFrame, key_columns: list[str]) -> int:
        """
        Count duplicate records by key

        Args:
            df: DataFrame to check
            key_columns: Columns that form unique key

        Returns:
            Number of duplicate records
        """
        return df.duplicated(subset=key_columns).sum()

    @staticmethod
    def check_schema_conformance(df: pd.DataFrame, expected_columns: list[str]) -> dict[str, Any]:
        """
        Verify DataFrame matches expected schema

        Args:
            df: DataFrame to check
            expected_columns: Expected column names

        Returns:
            Validation report
        """
        actual = set(df.columns)
        expected = set(expected_columns)

        return {
            "valid": actual == expected,
            "missing_columns": expected - actual,
            "extra_columns": actual - expected,
        }
