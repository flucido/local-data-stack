"""
OSS Framework: Batch Processing Utilities

Supports three batch processing modes:
- Delta: Incremental (only changed records)
- Additive: Append-only (new events)
- Snapshot: Full replacement
"""

import pandas as pd
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

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
        existing_data: Optional[pd.DataFrame] = None,
        key_columns: List[str] = None,
    ) -> pd.DataFrame:
        """
        Process batch according to configured mode

        Args:
            new_data: New data to process
            existing_data: Existing data (required for delta and additive modes)
            key_columns: Columns to use for merge key (required for delta mode)

        Returns:
            Processed data ready for database load
        """
        if self.mode == "delta":
            return self._delta_merge(new_data, existing_data, key_columns)
        elif self.mode == "additive":
            return self._additive_append(new_data, existing_data)
        else:  # snapshot
            return self._snapshot_replace(new_data)

    @staticmethod
    def _delta_merge(
        new_data: pd.DataFrame, existing_data: pd.DataFrame, key_columns: List[str]
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

        # Find records to update
        merge_df = new_data.merge(
            existing_data[key_columns], on=key_columns, how="left", indicator=True
        )

        # Split into new and updated
        new_records = new_data[merge_df["_merge"] == "left_only"]

        # Find existing records not in new batch
        existing_not_in_new = existing_data.merge(
            new_data[key_columns], on=key_columns, how="left", indicator=True
        )
        existing_not_in_new = existing_data[
            existing_not_in_new["_merge"] == "left_only"
        ]

        # Combine
        result = pd.concat(
            [
                existing_not_in_new,
                new_records,
                new_data[
                    new_data[key_columns].isin(existing_data[key_columns]).all(axis=1)
                ],
            ],
            ignore_index=True,
        )

        return result.drop_duplicates(subset=key_columns, keep="last")

    @staticmethod
    def _additive_append(
        new_data: pd.DataFrame, existing_data: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        Additive append: Only add new records (append-only log)

        Args:
            new_data: New events/records
            existing_data: Existing data (optional for validation)

        Returns:
            New records to append
        """
        # For additive mode, simply return new data
        # Caller is responsible for appending to table
        return new_data

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
        new_count: int, historical_counts: List[int], threshold_pct: float = 0.5
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
    def check_null_percentage(
        df: pd.DataFrame, threshold_pct: float = 0.1
    ) -> Dict[str, float]:
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
    def check_duplicates(df: pd.DataFrame, key_columns: List[str]) -> int:
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
    def check_schema_conformance(
        df: pd.DataFrame, expected_columns: List[str]
    ) -> Dict[str, Any]:
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
