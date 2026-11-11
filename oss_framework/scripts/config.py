"""Configuration for OSS Framework"""

import os
from pathlib import Path

# SIS connector — which Student Information System to pull from
SIS_CONNECTOR = os.getenv("SIS_CONNECTOR", "csv")

# Aeries Configuration (used when SIS_CONNECTOR=aeries)
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
DUCKDB_DATABASE_PATH = os.getenv("DUCKDB_DATABASE_PATH", "./oss_framework/data/analytics.duckdb")
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
EXCEL_DEMOGRAPHIC_UPDATE_FREQUENCY = os.getenv("EXCEL_DEMOGRAPHIC_UPDATE_FREQUENCY", "static")
EXCEL_RFEP_UPDATE_FREQUENCY = os.getenv("EXCEL_RFEP_UPDATE_FREQUENCY", "monthly")

# Data Retention
DATA_RETENTION_YEARS = int(os.getenv("DATA_RETENTION_YEARS", 5))
ARCHIVE_GRADUATED_STUDENTS = os.getenv("ARCHIVE_GRADUATED_STUDENTS", "true").lower() == "true"

# Pseudonymization
PSEUDONYMIZATION_LEVEL = os.getenv("PSEUDONYMIZATION_LEVEL", "full")
AUDIT_LOGGING_ENABLED = os.getenv("AUDIT_LOGGING_ENABLED", "true").lower() == "true"

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", "./oss_framework/logs/oea.log")

# Create log directory if it doesn't exist
Path(LOG_FILE).parent.mkdir(parents=True, exist_ok=True)


_PLACEHOLDER_SALTS = {
    "replace_with_your_secure_random_salt",
    "default_oss_framework_salt",
    "your-secret-salt-here",
    "your-secret-salt-here-do-not-commit",
    "oea_2026",
}


def validate_config(require_aeries: bool = True):
    """Validate that required configuration and privacy salts are set.

    Set require_aeries=False for local/sample runs that do not contact Aeries.
    """
    errors = []

    pii_salt = (os.getenv("PII_SALT") or "").strip()
    if (
        not pii_salt
        or len(pii_salt) < 16
        or pii_salt.lower() in _PLACEHOLDER_SALTS
        or pii_salt.lower().startswith("replace_with_")
    ):
        errors.append(
            "PII_SALT must be set to a random secret >= 16 characters and not a placeholder"
        )

    if require_aeries:
        if AERIES_AUTH_METHOD == "api_key" and not AERIES_API_KEY:
            errors.append("AERIES_API_KEY not set")

        if AERIES_AUTH_METHOD == "oauth2" and (not AERIES_CLIENT_ID or not AERIES_CLIENT_SECRET):
            errors.append("AERIES_CLIENT_ID or AERIES_CLIENT_SECRET not set")

        if AERIES_AUTH_METHOD == "database" and not all([AERIES_DB_HOST, AERIES_DB_DATABASE]):
            errors.append("Database configuration incomplete")

    if errors:
        raise ValueError(f"Configuration errors: {', '.join(errors)}")

    return True


def purge_expired_records(conn, retention_years: int | None = None) -> int:
    """Purge withdrawn student records older than ``retention_years`` across tables.

    Returns the total number of rows deleted.
    """
    years = int(retention_years if retention_years is not None else DATA_RETENTION_YEARS)
    if years < 1:
        raise ValueError("retention_years must be >= 1")

    candidate_cols = conn.execute(
        """
        SELECT table_schema, table_name
        FROM information_schema.columns
        WHERE column_name = 'withdrawal_date'
          AND table_schema NOT IN ('information_schema', 'pg_catalog')
        """
    ).fetchall()

    total_deleted = 0
    for schema_name, table_name in candidate_cols:
        tbl_type = conn.execute(
            """
            SELECT table_type
            FROM information_schema.tables
            WHERE table_schema = ? AND table_name = ?
            """,
            [schema_name, table_name],
        ).fetchone()
        if not tbl_type or tbl_type[0] != "BASE TABLE":
            continue
        q_schema = f'"{str(schema_name).replace(chr(34), chr(34) * 2)}"'
        q_table = f'"{str(table_name).replace(chr(34), chr(34) * 2)}"'
        before = conn.execute(f"SELECT COUNT(*) FROM {q_schema}.{q_table}").fetchone()[0]
        conn.execute(
            f"DELETE FROM {q_schema}.{q_table} "
            f"WHERE TRY_CAST(withdrawal_date AS DATE) IS NOT NULL "
            f"AND TRY_CAST(withdrawal_date AS DATE) < CURRENT_DATE - INTERVAL '{years} years'"
        )
        after = conn.execute(f"SELECT COUNT(*) FROM {q_schema}.{q_table}").fetchone()[0]
        total_deleted += max(0, int(before) - int(after))

    return total_deleted


if __name__ == "__main__":
    print("Current Configuration:")
    print(f"  Aeries Auth: {AERIES_AUTH_METHOD}")
    print(f"  DuckDB: {DUCKDB_DATABASE_PATH}")
    print(f"  Stage1: {STAGE1_PATH}")
    print(f"  Stage2: {STAGE2_PATH}")
    print(f"  Stage3: {STAGE3_PATH}")
    print(f"  Data Retention: {DATA_RETENTION_YEARS} years")
