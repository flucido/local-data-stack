"""Configuration for OSS Framework"""

import os
from pathlib import Path

# Aeries Configuration
AERIES_API_URL = os.getenv("AERIES_API_URL", "https://api.aeries.com/v5")
AERIES_API_KEY = os.getenv("AERIES_API_KEY")
AERIES_CLIENT_ID = os.getenv("AERIES_CLIENT_ID")
AERIES_CLIENT_SECRET = os.getenv("AERIES_CLIENT_SECRET")
AERIES_AUTH_METHOD = os.getenv("AERIES_AUTH_METHOD", "api_key")

# Database Configuration
AERIES_DB_HOST = os.getenv("AERIES_DB_HOST")
AERIES_DB_PORT = os.getenv("AERIES_DB_PORT", 1433)
AERIES_DB_DATABASE = os.getenv("AERIES_DB_DATABASE")
AERIES_DB_USERNAME = os.getenv("AERIES_DB_USERNAME")
AERIES_DB_PASSWORD = os.getenv("AERIES_DB_PASSWORD")

# DuckDB Configuration
DUCKDB_DATABASE_PATH = os.getenv(
    "DUCKDB_DATABASE_PATH", "./oss_framework/data/oea.duckdb"
)
DUCKDB_MEMORY_LIMIT = os.getenv("DUCKDB_MEMORY_LIMIT", "8GB")

# Data Lake Paths
STAGE1_PATH = Path(os.getenv("STAGE1_PATH", "./oss_framework/data/stage1"))
STAGE2_PATH = Path(os.getenv("STAGE2_PATH", "./oss_framework/data/stage2"))
STAGE3_PATH = Path(os.getenv("STAGE3_PATH", "./oss_framework/data/stage3"))

# Excel Report Paths
EXCEL_DF_REPORT_PATH = os.getenv("EXCEL_DF_REPORT_PATH")
EXCEL_DEMOGRAPHIC_PATH = os.getenv("EXCEL_DEMOGRAPHIC_PATH")
EXCEL_RFEP_PATH = os.getenv("EXCEL_RFEP_PATH")

# Update Frequencies
EXCEL_DF_UPDATE_FREQUENCY = os.getenv("EXCEL_DF_UPDATE_FREQUENCY", "weekly")
EXCEL_DEMOGRAPHIC_UPDATE_FREQUENCY = os.getenv(
    "EXCEL_DEMOGRAPHIC_UPDATE_FREQUENCY", "static"
)
EXCEL_RFEP_UPDATE_FREQUENCY = os.getenv("EXCEL_RFEP_UPDATE_FREQUENCY", "monthly")

# Data Retention
DATA_RETENTION_YEARS = int(os.getenv("DATA_RETENTION_YEARS", 5))
ARCHIVE_GRADUATED_STUDENTS = (
    os.getenv("ARCHIVE_GRADUATED_STUDENTS", "true").lower() == "true"
)

# Pseudonymization
PSEUDONYMIZATION_LEVEL = os.getenv("PSEUDONYMIZATION_LEVEL", "full")
AUDIT_LOGGING_ENABLED = os.getenv("AUDIT_LOGGING_ENABLED", "true").lower() == "true"

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", "./oss_framework/logs/oea.log")

# Create log directory if it doesn't exist
Path(LOG_FILE).parent.mkdir(parents=True, exist_ok=True)


def validate_config(require_aeries: bool = True):
    """Validate that required configuration is set.

    Set require_aeries=False for local/sample runs that do not contact Aeries.
    """
    errors = []

    if require_aeries:
        if AERIES_AUTH_METHOD == "api_key" and not AERIES_API_KEY:
            errors.append("AERIES_API_KEY not set")

        if AERIES_AUTH_METHOD == "oauth2" and (
            not AERIES_CLIENT_ID or not AERIES_CLIENT_SECRET
        ):
            errors.append("AERIES_CLIENT_ID or AERIES_CLIENT_SECRET not set")

        if AERIES_AUTH_METHOD == "database" and not all(
            [AERIES_DB_HOST, AERIES_DB_DATABASE]
        ):
            errors.append("Database configuration incomplete")

    if errors:
        raise ValueError(f"Configuration errors: {', '.join(errors)}")

    return True


if __name__ == "__main__":
    print("Current Configuration:")
    print(f"  Aeries Auth: {AERIES_AUTH_METHOD}")
    print(f"  DuckDB: {DUCKDB_DATABASE_PATH}")
    print(f"  Stage1: {STAGE1_PATH}")
    print(f"  Stage2: {STAGE2_PATH}")
    print(f"  Stage3: {STAGE3_PATH}")
    print(f"  Data Retention: {DATA_RETENTION_YEARS} years")
