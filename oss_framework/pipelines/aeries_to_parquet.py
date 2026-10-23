#!/usr/bin/env python3
"""
AeRIES CSV to Parquet Ingestion Pipeline

Converts AeRIES student information system CSV exports to Parquet format
with ZSTD compression and year-based partitioning.

This pipeline processes 7 domains (students, attendance, grades, discipline,
enrollment, programs, gpa) across 6 academic years (2020-2026) to create a
production-ready data lake in Stage 1.

Usage:
    # Process all domains and years
    python oss_framework/pipelines/aeries_to_parquet.py

    # Process specific domain
    python oss_framework/pipelines/aeries_to_parquet.py --domain students

    # Process specific year
    python oss_framework/pipelines/aeries_to_parquet.py --year 2023-2024

    # Process specific domain and year with verbose logging
    python oss_framework/pipelines/aeries_to_parquet.py --domain students --year 2023-2024 --verbose

    # Help
    python oss_framework/pipelines/aeries_to_parquet.py --help

Example:
    >>> from aeries_to_parquet import AeriesToParquetPipeline
    >>> pipeline = AeriesToParquetPipeline()
    >>> result = pipeline.convert(domain='students', year='2023-2024')
    >>> print(f"Converted {result['rows_written']} rows")
"""

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import polars as pl

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Configuration
SOURCE_BASE = Path(os.getenv("AERIES_SOURCE_PATH", "oss_framework/data/sample_data"))
TARGET_BASE = Path(os.getenv("STAGE1_PATH", "oss_framework/data/stage1")) / "aeries"

# Domain mappings: (target_name, source_directory, csv_prefix)
# target_name: how it appears in output directory and CLI
# source_directory: actual directory name in source data
# csv_prefix: prefix of CSV filename in source
DOMAIN_MAPPINGS = {
    "students": ("students", "students", "students"),
    "attendance": ("attendance_transformed", "attendance_transformed", "attendance"),
    "discipline": ("discipline_transformed", "discipline_transformed", "discipline"),
    "enrollment": ("enrollment", "enrollment", "enrollment"),
    "programs": ("programs", "programs", "programs"),
    "gpa": ("gpa", "grades_gpa", "gpa"),
    "grades": ("grades_transformed", "grades_transformed", "grades"),
}

DOMAINS = list(DOMAIN_MAPPINGS.keys())

YEARS = ["2020-2021", "2021-2022", "2022-2023", "2023-2024", "2024-2025", "2025-2026"]

# Compression settings
COMPRESSION_CODEC = "zstd"
COMPRESSION_LEVEL = 3

# Values treated as NULL when scanning CSVs
NULL_VALUES = ["", "NULL", "N/A", "NA", "None", " "]

# Data type mappings to preserve leading zeros in ID, code, and phone fields
DTYPE_MAPPINGS = {
    "students": {
        # Student identifiers - preserve leading zeros
        "StudentID": str,
        "OldStudentID": str,
        "StateStudentID": str,
        "StudentNumber": str,
        # School codes - preserve leading zeros
        "SchoolCode": str,
        "NextSchoolCode": str,
        # Language and counselor codes
        "CorrespondenceLanguageCode": str,
        "CounselorNumber": str,
        # Address zip codes and extensions - preserve leading zeros
        "MailingAddressZipCode": str,
        "MailingAddressZipExt": str,
        "ResidenceAddressZipCode": str,
        "ResidenceAddressZipExt": str,
        # Phone numbers - preserve leading zeros
        "HomePhone": str,
        "StudentMobilePhone": str,
        # User codes - preserve leading zeros
        "UserCode1": str,
        "UserCode2": str,
        "UserCode3": str,
        "UserCode4": str,
        "UserCode5": str,
        "UserCode6": str,
        "UserCode7": str,
        "UserCode8": str,
        "UserCode9": str,
        "UserCode10": str,
        "UserCode11": str,
        "UserCode12": str,
        "UserCode13": str,
        # Race codes - preserve leading zeros
        "RaceCode1": str,
        "RaceCode2": str,
        "RaceCode3": str,
        "RaceCode4": str,
        "RaceCode5": str,
        # Additional student codes - preserve leading zeros
        "NetworkLoginID": str,
        "RecordsReleaseCode": str,
        "LanguageFluencyCode": str,
        "HomeLanguageCode": str,
        "AttendanceProgramCodePrimary": str,
        "AttendanceProgramCodeAdditional1": str,
        "AttendanceProgramCodeAdditional2": str,
        "LockerNumber": str,
        "ElementaryTeacherNumber": str,
    },
    "attendance": {
        # Attendance program codes - preserve leading zeros
        "AttendanceProgramCodePrimary": str,
        "AttendanceProgramCodeAdditional1": str,
        "AttendanceProgramCodeAdditional2": str,
        "ReportingSchoolCode": str,
    },
    "discipline": {
        # Incident identifiers - preserve leading zeros
        "IncidentID": str,
        "SequenceNumber": str,
        "Admin_SequenceNumber": str,
        # Violation and user codes
        "ViolationCode1": str,
        "ViolationCode2": str,
        "ViolationCode3": str,
        "ViolationCode4": str,
        "ViolationCode5": str,
        "UserCode1": str,
        "UserCode2": str,
        "UserCode3": str,
        "UserCode4": str,
        "UserCode5": str,
        "UserCode6": str,
        "UserCode7": str,
        "UserCode8": str,
        "StaffReferral": str,
    },
    "enrollment": {
        # Student and school identifiers - preserve leading zeros
        "StudentID": str,
        "StudentNumber": str,
        "SchoolCode": str,
        "NextSchoolCode": str,
        "ReportingSchoolCode": str,
        # District and state codes
        "InterIntraDistrictStateCode": str,
        "NonpublicSchoolStateCode": str,
        "InterIntraDistrictTransferCode": str,
        "ExitReasonCode": str,
        # Attendance program codes
        "AttendanceProgramCode": str,
        "AttendanceProgramCodeAdditional1": str,
        "AttendanceProgramCodeAdditional2": str,
        # Teacher and track codes
        "ElementaryTeacherNumber": str,
        "Track": str,
    },
    "programs": {},
    "grades": {
        # Student and teacher identifiers - preserve leading zeros
        "StudentID": str,
        "TeacherNumber": str,
        "MP_PrimaryStaffID": str,
        "SectionNumber": str,
        "Period": str,
        "CourseID": str,
    },
    "gpa": {},
}


