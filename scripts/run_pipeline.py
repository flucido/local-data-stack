#!/usr/bin/env python3
"""
run_pipeline.py - Simple orchestration for local-data-stack

Replaces Dagster with a straightforward Python script that runs:
1. Stage 1: Data ingestion (Aeries API + Excel imports + CDE public data via dlt)
2. Stage 2: Data refinement (dbt transformations)
3. Stage 3: Analytics marts (dbt analytics models)
4. Stage 4: Export to Parquet for Rill dashboards

No cloud dependencies. All processing happens locally with DuckDB.
"""

import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class PipelineOrchestrator:
    """Simple orchestrator for the local data pipeline."""

    def __init__(
        self, dbt_project_dir: str | Path | None = None, db_path: str | Path | None = None
    ):
        self.project_root = project_root
        self.dbt_project_dir = (
            Path(dbt_project_dir)
            if dbt_project_dir
            else (self.project_root / "oss_framework" / "dbt")
        )
        default_db = self.project_root / "oss_framework" / "data" / "analytics.duckdb"
        self.prod_db_path = Path(
            db_path or os.getenv("DUCKDB_DATABASE_PATH") or default_db
        ).resolve()
        # Blue/green building file must have a single-dot basename: dbt-duckdb
        # derives the ref catalog name via os.path.splitext (strips only the final
        # extension -> "analytics.duckdb" for "analytics.duckdb.building"), while
        # DuckDB names the attached catalog by stripping from the first dot
        # ("analytics"). Refs compiled against the splitext name do not bind and
        # dbt dies with: Binder Error: Catalog "analytics.duckdb" does not exist!
        # Sanitizing the stem guarantees exactly one dot in the building basename,
        # so both derivations agree regardless of the prod filename.
        building_stem = self.prod_db_path.stem.replace(".", "_")
        self.building_db_path = self.prod_db_path.with_name(f"{building_stem}_building.duckdb")
        self._active_db_path = self.prod_db_path
        # Resolve dbt: prefer DBT_COMMAND env var, then venv dbt, then system dbt
        venv_dbt = str(self.project_root / ".venv" / "bin" / "dbt")
        self.dbt_executable = (
            os.getenv("DBT_COMMAND")
            or shutil.which("dbt")
            or (venv_dbt if Path(venv_dbt).exists() else "dbt")
        )
        self.python_executable = sys.executable
        self.start_time = datetime.now()

    def active_db_path_str(self) -> str:
        """Return the DuckDB path currently targeted by pipeline subprocesses."""
        return str(self._active_db_path)

    def log(self, message: str, level: str = "INFO"):
        """Simple logging."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")

    def run_command(self, cmd: str, description: str, workdir: Path | None = None) -> bool:
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

        # Ensure subprocesses can import oss_framework and scripts
        env = os.environ.copy()
        env["DUCKDB_DATABASE_PATH"] = str(self._active_db_path)
        existing_path = env.get("PYTHONPATH", "")
        project_root_str = str(self.project_root)
        if project_root_str not in existing_path:
            env["PYTHONPATH"] = (
                f"{project_root_str}:{existing_path}" if existing_path else project_root_str
            )

        try:
            result = subprocess.run(
                cmd,
                shell=True,
                cwd=str(cwd),
                env=env,
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
        - Aeries API (student, enrollment, attendance, grades) — test mode if no API key
        - Excel imports (supplemental data) — skips silently if env vars not set
        - CDE public data files (24 domains) — loads whatever files are in data/raw/

        Writes to: DuckDB (aeries_stage1, excel_stage1, cde_raw schemas)
        """
        self.log("=== STAGE 1: DATA INGESTION ===")

        # Check if ingestion scripts exist
        aeries_pipeline = (
            self.project_root / "oss_framework" / "pipelines" / "aeries_dlt_pipeline.py"
        )
        excel_pipeline = (
            self.project_root / "oss_framework" / "pipelines" / "excel_imports_dlt_pipeline.py"
        )
        cde_pipeline = self.project_root / "oss_framework" / "pipelines" / "cde_data_pipeline.py"

        success = True

        if aeries_pipeline.exists():
            # Orchestrated rebuilds must be idempotent: on the filesystem
            # destination dlt's write_disposition="merge" degrades to append for
            # plain Parquet, the landing dir accumulates one file-set per load,
            # and the sync materializes ALL of them (observed: a 17x-duplicated
            # rebuild). The duckdb destination merges on primary keys and
            # refresh="drop_sources" makes Stage 1 a deterministic full reload.
            success = success and self.run_command(
                f"{self.python_executable} {aeries_pipeline} duckdb --refresh",
                "Aeries API ingestion (dlt)",
            )
        else:
            self.log(f"Skipping: {aeries_pipeline} not found", "WARNING")

        if excel_pipeline.exists():
            success = success and self.run_command(
                f"{self.python_executable} {excel_pipeline}", "Excel imports ingestion (dlt)"
            )
        else:
            self.log(f"Skipping: {excel_pipeline} not found", "WARNING")

        if cde_pipeline.exists():
            success = success and self.run_command(
                f"{self.python_executable} {cde_pipeline}",
                "CDE public data ingestion (dlt)",
            )
        else:
            self.log(f"Skipping: {cde_pipeline} not found", "WARNING")

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

        # Then features, scoring, analytics, and the Rill export views. The
        # exports folder is part of the warehouse contract (Stage 4 reads
        # main_analytics.rill_* views); leaving it out of Stage 3 means the
        # blue/green copy carries stale view bodies from the previous build,
        # which reference the previous catalog name and fail Stage 4 binding.
        if success:
            success = success and self.run_command(
                self.dbt_command(
                    "run --select mart_features mart_scoring mart_analytics tag:rill_export"
                ),
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
            f"{self.python_executable} {export_script}",
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

    def run_full_pipeline(
        self, skip_tests: bool = False, allow_test_failures: bool = False
    ) -> bool:
        """
        Run the complete data pipeline.

        Args:
            skip_tests: If True, skip dbt test execution
            allow_test_failures: If True, return True even when dbt tests fail

        Returns:
            True if all stages succeeded
        """
        self.log("╔═══════════════════════════════════════════════════╗")
        self.log("║   LOCAL DATA STACK PIPELINE - FULL RUN          ║")
        self.log("╚═══════════════════════════════════════════════════╝")

        self.prod_db_path.parent.mkdir(parents=True, exist_ok=True)
        for stale in (self.building_db_path, Path(f"{self.building_db_path}.wal")):
            if stale.exists():
                stale.unlink()
        if self.prod_db_path.exists():
            shutil.copy2(self.prod_db_path, self.building_db_path)

        prev_env_db = os.environ.get("DUCKDB_DATABASE_PATH")
        self._active_db_path = self.building_db_path
        os.environ["DUCKDB_DATABASE_PATH"] = str(self.building_db_path)

        try:
            # Stage 1: Ingestion
            if not self.stage1_ingestion():
                self.log("Pipeline failed at Stage 1 (Ingestion)", "ERROR")
                return False

            # Stage 2: Refinement
            if not self.stage2_refinement():
                self.log("Pipeline failed at Stage 2 (Refinement)", "ERROR")
                return False

            # Stage 3: Analytics
            if not self.stage3_analytics():
                self.log("Pipeline failed at Stage 3 (Analytics)", "ERROR")
                return False

            # Tests (optional)
            if not skip_tests:
                if not self.run_tests():
                    if not allow_test_failures:
                        self.log("Pipeline failed at Data Quality Tests", "ERROR")
                        return False
                    self.log(
                        "Data quality tests failed (continuing due to --allow-test-failures)",
                        "WARNING",
                    )

            # Stage 4: Export to Parquet
            if not self.stage4_export():
                self.log("Pipeline failed at Stage 4 (Export)", "ERROR")
                return False

            # Atomic Blue/Green DuckDB swap
            if self.building_db_path.exists():
                os.replace(self.building_db_path, self.prod_db_path)
                wal_prod = Path(f"{self.prod_db_path}.wal")
                if wal_prod.exists():
                    wal_prod.unlink()

            elapsed = datetime.now() - self.start_time
            self.log("╔═══════════════════════════════════════════════════╗")
            self.log("║   PIPELINE COMPLETED SUCCESSFULLY                ║")
            self.log(f"║   Duration: {elapsed}                           ║")
            self.log("╚═══════════════════════════════════════════════════╝")
            return True
        finally:
            self._active_db_path = self.prod_db_path
            if prev_env_db is None:
                os.environ.pop("DUCKDB_DATABASE_PATH", None)
            else:
                os.environ["DUCKDB_DATABASE_PATH"] = prev_env_db
            for leftover in (self.building_db_path, Path(f"{self.building_db_path}.wal")):
                if leftover.exists():
                    leftover.unlink()


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
        "--allow-test-failures",
        action="store_true",
        help="Allow pipeline to succeed even if dbt data quality tests fail",
    )
    parser.add_argument(
        "--dbt-dir", type=str, help="Path to dbt project directory (default: oss_framework/dbt)"
    )

    args = parser.parse_args()

    orchestrator = PipelineOrchestrator(dbt_project_dir=args.dbt_dir)

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
        success = orchestrator.run_full_pipeline(
            skip_tests=args.skip_tests,
            allow_test_failures=args.allow_test_failures,
        )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
