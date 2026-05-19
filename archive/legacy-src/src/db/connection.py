import duckdb
from typing import Optional
import os

def get_connection(database_path: Optional[str] = None) -> duckdb.DuckDBPyConnection:
    """
    Get local DuckDB connection with Delta extension loaded.
    
    This is the primary connection method for local-data-stack. All data processing
    happens locally using DuckDB's embedded analytics engine.
    
    Args:
        database_path: Path to DuckDB database file. If None, uses environment
                      variable DUCKDB_DATABASE_PATH or defaults to
                      './oss_framework/data/oea.duckdb'
    
    Returns:
        duckdb.DuckDBPyConnection: Active DuckDB connection with Delta extension
    
    Example:
        >>> from src.db.connection import get_connection
        >>> conn = get_connection()
        >>> result = conn.execute('SELECT 1').fetchone()
        >>> print(result)
        (1,)
    """
    db_path = database_path or os.getenv(
        'DUCKDB_DATABASE_PATH',
        './oss_framework/data/oea.duckdb'
    )
    
    print(f"Connecting to local DuckDB at {db_path}...")
    conn = duckdb.connect(db_path)
    
    # Install and load Delta extension for Delta Lake support
    conn.execute("INSTALL delta")
    conn.execute("LOAD delta")
    
    # Load additional extensions for data processing
    conn.execute("INSTALL httpfs")  # For reading remote files if needed
    conn.execute("LOAD httpfs")
    conn.execute("INSTALL json")
    conn.execute("LOAD json")
    
    print(f"DuckDB connection established with Delta extension loaded.")
    return conn


