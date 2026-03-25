#!/usr/bin/env python3
"""
run_pipeline.py - Simple orchestration for local-data-stack

Replaces Dagster with a straightforward Python script that runs:
1. Stage 1: Data ingestion (Aeries API + Excel imports via dlt)
2. Stage 2: Data refinement (dbt transformations)
3. Stage 3: Analytics marts (dbt analytics models)

No cloud dependencies. All processing happens locally with DuckDB.
"""

import os
import sys
import subprocess
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import metrics collector (optional - graceful degradation if not available)
try:
    from scripts.metrics_exporter import MetricsCollector
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False
    print("[INFO] Metrics collection disabled (prometheus_client not installed)")


class PipelineOrchestrator:
    """Simple orchestrator for the local data pipeline."""

    def __init__(self, dbt_project_dir: Optional[str] = None, enable_metrics: bool = True):
        self.project_root = project_root
        self.dbt_project_dir = dbt_project_dir or self.project_root / "oss_framework" / "dbt"
        self.dbt_executable = os.getenv("DBT_COMMAND") or shutil.which("dbt") or "dbt"
        self.start_time = datetime.now()
        
        # Initialize metrics collector
        self.metrics = None
        if enable_metrics and METRICS_AVAILABLE:
            try:
                self.metrics = MetricsCollector(
                    mode='textfile',
                    export_path='/tmp/pipeline_metrics.prom'
                )
                self.log("Metrics collection enabled", "INFO")
            except Exception as e:
                self.log(f"Failed to initialize metrics: {e}", "WARNING")
                self.metrics = None

    def log(self, message: str, level: str = "INFO"):
        """Simple logging."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")

    def run_command(self, cmd: str, description: str, workdir: Optional[Path] = None) -> bool:
        """
        Run a shell command and return success status.

        Args:
            cmd: Command to execute
            description: Human-readable description
            workdir: Working directory (defaults to project root)

        Returns:
            True if command succeeded (exit code 0), False otherwise
        """
        self.log(f"Starting: {description}")
        self.log(f"Command: {cmd}")

        cwd = workdir or self.project_root

        try:
            result = subprocess.run(
                cmd,
                shell=True,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=3600,  # 1 hour timeout
            )

            if result.returncode == 0:
                self.log(f"✓ Completed: {description}", "SUCCESS")
                if result.stdout:
                    print(result.stdout)
                return True
            else:
                self.log(f"✗ Failed: {description}", "ERROR")
                if result.stderr:
                    print(f"Error output:\n{result.stderr}")
                if result.stdout:
                    print(f"Standard output:\n{result.stdout}")
                return False

        except subprocess.TimeoutExpired:
            self.log(f"✗ Timeout: {description}", "ERROR")
            return False
        except Exception as e:
            self.log(f"✗ Exception: {description} - {str(e)}", "ERROR")
            return False

    def dbt_command(self, args: str) -> str:
        """Build a dbt command using the current environment."""
        return f"{self.dbt_executable} {args} --project-dir . --profiles-dir ."

    def stage1_ingestion(self) -> bool:
        """
        Stage 1: Ingest raw data from external sources.

        Runs dlt pipelines to extract data from:
        - Aeries API (student, enrollment, attendance, grades)
        - Excel imports (supplemental data)

        Writes to: data/stage1/raw/
        """
        self.log("=== STAGE 1: DATA INGESTION ===")

        # Check if ingestion scripts exist
        aeries_pipeline = (
            self.project_root / "oss_framework" / "pipelines" / "aeries_dlt_pipeline.py"
        )
        excel_pipeline = (
            self.project_root / "oss_framework" / "pipelines" / "excel_imports_dlt_pipeline.py"
        )

        success = True

        if aeries_pipeline.exists():
            success = success and self.run_command(
                f"python3 {aeries_pipeline}", "Aeries API ingestion (dlt)"
            )
        else:
            self.log(f"Skipping: {aeries_pipeline} not found", "WARNING")

        if excel_pipeline.exists():
            success = success and self.run_command(
                f"python3 {excel_pipeline}", "Excel imports ingestion (dlt)"
            )
        else:
            self.log(f"Skipping: {excel_pipeline} not found", "WARNING")

        return success

    def stage2_refinement(self) -> bool:
        """
        Stage 2: Refine and standardize raw data.

        Runs dbt models tagged with 'stage2' or in mart_core.
        Applies data quality, normalization, deduplication.

        Writes to: DuckDB tables in mart_core schema
        """
        self.log("=== STAGE 2: DATA REFINEMENT ===")

        return self.run_command(
            self.dbt_command("run --select tag:staging"),
            "dbt refinement models (staging layer)",
            workdir=self.dbt_project_dir,
        )

    def stage3_analytics(self) -> bool:
        """
        Stage 3: Build analytics marts and aggregations.

        Runs dbt models for:
        - Feature engineering (mart_features)
        - Risk scoring (mart_scoring)
        - Analytics views (mart_analytics)

        Writes to: DuckDB tables in analytics schemas
        """
        self.log("=== STAGE 3: ANALYTICS MARTS ===")

        # Seed required mapping tables first
        success = self.run_command(
            self.dbt_command("seed --select school_cds_mapping_seed"),
            "dbt seed school mapping table",
            workdir=self.dbt_project_dir,
        )

        # Build privacy layer required by core marts
        if success:
            success = success and self.run_command(
                self.dbt_command("run --select mart_privacy"),
                "dbt privacy pseudonymization models",
                workdir=self.dbt_project_dir,
            )

        # Run core marts
        if success:
            success = success and self.run_command(
                self.dbt_command("run --select mart_core"),
                "dbt core dimension/fact tables",
                workdir=self.dbt_project_dir,
            )

        # Then features, scoring, and analytics
        if success:
            success = success and self.run_command(
                self.dbt_command("run --select mart_features mart_scoring mart_analytics"),
                "dbt analytics models",
                workdir=self.dbt_project_dir,
            )

        return success

    def stage4_export(self) -> bool:
        """
        Stage 4: Export analytics to Parquet for Rill.
        
        Exports all analytics views from DuckDB to Parquet files
        in rill_project/data/ using the export_to_rill.py script.
        """
        self.log("=== STAGE 4: EXPORTING ANALYTICS TO PARQUET FOR RILL ===")

        export_script = self.project_root / "scripts" / "export_to_rill.py"
        
        if not export_script.exists():
            self.log(f"Export script not found: {export_script}", "ERROR")
            return False

        return self.run_command(
            f"python3 {export_script}",
            "Export analytics views to Parquet for Rill dashboards",
        )

    def run_tests(self) -> bool:
        """Run dbt tests to validate data quality."""
        self.log("=== RUNNING DATA QUALITY TESTS ===")

        return self.run_command(
            self.dbt_command("test"),
            "dbt data quality tests",
            workdir=self.dbt_project_dir,
        )

    def run_full_pipeline(self, skip_tests: bool = False) -> bool:
        """
        Run the complete data pipeline with metrics collection.

        Args:
            skip_tests: If True, skip dbt test execution

        Returns:
            True if all stages succeeded
        """
        self.log("╔═══════════════════════════════════════════════════╗")
        self.log("║   LOCAL DATA STACK PIPELINE - FULL RUN          ║")
        self.log("╚═══════════════════════════════════════════════════╝")

        # Stage 1: Ingestion
        if self.metrics:
            self.metrics.record_stage_start('stage1_ingestion')
        
        stage1_success = self.stage1_ingestion()
        
        if self.metrics:
            if stage1_success:
                self.metrics.record_stage_complete('stage1_ingestion', rows=0, status='success')
            else:
                self.metrics.record_stage_error('stage1_ingestion', error_type='execution_failed')
        
        if not stage1_success:
            self.log("Pipeline failed at Stage 1 (Ingestion)", "ERROR")
            return False

        # Stage 2: Refinement
        if self.metrics:
            self.metrics.record_stage_start('stage2_refinement')
        
        stage2_success = self.stage2_refinement()
        
        if self.metrics:
            if stage2_success:
                self.metrics.record_stage_complete('stage2_refinement', rows=0, status='success')
            else:
                self.metrics.record_stage_error('stage2_refinement', error_type='execution_failed')
        
        if not stage2_success:
            self.log("Pipeline failed at Stage 2 (Refinement)", "ERROR")
            return False

        # Stage 3: Analytics
        if self.metrics:
            self.metrics.record_stage_start('stage3_analytics')
        
        stage3_success = self.stage3_analytics()
        
        if self.metrics:
            if stage3_success:
                self.metrics.record_stage_complete('stage3_analytics', rows=0, status='success')
            else:
                self.metrics.record_stage_error('stage3_analytics', error_type='execution_failed')
        
        if not stage3_success:
            self.log("Pipeline failed at Stage 3 (Analytics)", "ERROR")
            return False

        # Stage 4: Export to Parquet
        if self.metrics:
            self.metrics.record_stage_start('stage4_export')
        
        stage4_success = self.stage4_export()
        
        if self.metrics:
            if stage4_success:
                self.metrics.record_stage_complete('stage4_export', rows=0, status='success')
            else:
                self.metrics.record_stage_error('stage4_export', error_type='execution_failed')
        
        if not stage4_success:
            self.log("Pipeline failed at Stage 4 (Export)", "ERROR")
            return False

        # Tests (optional)
        if not skip_tests:
            if not self.run_tests():
                self.log("Data quality tests failed (pipeline completed)", "WARNING")

        # Success summary
        elapsed = datetime.now() - self.start_time
        self.log("╔═══════════════════════════════════════════════════╗")
        self.log("║   PIPELINE COMPLETED SUCCESSFULLY                ║")
        self.log(f"║   Duration: {elapsed}                           ║")
        self.log("╚═══════════════════════════════════════════════════╝")

        return True


def main():
    """CLI entrypoint."""
    import argparse

    parser = argparse.ArgumentParser(description="Local Data Stack Pipeline Orchestrator")
    parser.add_argument(
        "--stage",
        choices=["1", "2", "3", "4", "all"],
        default="all",
        help="Run specific stage or entire pipeline (default: all)",
    )
    parser.add_argument(
        "--skip-tests", action="store_true", help="Skip dbt tests after pipeline run"
    )
    parser.add_argument(
        "--dbt-dir", type=str, help="Path to dbt project directory (default: oss_framework/dbt)"
    )
    parser.add_argument(
        "--no-metrics", action="store_true", help="Disable Prometheus metrics collection"
    )

    args = parser.parse_args()

    orchestrator = PipelineOrchestrator(
        dbt_project_dir=args.dbt_dir,
        enable_metrics=not args.no_metrics
    )

    # Run requested stage(s)
    if args.stage == "1":
        success = orchestrator.stage1_ingestion()
    elif args.stage == "2":
        success = orchestrator.stage2_refinement()
    elif args.stage == "3":
        success = orchestrator.stage3_analytics()
    elif args.stage == "4":
        success = orchestrator.stage4_export()
    else:  # args.stage == "all"
        success = orchestrator.run_full_pipeline(skip_tests=args.skip_tests)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
