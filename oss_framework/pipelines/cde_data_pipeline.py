#!/usr/bin/env python3
"""
CDE Data Pipeline - California Department of Education Data Ingestion

This pipeline loads CDE downloadable data files (chronic absenteeism, staff,
assessments, etc.) into DuckDB for downstream dbt transformations.

Features:
- Tab-delimited text file processing
- Handles data suppression symbols (*) as NULL
- Multi-year historical data loading
- Demographic disaggregation support
- Writes to DuckDB for dbt consumption
"""

import os
from typing import Iterator, Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path
import dlt
from dlt.sources import DltResource
from dlt.common.pipeline import LoadInfo
import csv


class CDEDataLoader:
    """Loader for California Department of Education data files"""

    def __init__(self, data_dir: str = ""):
        self.data_dir = data_dir or os.getenv(
            "CDE_DATA_PATH",
            "oss_framework/data/raw",
        )

    def _read_tsv_file(
        self, file_path: str, encoding: str = "utf-8"
    ) -> Iterator[Dict[str, Any]]:
        """
        Read tab-delimited CDE file and yield rows as dictionaries

        Args:
            file_path: Path to .txt file
            encoding: File encoding (default: ascii)

        Yields:
            Dictionary for each row with column names as keys
        """
        try:
            with open(file_path, "r", encoding=encoding) as f:
                reader = csv.DictReader(f, delimiter="\t")
                for row in reader:
                    # Convert suppression symbols to None
                    processed_row = {}
                    for key, value in row.items():
                        if value == "*":
                            processed_row[key] = None
                        elif value == "":
                            processed_row[key] = None
                        else:
                            processed_row[key] = value

                    yield processed_row
        except FileNotFoundError:
            print(f"⚠️  File not found: {file_path}")
            return
        except Exception as e:
            print(f"❌ Error reading {file_path}: {e}")
            return

    def load_chronic_absenteeism(
        self, academic_year: Optional[str] = None
    ) -> Iterator[Dict[str, Any]]:
        """
        Load chronic absenteeism data

        Args:
            academic_year: Academic year (e.g., "2425" for 2024-25),
                          or None to load all available years

        Yields:
            Chronic absenteeism records
        """
        absenteeism_dir = Path(self.data_dir) / "absenteeism"

        if academic_year:
            files = [f"chronicabsenteeism{academic_year}.txt"]
        else:
            # Load all available years (excluding 2019-20 - COVID)
            files = [
                "chronicabsenteeism17.txt",
                "chronicabsenteeism18.txt",
                "chronicabsenteeism19.txt",
                "chronicabsenteeism21.txt",
                "chronicabsenteeism22.txt",
                "chronicabsenteeism23.txt",
                "chronicabsenteeism24.txt",
                "chronicabsenteeism25.txt",
            ]

        for filename in files:
            file_path = absenteeism_dir / filename
            if not file_path.exists():
                print(f"⚠️  Skipping {filename} - file not found")
                continue

            print(f"📂 Loading {filename}...")
            row_count = 0

            for row in self._read_tsv_file(str(file_path)):
                row["_loaded_at"] = datetime.now().isoformat()
                row["_source_file"] = filename
                yield row
                row_count += 1

            print(f"   ✓ Loaded {row_count:,} rows from {filename}")

    def load_public_schools(self) -> Iterator[Dict[str, Any]]:
        """
        Load CDE Public Schools Directory

        Note: This is handled by stg_cde__schools.sql in dbt.
        This method exists for pipeline completeness but may not be needed.

        Yields:
            School directory records
        """
        schools_file = Path(self.data_dir) / "public_schools" / "pubschls.txt"

        if not schools_file.exists():
            print(f"⚠️  Public schools file not found: {schools_file}")
            return

        print(f"📂 Loading public schools directory...")
        row_count = 0

        for row in self._read_tsv_file(str(schools_file)):
            row["_loaded_at"] = datetime.now().isoformat()
            yield row
            row_count += 1

        print(f"   ✓ Loaded {row_count:,} schools")


@dlt.source(name="cde")
def cde_source(
    data_dir: Optional[str] = None, academic_year: Optional[str] = None
) -> List[DltResource]:
    """
    dlt source for California Department of Education data

    Args:
        data_dir: Path to CDE data directory
        academic_year: Specific year to load (e.g., "2425"), or None for all
    """

    loader = CDEDataLoader(data_dir=data_dir or "")

    @dlt.resource(name="cde_chronic_absenteeism", write_disposition="replace")
    def chronic_absenteeism() -> Iterator[Dict[str, Any]]:
        """Extract chronic absenteeism data"""
        yield from loader.load_chronic_absenteeism(academic_year=academic_year)

    return [chronic_absenteeism]


def run_cde_pipeline(
    destination_type: str = "duckdb",
    dataset_name: str = "cde_raw",
    data_dir: Optional[str] = None,
    academic_year: Optional[str] = None,
) -> LoadInfo:
    """
    Run the CDE dlt pipeline

    Args:
        destination_type: "duckdb" (default) or "filesystem"
        dataset_name: Name for the dataset
        data_dir: Path to CDE raw data directory
        academic_year: Specific year to load (e.g., "2425"), or None for all

    Returns:
        LoadInfo object with pipeline execution details
    """

    if academic_year:
        print(f"📊 Loading CDE data for academic year 20{academic_year}")
    else:
        print(f"📊 Loading ALL available CDE data (multi-year)")

    if destination_type == "duckdb":
        db_path = os.getenv("DUCKDB_DATABASE_PATH", "data/oea.duckdb")
        db_path = os.path.abspath(db_path)

        pipeline = dlt.pipeline(
            pipeline_name="cde_to_duckdb",
            destination=dlt.destinations.duckdb(db_path),
            dataset_name=dataset_name,
        )
    else:
        stage1_path = os.getenv("STAGE1_PATH", "./oss_framework/data/stage1")

        pipeline = dlt.pipeline(
            pipeline_name="cde_to_stage1",
            destination=dlt.destinations.filesystem(
                bucket_url=f"{stage1_path}/transactional/cde"
            ),
            dataset_name=dataset_name,
        )

    source = cde_source(data_dir=data_dir, academic_year=academic_year)
    info = pipeline.run(source)

    print(f"\n✅ Pipeline completed successfully")
    print(f"   Pipeline: {info.pipeline.pipeline_name}")
    print(f"   Destination: {destination_type}")
    print(f"   Dataset: {dataset_name}")
    print(f"   Loads: {len(info.loads_ids)}")

    return info


if __name__ == "__main__":
    import sys

    destination = "duckdb"
    academic_year = None
    data_dir = None

    # Parse command line arguments
    for arg in sys.argv[1:]:
        if arg.startswith("--year="):
            academic_year = arg.split("=")[1]
        elif arg.startswith("--data-dir="):
            data_dir = arg.split("=")[1]
        elif arg == "--filesystem":
            destination = "filesystem"

    run_cde_pipeline(
        destination_type=destination, data_dir=data_dir, academic_year=academic_year
    )
