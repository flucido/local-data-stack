#!/usr/bin/env python3
"""
Export DuckDB Analytics Views to Parquet for Rill Dashboards

This script exports analytics views from DuckDB to Parquet files for Rill.
Rill reads these Parquet files via SQL models (SELECT * FROM read_parquet(...)).

Usage:
    python scripts/export_to_rill.py                    # Export all views
    python scripts/export_to_rill.py --view chronic     # Export specific view
    python scripts/export_to_rill.py --dry-run          # Preview without exporting

Architecture:
    DuckDB Analytics Views → Parquet Files → Rill SQL Models → Rill Dashboards
"""

from __future__ import annotations

import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
DUCKDB_PATH = PROJECT_ROOT / "oss_framework" / "data" / "oea.duckdb"
RILL_DATA_DIR = PROJECT_ROOT / "rill_project" / "data"

# Analytics views to export
# Format: {view_name: output_parquet_filename}
ANALYTICS_VIEWS = {
    "main_analytics.v_chronic_absenteeism_risk": "chronic_absenteeism_risk.parquet",
    "main_analytics.v_equity_outcomes_by_demographics": "equity_outcomes_by_demographics.parquet",
    "main_analytics.v_class_section_comparison": "class_effectiveness.parquet",
    "main_analytics.v_performance_correlations": "performance_correlations.parquet",
    "main_analytics.v_wellbeing_risk_profiles": "wellbeing_risk_profiles.parquet",
}



def get_partition_columns(view_name: str) -> list[str]:
    """
    Determine optimal partition columns for a view.
    
    Partitioning provides 40-60% query speedup when filtering by partition column.
    Only partition views with school_id (low cardinality, common filter).
    
    Args:
        view_name: Fully qualified view name
    
    Returns:
        List of column names to partition by (empty list if no partitioning)
    """
    # DISABLED: Partitioning creates directories incompatible with dbt COPY FROM
    # Views with school_id dimension benefit from partitioning
    # views_with_school_id = [
    #     "main_analytics.v_chronic_absenteeism_risk",
    #     "main_analytics.v_class_section_comparison",
    #     "main_analytics.v_wellbeing_risk_profiles",
    # ]
    # 
    # if view_name in views_with_school_id:
    #     return ["school_id"]
    
    return []


def export_view_to_parquet(
    con: duckdb.DuckDBPyConnection, view_name: str, output_path: Path, dry_run: bool = False
) -> dict[str, Any]:
    """
    Export a DuckDB view to Parquet file.

    Args:
        con: DuckDB connection
        view_name: Fully qualified view name (e.g., "main_analytics.v_chronic_absenteeism_risk")
        output_path: Path to output Parquet file
        dry_run: If True, preview without writing

    Returns:
        Dictionary with export metadata (row_count, file_size, etc.)
    """
    logger.info(f"Exporting {view_name} → {output_path.name}")

    # Get row count first
    try:
        result = con.execute(f"SELECT COUNT(*) FROM {view_name}").fetchone()
        row_count = result[0] if result else 0
    except Exception as e:
        logger.error(f"Failed to count rows in {view_name}: {e}")
        return {"status": "error", "error": str(e)}

    if row_count == 0:
        logger.warning(f"View {view_name} is empty (0 rows)")
        return {"status": "skipped", "reason": "empty_view", "row_count": 0}

    if dry_run:
        logger.info(f"[DRY RUN] Would export {row_count} rows from {view_name}")
        return {"status": "dry_run", "row_count": row_count}

    # Export to Parquet
    try:
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # When partitioning, DuckDB creates a directory structure
        # Remove existing file/directory to avoid conflicts
        import shutil
        if output_path.exists():
            if output_path.is_dir():
                shutil.rmtree(output_path)
            else:
                output_path.unlink()

        # Execute COPY TO command
        # Execute COPY TO command with partitioning optimization
        # Partition by school_id for 40-60% faster queries when filtering by school
        # See: DuckDB partitioning docs and Definite.app case study
        partition_cols = get_partition_columns(view_name)
        partition_clause = f", PARTITION_BY ({', '.join(partition_cols)})" if partition_cols else ""
        
        copy_sql = f"""
        COPY (SELECT * FROM {view_name})
        TO '{output_path}'
        (FORMAT PARQUET, COMPRESSION ZSTD{partition_clause})
        """
        con.execute(copy_sql)

        # Get file/directory size
        if output_path.is_dir():
            # Sum all files in partitioned directory
            file_size_mb = sum(f.stat().st_size for f in output_path.rglob('*.parquet')) / (1024 * 1024)
        else:
            file_size_mb = output_path.stat().st_size / (1024 * 1024)

        logger.info(f"✅ Exported {row_count:,} rows ({file_size_mb:.2f} MB) → {output_path.name}")

        return {
            "status": "success",
            "row_count": row_count,
            "file_size_mb": round(file_size_mb, 2),
            "output_path": str(output_path),
        }

    except Exception as e:
        logger.error(f"Failed to export {view_name}: {e}")
        return {"status": "error", "error": str(e)}


