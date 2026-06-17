#!/usr/bin/env python3
"""
SIS dlt Pipeline — Stage 1 Data Ingestion.

This pipeline uses a pluggable SIS connector (configured via the SIS_CONNECTOR
environment variable) to extract student data and load it into Stage 1
(Parquet files) following the medallion architecture.

Features:
- Test mode: Uses synthetic data when real credentials unavailable
- Production mode: Connects to the configured SIS API
- Incremental loading: Tracks state for efficient updates
- Parquet output: Writes to stage1/transactional/
"""

import os
from collections.abc import Iterator
from datetime import datetime
from typing import Any, Dict, List, Optional

import dlt
from dlt.common.pipeline import LoadInfo
from dlt.sources import DltResource

from oss_framework.connectors import get_sis_connector


# dlt source definition
@dlt.source(name="aeries")
def aeries_source(
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    test_mode: Optional[bool] = None,
) -> List[DltResource]:
    """
    dlt source for Aeries SIS data

    Args:
        base_url: Aeries API base URL
        api_key: Aeries API certificate/key
        test_mode: Force test mode (synthetic data)
    """

    if test_mode is None:
        test_mode = not api_key

    client = get_sis_connector(
        name="aeries",
        base_url=base_url or "",
        api_key=api_key or "",
        test_mode=test_mode,
    )

    @dlt.resource(name="raw_students", write_disposition="replace")
    def students() -> Iterator[Dict[str, Any]]:
        """Extract student data"""
        data = client.get_students()
        for record in data:
            record["created_at"] = datetime.now().isoformat()
            record["updated_at"] = datetime.now().isoformat()
            yield record

    @dlt.resource(name="raw_attendance", write_disposition="append")
    def attendance() -> Iterator[Dict[str, Any]]:
        """Extract attendance data"""
        data = client.get_attendance()
        for record in data:
            record["created_at"] = datetime.now().isoformat()
            yield record

    @dlt.resource(name="raw_academic_records", write_disposition="append")
    def academic_records() -> Iterator[Dict[str, Any]]:
        """Extract grade/academic records"""
        data = client.get_grades()
        for record in data:
            record["created_at"] = datetime.now().isoformat()
            yield record

    @dlt.resource(name="raw_discipline", write_disposition="append")
    def discipline() -> Iterator[Dict[str, Any]]:
        """Extract discipline incidents"""
        data = client.get_discipline()
        for record in data:
            record["created_at"] = datetime.now().isoformat()
            yield record

    @dlt.resource(name="raw_enrollment", write_disposition="replace")
    def enrollment() -> Iterator[Dict[str, Any]]:
        """Extract enrollment data"""
        data = client.get_enrollment()
        for record in data:
            record["created_at"] = datetime.now().isoformat()
            yield record

    return [students, attendance, academic_records, discipline, enrollment]


def run_aeries_pipeline(
    destination_type: str = "filesystem",
    dataset_name: str = "aeries_stage1",
    test_mode: Optional[bool] = None,
) -> LoadInfo:
    """
    Run the Aeries dlt pipeline

    Args:
        destination_type: "filesystem" (Parquet) or "duckdb"
        dataset_name: Name for the dataset
        test_mode: Force test mode with synthetic data
    """

    api_key = os.getenv("AERIES_API_KEY")
    base_url = os.getenv("AERIES_API_URL")

    if test_mode is None:
        test_mode = not api_key

    if test_mode:
        print("🧪 Running in TEST MODE with synthetic data")
    else:
        print("🔌 Running in PRODUCTION MODE with real Aeries API")

    if destination_type == "filesystem":
        stage1_path = os.getenv("STAGE1_PATH", "./oss_framework/data/stage1")

        pipeline = dlt.pipeline(
            pipeline_name="aeries_to_stage1",
            destination=dlt.destinations.filesystem(
                bucket_url=f"{stage1_path}/transactional/aeries"
            ),
            dataset_name=dataset_name,
        )
    else:
        db_path = os.getenv("DUCKDB_DATABASE_PATH", "./oss_framework/data/analytics.duckdb")

        pipeline = dlt.pipeline(
            pipeline_name="aeries_to_duckdb",
            destination=dlt.destinations.duckdb(database=db_path),
            dataset_name=dataset_name,
        )

    source = aeries_source(base_url=base_url or "", api_key=api_key or "", test_mode=test_mode)
    info = pipeline.run(source)

    print("\n✅ Pipeline completed successfully")
    print(f"   Pipeline: {info.pipeline.pipeline_name}")
    print(f"   Destination: {destination_type}")
    print(f"   Dataset: {dataset_name}")
    print(f"   Loads: {len(info.loads_ids)}")

    return info


if __name__ == "__main__":
    import sys

    destination = sys.argv[1] if len(sys.argv) > 1 else "filesystem"
    test_mode = "--test" in sys.argv or "--test-mode" in sys.argv

    run_aeries_pipeline(destination_type=destination, test_mode=test_mode)
