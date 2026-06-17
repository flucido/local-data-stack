"""Shared pytest fixtures for the nl_query NL→SQL layer.

The `db` fixture opens a read-only connection to the unified warehouse
(data/warehouse.duckdb, or the existing oss_framework analytics DB as a
fallback). Tests that need it are skipped when no warehouse is present, so
the suite still runs on a clean checkout before the pipeline has been built.
"""

import sys
from pathlib import Path

# Ensure the nl_query package root is importable as flat modules
# (data_engine, prompts, model_inference, ui_strings).
PACKAGE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PACKAGE_ROOT))

import pytest
from data_engine import create_session, get_warehouse_path


def warehouse_available() -> bool:
    return get_warehouse_path().exists()


@pytest.fixture
def db():
    """Read-only warehouse connection for each test (skips if absent)."""
    if not warehouse_available():
        pytest.skip(f"No warehouse at {get_warehouse_path()} — run the pipeline first.")
    conn = create_session()
    yield conn
    conn.close()
