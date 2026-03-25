#!/usr/bin/env python3
"""
Comprehensive Pre-Implementation Test Suite
Validates all prerequisites before Week 1-2 execution
Run this AFTER answering clarification questions and BEFORE starting Week 1
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment
load_dotenv()


class PreImplementationValidator:
    """Validate system is ready for Week 1-2 implementation"""

    def __init__(self):
        self.tests = []
        self.passed = 0
        self.failed = 0
        self.skipped = 0

    def test(self, name: str, condition: bool, error_msg: str = "") -> bool:
        """Record test result"""
        status = "✅" if condition else ("⏭️ " if error_msg == "SKIP" else "❌")
        self.tests.append((name, condition, error_msg))

        if condition:
            self.passed += 1
            print(f"{status} {name}")
        elif error_msg == "SKIP":
            self.skipped += 1
            print(f"{status} {name} - {error_msg}")
        else:
            self.failed += 1
            print(f"{status} {name}")
            if error_msg:
                print(f"   └─ {error_msg}")

        return condition

    def check_python_version(self):
        """Verify Python 3.9+"""
        version = sys.version_info
        is_valid = version.major == 3 and version.minor >= 9
        self.test(
            "Python Version",
            is_valid,
            f"Found {version.major}.{version.minor}, need 3.9+" if not is_valid else "",
        )

    def check_required_packages(self):
        """Verify required Python packages are installed"""
        required = [
            ("duckdb", "DuckDB"),
            ("pandas", "Pandas"),
            ("requests", "Requests"),
            ("dotenv", "python-dotenv"),
            ("pyarrow", "PyArrow"),
            ("openpyxl", "OpenPyXL"),
        ]

        for package, display_name in required:
            try:
                __import__(package)
                self.test(f"Package: {display_name}", True)
            except ImportError:
                self.test(
                    f"Package: {display_name}",
                    False,
                    f"Install with: pip install {package}",
                )

    def check_environment_variables(self):
        """Verify required environment variables are set"""
        # Week 1 can run with sample/local data; Aeries credentials are optional.
        # If AERIES_AUTH_METHOD is set, validate it; otherwise skip.
        auth_method = os.getenv("AERIES_AUTH_METHOD", "").lower().strip()

        if not auth_method:
            self.test("Aeries Auth Method", True, "SKIP")
            return

        if auth_method == "api_key":
            api_key = os.getenv("AERIES_API_KEY")
            self.test(
                "Aeries API Key",
                bool(api_key),
                "Set AERIES_API_KEY environment variable",
            )
        elif auth_method == "oauth2":
            client_id = os.getenv("AERIES_CLIENT_ID")
            client_secret = os.getenv("AERIES_CLIENT_SECRET")
            self.test(
                "Aeries OAuth2 Credentials",
                bool(client_id and client_secret),
                "Set AERIES_CLIENT_ID and AERIES_CLIENT_SECRET",
            )
        elif auth_method == "database":
            db_host = os.getenv("AERIES_DB_HOST")
            db_name = os.getenv("AERIES_DB_DATABASE")
            self.test(
                "Aeries Database Config",
                bool(db_host and db_name),
                "Set AERIES_DB_HOST and AERIES_DB_DATABASE",
            )
        else:
            self.test(
                "Aeries Auth Method",
                False,
                f"Invalid auth method: {auth_method}. Use: api_key, oauth2, or database",
            )

    def check_duckdb_connection(self):
        """Verify DuckDB is accessible"""
        try:
            import duckdb

            db_path = os.getenv(
                "DUCKDB_DATABASE_PATH", "./oss_framework/data/oea.duckdb"
            )
            con = duckdb.connect(db_path)
            result = con.execute("SELECT 1").fetchall()
            con.close()
            self.test("DuckDB Connection", True)
        except Exception as e:
            self.test("DuckDB Connection", False, str(e))

    def check_data_directories(self):
        """Verify data directories exist and are writable"""
        dirs = [
            "./oss_framework/data/stage1",
            "./oss_framework/data/stage2",
            "./oss_framework/data/stage3",
            "./oss_framework/logs",
        ]

        for dir_path in dirs:
            dir_obj = Path(dir_path)
            exists = dir_obj.exists()
            writable = os.access(dir_path, os.W_OK) if exists else False

            self.test(
                f"Directory: {dir_path}",
                exists and writable,
                f"{'Does not exist' if not exists else 'Not writable'}",
            )

    def check_excel_files(self):
        """Verify Excel files exist (if configured)"""
        excel_files = [
            ("EXCEL_DF_REPORT_PATH", "D&F Report"),
            ("EXCEL_DEMOGRAPHIC_PATH", "Demographic Report"),
            ("EXCEL_RFEP_PATH", "RFEP Data"),
        ]

        for env_var, display_name in excel_files:
            path = os.getenv(env_var)
            if path:
                exists = Path(path).exists()
                self.test(
                    f"Excel: {display_name}",
                    exists,
                    f"File not found: {path}" if not exists else "",
                )
            else:
                self.test(f"Excel: {display_name}", True, "SKIP")

    def check_excel_update_frequencies(self):
        """Verify Excel update frequencies are valid"""
        valid_frequencies = [
            "daily",
            "weekly",
            "monthly",
            "on-demand",
            "manual",
            "static",
        ]

        frequencies = [
            ("EXCEL_DF_UPDATE_FREQUENCY", "D&F Update Frequency"),
            ("EXCEL_DEMOGRAPHIC_UPDATE_FREQUENCY", "Demographic Update Frequency"),
            ("EXCEL_RFEP_UPDATE_FREQUENCY", "RFEP Update Frequency"),
        ]

        for env_var, display_name in frequencies:
            freq = os.getenv(env_var, "").lower()
            is_valid = freq in valid_frequencies
            self.test(
                display_name,
                is_valid,
                f"Invalid: {freq}. Use: {', '.join(valid_frequencies)}"
                if not is_valid
                else "",
            )

    def check_clarification_answers(self):
        """Verify clarification questions have been answered"""
        answers_file = Path("./oss_framework/docs/CLARIFICATION_ANSWERS.md")
        if answers_file.exists():
            self.test("Clarification Answers", True, "Found answers file")
        else:
            self.test(
                "Clarification Answers",
                False,
                "Complete CLARIFICATION_QUESTIONS.md first and save as CLARIFICATION_ANSWERS.md",
            )

    def run_all_checks(self):
        """Execute all validation checks"""
        print("\n" + "=" * 60)
        print("Pre-Implementation Validation Suite")
        print("=" * 60 + "\n")

        self.check_python_version()
        print()

        self.check_required_packages()
        print()

        self.check_environment_variables()
        print()

        self.check_duckdb_connection()
        print()

        self.check_data_directories()
        print()

        self.check_excel_files()
        print()

        self.check_excel_update_frequencies()
        print()

        self.check_clarification_answers()
        print()

        # Summary
        total = self.passed + self.failed + self.skipped
        print("=" * 60)
        print(
            f"Results: {self.passed}✅ {self.failed}❌ {self.skipped}⏭️  (Total: {total})"
        )
        print("=" * 60)

        if self.failed == 0:
            print("\n✅ All checks passed! Ready for Week 1-2 implementation.")
            print("\nNext steps:")
            print("1. Run: python oss_framework/scripts/run_week1_orchestrator.py")
            print("2. Or run: bash oss_framework/scripts/setup_week1_automated.sh")
            return True
        else:
            print(f"\n❌ {self.failed} check(s) failed. Please fix the issues above.")
            print("\nCommon fixes:")
            print("- Set missing environment variables in .env")
            print("- Install missing Python packages: pip install -r requirements.txt")
            print("- Verify file paths in .env are correct")
            return False


if __name__ == "__main__":
    validator = PreImplementationValidator()
    success = validator.run_all_checks()
    sys.exit(0 if success else 1)