def export_all_views(dry_run: bool = False, filter_view: str | None = None) -> dict[str, Any]:
    """
    Export all analytics views to Parquet files for Rill.

    Args:
        dry_run: If True, preview exports without writing files
        filter_view: If provided, only export views containing this string

    Returns:
        Summary dictionary with export results
    """
    logger.info("=" * 80)
    logger.info("DuckDB → Parquet Export for Rill Dashboards")
    logger.info("=" * 80)
    logger.info(f"DuckDB Database: {DUCKDB_PATH}")
    logger.info(f"Rill Data Directory: {RILL_DATA_DIR}")
    logger.info(f"Views to Export: {len(ANALYTICS_VIEWS)}")

    if dry_run:
        logger.info("🔍 DRY RUN MODE - No files will be written")

    if filter_view:
        logger.info(f"📌 Filter: Only exporting views matching '{filter_view}'")

    # Validate DuckDB exists
    if not DUCKDB_PATH.exists():
        error_msg = f"DuckDB database not found: {DUCKDB_PATH}"
        logger.error(error_msg)
        return {"status": "error", "error": error_msg}

    # Connect to DuckDB
    logger.info("\n📊 Connecting to DuckDB...")
    con = duckdb.connect(str(DUCKDB_PATH), read_only=True)

    # Export each view
    results = {}
    start_time = datetime.now()

    logger.info("\n📤 Exporting views...\n")

    for view_name, parquet_filename in ANALYTICS_VIEWS.items():
        # Apply filter if specified
        if filter_view and filter_view.lower() not in view_name.lower():
            logger.debug(f"Skipping {view_name} (doesn't match filter)")
            continue

        output_path = RILL_DATA_DIR / parquet_filename
        result = export_view_to_parquet(con, view_name, output_path, dry_run)
        results[view_name] = result

    con.close()

    # Summary
    duration = (datetime.now() - start_time).total_seconds()

    successful = [k for k, v in results.items() if v.get("status") == "success"]
    errors = [k for k, v in results.items() if v.get("status") == "error"]
    skipped = [k for k, v in results.items() if v.get("status") == "skipped"]

    total_rows = sum(v.get("row_count", 0) for v in results.values())
    total_size_mb = sum(v.get("file_size_mb", 0) for v in results.values())

    logger.info("\n" + "=" * 80)
    logger.info("Export Summary")
    logger.info("=" * 80)
    logger.info(f"Duration: {duration:.2f} seconds")
    logger.info(f"Total Rows Exported: {total_rows:,}")
    logger.info(f"Total File Size: {total_size_mb:.2f} MB")
    logger.info(f"✅ Successful: {len(successful)}")
    logger.info(f"⏭️  Skipped: {len(skipped)}")
    logger.info(f"❌ Errors: {len(errors)}")

    if errors:
        logger.error("\nFailed exports:")
        for view in errors:
            logger.error(f"  - {view}: {results[view].get('error')}")

    if not dry_run and successful:
        logger.info("\n🎉 Next steps:")
        logger.info("  1. Create Rill SQL models (if not exists):")
        for view in successful:
            parquet_file = ANALYTICS_VIEWS[view]
            model_name = parquet_file.replace(".parquet", "")
            logger.info(f"     - rill_project/models/{model_name}.sql")
        logger.info("  2. Create Rill dashboards (if not exists):")
        for view in successful:
            parquet_file = ANALYTICS_VIEWS[view]
            dashboard_name = parquet_file.replace(".parquet", "")
            logger.info(f"     - rill_project/dashboards/{dashboard_name}.yaml")
        logger.info("  3. Start Rill:")
        logger.info("     cd rill_project && rill start")

    return {
        "status": "complete",
        "duration_seconds": duration,
        "total_rows": total_rows,
        "total_size_mb": total_size_mb,
        "successful": len(successful),
        "skipped": len(skipped),
        "errors": len(errors),
        "results": results,
    }


def main():
    """Command-line interface."""
    parser = argparse.ArgumentParser(
        description="Export DuckDB analytics views to Parquet for Rill dashboards"
    )
    parser.add_argument(
        "--view",
        type=str,
        help="Filter: only export views containing this string (e.g., 'chronic', 'equity')",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview exports without writing files"
    )
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    summary = export_all_views(dry_run=args.dry_run, filter_view=args.view)

    # Exit with error code if any exports failed
    if summary.get("errors", 0) > 0:
        exit(1)


if __name__ == "__main__":
    main()
