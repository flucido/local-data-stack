#!/usr/bin/env python3
"""
Excel Imports dlt Pipeline - Stage 1 Data Ingestion

This pipeline extracts data from Excel files (D&F report, Demographics, RFEP)
and loads them into Stage 1 (Parquet files) following the medallion architecture.

Features:
- Reads Excel files using pandas
- Writes to stage1/reference/excel/ as Parquet
- Handles missing files gracefully
- Supports both individual and batch imports
"""

import os
from typing import Iterator, Dict, Any, List, Optional
from datetime import datetime, date
from pathlib import Path
import dlt
from dlt.sources import DltResource
from dlt.common.pipeline import LoadInfo
import pandas as pd


class ExcelImporter:
    """Import Excel files for Stage 1 landing"""

    def __init__(self):
        self.excel_df_path = os.getenv("EXCEL_DF_REPORT_PATH")
        self.excel_demographic_path = os.getenv("EXCEL_DEMOGRAPHIC_PATH")
        self.excel_rfep_path = os.getenv("EXCEL_RFEP_PATH")

    def read_d_and_f_report(self) -> List[Dict]:
        """Read D&F (Ds, Fs, 504, SPED) report from Excel"""
        if not self.excel_df_path or not os.path.exists(self.excel_df_path):
            print(f"⏭️  D&F report not found at: {self.excel_df_path}")
            return []

        df = pd.read_excel(self.excel_df_path)
        print(f"📊 Loaded D&F report: {len(df)} rows")
        return df.to_dict("records")

    def read_demographic_data(self) -> List[Dict]:
        """Read demographic data from Excel"""
        if not self.excel_demographic_path or not os.path.exists(
            self.excel_demographic_path
        ):
            print(f"⏭️  Demographic data not found at: {self.excel_demographic_path}")
            return []

        df = pd.read_excel(self.excel_demographic_path)
        print(f"📊 Loaded demographic data: {len(df)} rows")
        return df.to_dict("records")

    def read_rfep_data(self) -> List[Dict]:
        """Read RFEP data (note: may be PNG, needs special handling)"""
        if not self.excel_rfep_path:
            print("⏭️  RFEP data path not configured")
            return []

        # Check if it's actually an Excel file
        if self.excel_rfep_path.lower().endswith((".xlsx", ".xls")):
            if not os.path.exists(self.excel_rfep_path):
                print(f"⏭️  RFEP data not found at: {self.excel_rfep_path}")
                return []

            df = pd.read_excel(self.excel_rfep_path)
            print(f"📊 Loaded RFEP data: {len(df)} rows")
            return df.to_dict("records")
        else:
            print(
                f"⚠️  RFEP file is not Excel format ({self.excel_rfep_path}), skipping"
            )
            return []


# dlt source definition
@dlt.source(name="excel_imports")
def excel_imports_source() -> List[DltResource]:
    """
    dlt source for Excel file imports

    Reads D&F report, demographic data, and RFEP data from Excel files
    """

    importer = ExcelImporter()

    @dlt.resource(name="raw_d_and_f", write_disposition="replace")
    def d_and_f_report() -> Iterator[Dict[str, Any]]:
        """Extract D&F report data"""
        data = importer.read_d_and_f_report()
        for record in data:
            record["created_at"] = datetime.now().isoformat()
            record["load_date"] = date.today().isoformat()
            yield record

    @dlt.resource(name="raw_demographic", write_disposition="replace")
    def demographic_data() -> Iterator[Dict[str, Any]]:
        """Extract demographic data"""
        data = importer.read_demographic_data()
        for record in data:
            record["created_at"] = datetime.now().isoformat()
            record["load_date"] = date.today().isoformat()
            yield record

    @dlt.resource(name="raw_rfep", write_disposition="replace")
    def rfep_data() -> Iterator[Dict[str, Any]]:
        """Extract RFEP data"""
        data = importer.read_rfep_data()
        for record in data:
            record["created_at"] = datetime.now().isoformat()
            record["load_date"] = date.today().isoformat()
            yield record

    return [d_and_f_report, demographic_data, rfep_data]


def run_excel_imports_pipeline(
    destination_type: str = "filesystem", dataset_name: str = "excel_stage1"
) -> LoadInfo:
    """
    Run the Excel imports dlt pipeline

    Args:
        destination_type: "filesystem" (Parquet) or "duckdb"
        dataset_name: Name for the dataset
    """

    if destination_type == "filesystem":
        stage1_path = os.getenv("STAGE1_PATH", "./oss_framework/data/stage1")

        pipeline = dlt.pipeline(
            pipeline_name="excel_to_stage1",
            destination=dlt.destinations.filesystem(
                bucket_url=f"{stage1_path}/reference/excel"
            ),
            dataset_name=dataset_name,
        )
    else:
        db_path = os.getenv("DUCKDB_DATABASE_PATH", "./oss_framework/data/oea.duckdb")

        pipeline = dlt.pipeline(
            pipeline_name="excel_to_duckdb",
            destination=dlt.destinations.duckdb(database=db_path),
            dataset_name=dataset_name,
        )

    source = excel_imports_source()
    info = pipeline.run(source)

    print(f"\n✅ Excel imports pipeline completed")
    print(f"   Pipeline: {info.pipeline.pipeline_name}")
    print(f"   Destination: {destination_type}")
    print(f"   Dataset: {dataset_name}")
    print(f"   Loads: {len(info.loads_ids)}")

    return info


if __name__ == "__main__":
    import sys

    destination = sys.argv[1] if len(sys.argv) > 1 else "filesystem"

    run_excel_imports_pipeline(destination_type=destination)
