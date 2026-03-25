#!/usr/bin/env python3
"""
DuckDB Production Configuration Module

Provides production-optimized DuckDB connections with proper memory management,
thread control, and performance tuning.

Usage:
    from oss_framework.config.duckdb_config import get_production_connection

    conn = get_production_connection('path/to/database.duckdb')
    # Use conn for queries...
    conn.close()

Based on production best practices:
- Memory limit at 90% (prevents OS lockups)
- Thread count = physical cores only
- Explicit temp directory for spill operations
- WAL checkpointing enabled
"""

import os
from pathlib import Path
from typing import Optional
import duckdb
import logging

logger = logging.getLogger(__name__)


def get_production_connection(
    db_path: str,
    memory_limit: Optional[str] = None,
    threads: Optional[int] = None,
    temp_directory: Optional[str] = None,
    read_only: bool = False,
) -> duckdb.DuckDBPyConnection:
    """
    Get DuckDB connection with production-optimized settings.

    Args:
        db_path: Path to DuckDB database file
        memory_limit: Memory limit (e.g., '4GB', '90%'). Default: '90%'
        threads: Number of threads. Default: CPU physical cores
        temp_directory: Temp spill directory. Default: /tmp/duckdb_temp
        read_only: Open in read-only mode (for analytics queries)

    Returns:
        Configured DuckDB connection

    Example:
        >>> conn = get_production_connection('analytics.duckdb')
        >>> df = conn.execute("SELECT * FROM students").fetchdf()
        >>> conn.close()
    """
    # Connect to database
    conn = duckdb.connect(db_path, read_only=read_only)

    # Memory management (90% to prevent OS lockups)
    if memory_limit is None:
        memory_limit = os.getenv("DUCKDB_MEMORY_LIMIT", "90%")
    conn.execute(f"SET memory_limit = '{memory_limit}'")
    logger.info(f"DuckDB memory_limit set to: {memory_limit}")

    # Thread optimization (physical cores only)
    if threads is None:
        cpu_count = os.cpu_count() or 4
        # Use physical cores (assume hyperthreading = 2x logical cores)
        threads = max(1, cpu_count // 2)
    conn.execute(f"SET threads = {threads}")
    logger.info(f"DuckDB threads set to: {threads}")

    # Temp spill directory
    if temp_directory is None:
        temp_directory = os.getenv("DUCKDB_TEMP_DIR", "/tmp/duckdb_temp")

    # Ensure temp directory exists
    Path(temp_directory).mkdir(parents=True, exist_ok=True)
    conn.execute(f"SET temp_directory = '{temp_directory}'")
    logger.info(f"DuckDB temp_directory set to: {temp_directory}")

    # WAL checkpointing for durability
    conn.execute("PRAGMA wal_autocheckpoint=1000")

    # Enable object cache for frequently accessed objects
    conn.execute("SET enable_object_cache = true")

    # Preserve insertion order (can improve query performance)
    conn.execute("SET preserve_insertion_order = true")

    # HTTP settings for remote data (S3/GCS)
    conn.execute("SET http_timeout = 60000")  # 60 seconds
    conn.execute("SET http_retries = 3")

    # Enable parallel CSV reading
    conn.execute("SET experimental_parallel_csv = true")

    logger.info(f"DuckDB connection established: {db_path} (read_only={read_only})")

    return conn


def apply_query_profiling(conn: duckdb.DuckDBPyConnection) -> None:
    """
    Enable query profiling for performance debugging.

    Args:
        conn: DuckDB connection

    Example:
        >>> conn = get_production_connection('analytics.duckdb')
        >>> apply_query_profiling(conn)
        >>> conn.execute("SELECT * FROM large_table")
        >>> show_last_profile(conn)
    """
    conn.execute("SET enable_profiling = 'query_tree'")
    logger.info("Query profiling enabled (use PRAGMA show_last_profile)")


def show_last_profile(conn: duckdb.DuckDBPyConnection) -> None:
    """
    Display profiling information for the last executed query.

    Args:
        conn: DuckDB connection
    """
    result = conn.execute("PRAGMA show_last_profile").fetchall()
    print("\n=== Query Profile ===")
    for row in result:
        print(row[0])
    print("===================\n")


def get_connection_info(conn: duckdb.DuckDBPyConnection) -> dict:
    """
    Get current DuckDB connection configuration.

    Args:
        conn: DuckDB connection

    Returns:
        Dictionary with configuration settings

    Example:
        >>> conn = get_production_connection('analytics.duckdb')
        >>> info = get_connection_info(conn)
        >>> print(f"Memory limit: {info['memory_limit']}")
    """
    return {
        "memory_limit": conn.execute("SELECT current_setting('memory_limit')").fetchone()[0],
        "threads": conn.execute("SELECT current_setting('threads')").fetchone()[0],
        "temp_directory": conn.execute("SELECT current_setting('temp_directory')").fetchone()[0],
        "object_cache": conn.execute("SELECT current_setting('enable_object_cache')").fetchone()[0],
        "preserve_order": conn.execute(
            "SELECT current_setting('preserve_insertion_order')"
        ).fetchone()[0],
    }


# Example usage and testing
if __name__ == "__main__":
    import tempfile

    # Setup logging
    logging.basicConfig(level=logging.INFO)

    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix=".duckdb", delete=False) as tmp:
        db_path = tmp.name

    print("Creating production DuckDB connection...")
    conn = get_production_connection(db_path)

    # Display configuration
    print("\nConnection Configuration:")
    info = get_connection_info(conn)
    for key, value in info.items():
        print(f"  {key}: {value}")

    # Test query
    print("\nRunning test query...")
    conn.execute("CREATE TABLE test AS SELECT range as id FROM range(1000)")
    result = conn.execute("SELECT COUNT(*) FROM test").fetchone()
    print(f"  Result: {result[0]} rows")

    # Enable profiling
    print("\nEnabling query profiling...")
    apply_query_profiling(conn)
    conn.execute("SELECT * FROM test WHERE id > 500")
    show_last_profile(conn)

    # Cleanup
    conn.close()
    os.unlink(db_path)
    print("✅ Test completed successfully")
