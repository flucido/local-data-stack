"""
Orchestrator for Week 1-2 Data Foundation Implementation
Runs all data ingestion, transformation, and validation in sequence
"""

import logging
import sys
from pathlib import Path
from datetime import datetime

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

from logging_config import setup_logging
from config import validate_config, STAGE1_PATH, STAGE2_PATH

logger = setup_logging(__name__)


class Week1Orchestrator:
    """Orchestrate Week 1-2 data foundation setup"""

    def __init__(self):
        self.start_time = datetime.now()
        self.results = {}
        logger.info("=" * 60)
        logger.info("Week 1-2 Data Foundation Orchestration")
        logger.info("=" * 60)

    def validate_prerequisites(self) -> bool:
        """Validate all prerequisites are met"""
        logger.info("STEP 1: Validating prerequisites...")
        try:
            # This Week 1 path can run with local/sample data.
            validate_config(require_aeries=False)
            logger.info("✅ Configuration validated")
            return True
        except ValueError as e:
            logger.error(f"❌ Configuration error: {e}")
            return False

    def load_stage1_parquet(self) -> bool:
        """Load Stage 1 canonical Parquet data"""
        logger.info("STEP 2: Generating Stage 1 Parquet landing data...")
        try:
            from stage1_generate_sample_parquet import generate_stage1_parquet
            from sync_raw_views_from_stage1 import sync_raw_views_from_stage1

            result = generate_stage1_parquet(stage1_path=STAGE1_PATH)
            logger.info(f"✅ Stage 1 Parquet generated: {result['load_date']}")
            self.results["stage1_parquet"] = {
                "load_date": result["load_date"],
                "stage1_path": result["stage1_path"],
            }

            view_result = sync_raw_views_from_stage1()
            logger.info("✅ DuckDB raw_* views synced from Stage 1 Parquet")
            self.results["raw_views"] = "success"
            return True
        except Exception as e:
            logger.error(f"❌ Error loading Stage 1 Parquet: {e}")
            self.results["stage1_parquet"] = f"failed: {e}"
            return False

    def import_d_and_f_report(self) -> bool:
        """Import D&F (D grades, F grades, 504, SPED) report"""
        logger.info("STEP 4: Importing D&F report from Excel...")
        try:
            from import_d_and_f_report import DAndFImporter
            from config import EXCEL_DF_REPORT_PATH

            if not EXCEL_DF_REPORT_PATH:
                logger.warning("⚠️  D&F report path not configured, skipping")
                self.results["d_and_f_import"] = "skipped"
                return True

            importer = DAndFImporter()
            count = importer.import_from_excel(EXCEL_DF_REPORT_PATH)
            importer.close()

            logger.info(f"✅ D&F report imported: {count} records")
            self.results["d_and_f_import"] = count
            return True
        except Exception as e:
            logger.error(f"❌ Error importing D&F report: {e}")
            self.results["d_and_f_import"] = f"failed: {e}"
            return False

    def import_demographic_data(self) -> bool:
        """Import demographic data from Excel"""
        logger.info("STEP 5: Importing demographic data from Excel...")
        try:
            from import_demographic_data import DemographicImporter
            from config import EXCEL_DEMOGRAPHIC_PATH

            if not EXCEL_DEMOGRAPHIC_PATH:
                logger.warning("⚠️  Demographic report path not configured, skipping")
                self.results["demographic_import"] = "skipped"
                return True

            importer = DemographicImporter()
            count = importer.import_from_excel(EXCEL_DEMOGRAPHIC_PATH)
            importer.close()

            logger.info(f"✅ Demographic data imported: {count} records")
            self.results["demographic_import"] = count
            return True
        except Exception as e:
            logger.error(f"❌ Error importing demographic data: {e}")
            self.results["demographic_import"] = f"failed: {e}"
            return False

    def run_data_quality_tests(self) -> bool:
        """Run data quality validation tests"""
        logger.info("STEP 6: Running data quality validation tests...")
        try:
            from data_quality import DataQualityValidator
            from config import DUCKDB_DATABASE_PATH

            validator = DataQualityValidator(DUCKDB_DATABASE_PATH)
            results = validator.run_all_validations()
            validator.close()

            passed = sum(1 for v in results.values() if v)
            total = len(results)

            if passed == total:
                logger.info(f"✅ All data quality tests passed ({passed}/{total})")
                self.results["data_quality"] = "all_passed"
                return True
            else:
                logger.warning(f"⚠️  Data quality tests: {passed}/{total} passed")
                self.results["data_quality"] = f"{passed}/{total} passed"
                return True  # Continue even if some tests fail
        except Exception as e:
            logger.error(f"❌ Error running data quality tests: {e}")
            self.results["data_quality"] = f"failed: {e}"
            return False

    def generate_report(self) -> str:
        """Generate execution report"""
        logger.info("=" * 60)
        logger.info("Week 1-2 Data Foundation - Execution Report")
        logger.info("=" * 60)

        duration = (datetime.now() - self.start_time).total_seconds()
        logger.info(f"Total Duration: {duration:.1f} seconds")
        logger.info("")
        logger.info("Results:")
        for step, result in self.results.items():
            logger.info(f"  {step}: {result}")
        logger.info("")
        logger.info("=" * 60)

        report = f"""
Week 1-2 Data Foundation Setup Complete

Duration: {duration:.1f} seconds
Timestamp: {datetime.now().isoformat()}

Results:
{chr(10).join(f"  - {k}: {v}" for k, v in self.results.items())}

Next Steps:
1. Review data quality report
2. Run Week 3-4 feature engineering (when ready)
3. Check dashboards at http://localhost:3000 (Metabase)

For detailed logs, see: ./oss_framework/logs/oea.log
"""
        return report

    def run(self) -> bool:
        """Execute complete Week 1-2 pipeline"""
        steps = [
            ("prerequisites", self.validate_prerequisites),
            ("stage1_parquet", self.load_stage1_parquet),
            ("d_and_f_import", self.import_d_and_f_report),
            ("demographic_import", self.import_demographic_data),
            ("quality_validation", self.run_data_quality_tests),
        ]

        all_passed = True
        for step_name, step_func in steps:
            try:
                if not step_func():
                    all_passed = False
                    logger.warning(f"⚠️  Step {step_name} had issues but continuing...")
            except Exception as e:
                logger.error(f"❌ Step {step_name} failed with exception: {e}")
                all_passed = False

        # Generate and log report
        report = self.generate_report()
        logger.info(report)

        return all_passed


if __name__ == "__main__":
    orchestrator = Week1Orchestrator()
    success = orchestrator.run()

    if success:
        logger.info("✅ Week 1-2 data foundation setup COMPLETE")
        sys.exit(0)
    else:
        logger.error("❌ Week 1-2 setup had errors - check logs for details")
        sys.exit(1)
