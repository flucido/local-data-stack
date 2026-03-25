#!/usr/bin/env python3
"""
Stage 1 Ingestion Orchestrator

Runs all Stage 1 data ingestion pipelines:
- Aeries SIS data (students, attendance, grades, discipline, enrollment)
- Excel imports (D&F report, demographic data, RFEP)

Writes all data to Parquet files in stage1/ following medallion architecture.
"""

import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from aeries_dlt_pipeline import run_aeries_pipeline
from excel_imports_dlt_pipeline import run_excel_imports_pipeline


def run_stage1_ingestion():
    """Execute all Stage 1 ingestion pipelines"""

    print("=" * 60)
    print("STAGE 1 DATA INGESTION - Medallion Architecture")
    print("=" * 60)
    print(f"Started: {datetime.now().isoformat()}")
    print()

    results = {}
    start_time = datetime.now()

    try:
        print("\n📡 Step 1: Aeries SIS Data Ingestion")
        print("-" * 60)
        aeries_info = run_aeries_pipeline(destination_type="filesystem", test_mode=None)
        results["aeries"] = {
            "status": "success",
            "loads": len(aeries_info.loads_ids),
            "pipeline": aeries_info.pipeline.pipeline_name,
        }
        print("✅ Aeries data ingestion completed")

    except Exception as e:
        print(f"❌ Aeries ingestion failed: {e}")
        results["aeries"] = {"status": "failed", "error": str(e)}

    try:
        print("\n📊 Step 2: Excel Imports")
        print("-" * 60)
        excel_info = run_excel_imports_pipeline(destination_type="filesystem")
        results["excel"] = {
            "status": "success",
            "loads": len(excel_info.loads_ids),
            "pipeline": excel_info.pipeline.pipeline_name,
        }
        print("✅ Excel imports completed")

    except Exception as e:
        print(f"❌ Excel imports failed: {e}")
        results["excel"] = {"status": "failed", "error": str(e)}

    duration = (datetime.now() - start_time).total_seconds()

    print("\n" + "=" * 60)
    print("STAGE 1 INGESTION SUMMARY")
    print("=" * 60)
    print(f"Duration: {duration:.1f} seconds")
    print()

    for pipeline_name, result in results.items():
        status_icon = "✅" if result["status"] == "success" else "❌"
        print(f"{status_icon} {pipeline_name.upper()}: {result['status']}")
        if result["status"] == "success":
            print(f"   Loads: {result.get('loads', 0)}")
        else:
            print(f"   Error: {result.get('error', 'Unknown')}")

    all_success = all(r["status"] == "success" for r in results.values())

    print()
    if all_success:
        print("🎉 All Stage 1 ingestion pipelines completed successfully!")
        print()
        print("Next steps:")
        print("  1. Verify Parquet files:")
        print(
            "     find oss_framework/data/stage1 -name '*.parquet' -type f | head -20"
        )
        print("  2. Run dbt to create DuckDB views:")
        print("     cd oss_framework/dbt && dbt build")
        print()
    else:
        print("⚠️  Some pipelines failed. Check errors above.")
        sys.exit(1)


if __name__ == "__main__":
    run_stage1_ingestion()