class AeriesToParquetPipeline:
    """Pipeline for converting AeRIES CSV files to Parquet format."""

    def __init__(self, verbose: bool = False):
        """Initialize pipeline.

        Args:
            verbose: Enable verbose logging.
        """
        self.verbose = verbose
        if verbose:
            logger.setLevel(logging.DEBUG)

        self.stats = {
            "total_files_processed": 0,
            "total_rows_written": 0,
            "total_input_bytes": 0,
            "total_output_bytes": 0,
            "files_failed": 0,
            "failed_files": [],
        }

    @staticmethod
    def _scan_csv(csv_file: Path, domain: str) -> pl.LazyFrame:
        """Lazily scan a CSV with Polars, pinning ID/code columns to Utf8.

        ``encoding='lossy_utf8'`` tolerates the BOM in Excel-exported CSVs and
        ``truncate_ragged_lines`` absorbs trailing-delimiter drift.
        """
        overrides = {col: pl.Utf8 for col in DTYPE_MAPPINGS.get(domain, {})}
        return pl.scan_csv(
            csv_file,
            schema_overrides=overrides,
            encoding="utf8-lossy",
            null_values=NULL_VALUES,
            infer_schema_length=10_000,
            truncate_ragged_lines=True,
        )

    def convert(self, domain: str, year: str) -> dict[str, Any]:
        """
        Convert single CSV file to Parquet with ZSTD compression.

        Args:
            domain: Domain name (e.g., 'students')
            year: Academic year (e.g., '2023-2024')

        Returns:
            Dictionary with conversion results:
            - success: bool
            - rows_written: int or None
            - input_size: int or None
            - output_size: int or None
            - compression_ratio: float or None
            - error: str or None
        """
        result = {
            "domain": domain,
            "year": year,
            "success": False,
            "rows_written": None,
            "input_size": None,
            "output_size": None,
            "compression_ratio": None,
            "error": None,
        }

        try:
            # Get domain mapping
            if domain not in DOMAIN_MAPPINGS:
                result["error"] = f"Unknown domain: {domain}"
                logger.warning(result["error"])
                return result

            target_name, source_dir, csv_prefix = DOMAIN_MAPPINGS[domain]

            # Build paths
            year_underscore = year.replace("-", "_")
            csv_file = SOURCE_BASE / source_dir / f"{csv_prefix}_{year_underscore}.csv"

            output_dir = TARGET_BASE / target_name / f"year={year}"
            output_file = output_dir / "part-000.parquet"

            # Check if source file exists
            if not csv_file.exists():
                result["error"] = f"CSV file not found: {csv_file}"
                logger.warning(result["error"])
                return result

            # Get input file size
            input_size = csv_file.stat().st_size
            result["input_size"] = input_size

            if self.verbose:
                logger.debug(f"Reading CSV: {csv_file}")

            # Scan CSV lazily with Polars (BOM-tolerant, all IDs kept as Utf8)
            lf = self._scan_csv(csv_file, domain)
            rows_read = lf.select(pl.len()).collect().item()

            if self.verbose:
                columns = lf.collect_schema().names()
                logger.debug(f"Loaded {rows_read} rows from {csv_file}")
                logger.debug(f"Columns: {', '.join(columns)}")

            # Create parent directories
            output_dir.mkdir(parents=True, exist_ok=True)

            # Stream to Parquet with ZSTD compression (level 3)
            lf.sink_parquet(
                output_file,
                compression=COMPRESSION_CODEC,
                compression_level=COMPRESSION_LEVEL,
            )

            # Get output file size
            output_size = output_file.stat().st_size
            result["output_size"] = output_size

            # Validate: Check row count in written Parquet
            try:
                parquet_rows = pl.scan_parquet(output_file).select(pl.len()).collect().item()

                if parquet_rows != rows_read:
                    logger.warning(
                        f"Row count mismatch for {domain}/{year}: "
                        f"CSV={rows_read}, Parquet={parquet_rows}"
                    )
                    result["error"] = f"Row count validation failed: {rows_read} vs {parquet_rows}"
                    return result
            except Exception as e:
                logger.warning(f"Could not validate row count: {str(e)}")

            # Calculate compression ratio
            if input_size > 0:
                compression_ratio = 1.0 - (output_size / input_size)
                result["compression_ratio"] = compression_ratio
            else:
                result["compression_ratio"] = 0.0

            result["success"] = True
            result["rows_written"] = rows_read

            # Update statistics
            self.stats["total_files_processed"] += 1
            self.stats["total_rows_written"] += rows_read
            self.stats["total_input_bytes"] += input_size
            self.stats["total_output_bytes"] += output_size

            # Log success
            logger.info(
                f"✓ {domain:20} {year}  "
                f"Rows: {rows_read:8}  "
                f"Input: {input_size / 1024:8.1f}KB  "
                f"Output: {output_size / 1024:8.1f}KB  "
                f"Compression: {compression_ratio * 100:5.1f}%"
            )

            return result

        except Exception as e:
            result["error"] = str(e)
            self.stats["files_failed"] += 1
            self.stats["failed_files"].append(f"{domain}/{year}")
            logger.error(f"✗ {domain:20} {year}  Error: {str(e)}")
            return result

    def convert_domain_union(self, domain: str, years: list[str] | None = None) -> dict[str, Any]:
        """Union all available years of a domain into a single Parquet file.

        Uses ``pl.concat(how="diagonal_relaxed")`` so schema drift across
        academic years (columns added/removed between exports) is unioned by
        name, with missing columns filled as null.  A ``source_year`` column
        preserves provenance.

        Args:
            domain: Domain name (e.g., 'students')
            years: Academic years to union (default: all available).

        Returns:
            Result dictionary (same shape as ``convert()``).
        """
        result: dict[str, Any] = {
            "domain": domain,
            "year": "all",
            "success": False,
            "rows_written": None,
            "input_size": None,
            "output_size": None,
            "compression_ratio": None,
            "error": None,
        }

        if domain not in DOMAIN_MAPPINGS:
            result["error"] = f"Unknown domain: {domain}"
            logger.warning(result["error"])
            return result

        target_name, source_dir, csv_prefix = DOMAIN_MAPPINGS[domain]
        candidate_years = years or YEARS

        frames: list[pl.LazyFrame] = []
        total_input_bytes = 0
        for year in candidate_years:
            csv_file = SOURCE_BASE / source_dir / f"{csv_prefix}_{year.replace('-', '_')}.csv"
            if not csv_file.exists():
                logger.warning(f"CSV file not found, skipping: {csv_file}")
                continue
            total_input_bytes += csv_file.stat().st_size
            frames.append(
                self._scan_csv(csv_file, domain).with_columns(pl.lit(year).alias("source_year"))
            )

        if not frames:
            result["error"] = f"No source CSV files found for domain '{domain}'"
            logger.warning(result["error"])
            return result

        output_dir = TARGET_BASE / target_name / "year=all"
        output_file = output_dir / "part-000.parquet"
        output_dir.mkdir(parents=True, exist_ok=True)

        unioned = pl.concat(frames, how="diagonal_relaxed")
        unioned.sink_parquet(
            output_file,
            compression=COMPRESSION_CODEC,
            compression_level=COMPRESSION_LEVEL,
        )

        rows_written = pl.scan_parquet(output_file).select(pl.len()).collect().item()
        output_size = output_file.stat().st_size

        result.update(
            {
                "success": True,
                "rows_written": rows_written,
                "input_size": total_input_bytes,
                "output_size": output_size,
                "compression_ratio": (
                    1.0 - (output_size / total_input_bytes) if total_input_bytes else 0.0
                ),
            }
        )

        self.stats["total_files_processed"] += len(frames)
        self.stats["total_rows_written"] += rows_written
        self.stats["total_input_bytes"] += total_input_bytes
        self.stats["total_output_bytes"] += output_size

        logger.info(
            f"✓ {domain:20} all-years  Rows: {rows_written:8}  "
            f"Files: {len(frames)}  Output: {output_size / 1024:8.1f}KB"
        )
        return result

    def process_domains_and_years(
        self, domains: list[str] | None = None, years: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """
        Process multiple domains and years.

        Args:
            domains: List of domains to process (default: all)
            years: List of years to process (default: all)

        Returns:
            List of conversion results.
        """
        if domains is None:
            domains = DOMAINS
        if years is None:
            years = YEARS

        # Validate requested domains
        invalid_domains = [d for d in domains if d not in DOMAINS]
        if invalid_domains:
            logger.warning(f"Skipping invalid domains: {invalid_domains}")
            domains = [d for d in domains if d in DOMAINS]

        # Validate requested years
        invalid_years = [y for y in years if y not in YEARS]
        if invalid_years:
            logger.warning(f"Skipping invalid years: {invalid_years}")
            years = [y for y in years if y in YEARS]

        results = []
        total_combinations = len(domains) * len(years)

        logger.info(f"Processing {total_combinations} domain/year combinations")
        logger.info(f"Domains: {', '.join(domains)}")
        logger.info(f"Years: {', '.join(years)}")
        logger.info("-" * 100)

        for domain in domains:
            for year in years:
                result = self.convert(domain, year)
                results.append(result)

        return results

    def print_summary(self):
        """Print execution summary statistics."""
        logger.info("-" * 100)
        logger.info("SUMMARY STATISTICS")
        logger.info("-" * 100)

        # Calculate totals and averages
        total_processed = self.stats["total_files_processed"]
        total_rows = self.stats["total_rows_written"]
        total_input = self.stats["total_input_bytes"]
        total_output = self.stats["total_output_bytes"]
        total_failed = self.stats["files_failed"]

        if total_input > 0:
            overall_compression = 1.0 - (total_output / total_input)
        else:
            overall_compression = 0.0

        logger.info(f"Files Processed:        {total_processed}")
        logger.info(f"Files Failed:           {total_failed}")
        logger.info(f"Total Rows Written:     {total_rows:,}")
        logger.info(f"Total Input Size:       {total_input / (1024 * 1024):.2f} MB")
        logger.info(f"Total Output Size:      {total_output / (1024 * 1024):.2f} MB")
        logger.info(f"Overall Compression:    {overall_compression * 100:.1f}%")

        if total_processed > 0:
            avg_rows = total_rows / total_processed
            logger.info(f"Average Rows/File:      {avg_rows:.0f}")

        if total_failed > 0:
            logger.warning(f"Failed Files: {', '.join(self.stats['failed_files'])}")

        logger.info("-" * 100)

        return self.stats


def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="AeRIES CSV to Parquet Ingestion Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process all domains and years
  python aeries_to_parquet.py

  # Process specific domain
  python aeries_to_parquet.py --domain students

  # Process specific year
  python aeries_to_parquet.py --year 2023-2024

  # Process specific domain and year with verbose logging
  python aeries_to_parquet.py --domain students --year 2023-2024 --verbose

Available Domains:
  students, attendance, discipline, enrollment, programs, gpa, grades

Available Years:
  2020-2021, 2021-2022, 2022-2023, 2023-2024, 2024-2025, 2025-2026
        """,
    )

    parser.add_argument(
        "--domain", type=str, default=None, help="Process specific domain (default: all)"
    )
    parser.add_argument(
        "--year", type=str, default=None, help="Process specific year (default: all)"
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    # Build lists of domains and years to process
    domains = [args.domain] if args.domain else None
    years = [args.year] if args.year else None

    # Create and run pipeline
    pipeline = AeriesToParquetPipeline(verbose=args.verbose)
    logger.info("Starting AeRIES CSV to Parquet Pipeline")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")

    try:
        pipeline.process_domains_and_years(domains=domains, years=years)

        # Print summary
        stats = pipeline.print_summary()

        # Exit with appropriate code
        if stats["files_failed"] > 0:
            sys.exit(1)
        else:
            sys.exit(0)

    except KeyboardInterrupt:
        logger.info("Pipeline interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Pipeline failed: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
