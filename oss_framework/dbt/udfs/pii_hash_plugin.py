"""dbt-duckdb plugin: registers the HMAC-SHA256 PII hash UDF on connection.

Used by the ``hash_pii`` / ``hash_pii_secure`` dbt macros so every hashed
identifier in the warehouse is a true HMAC-SHA256 digest (secret salt as HMAC
key), matching ``scripts/anonymize_aeries.py``.
"""

from typing import Any

from dbt.adapters.duckdb.credentials import DuckDBCredentials
from dbt.adapters.duckdb.plugins import BasePlugin
from duckdb import DuckDBPyConnection
from pii_hash import pii_hmac_sha256


class Plugin(BasePlugin):
    """Registers the ``pii_hmac_sha256`` scalar UDF."""

    def __init__(
        self,
        name: str,
        plugin_config: dict[str, Any],
        credentials: DuckDBCredentials | None = None,
    ):
        super().__init__(name=name, plugin_config=plugin_config, credentials=credentials)

    def configure_connection(self, conn: DuckDBPyConnection):
        conn.create_function(
            "pii_hmac_sha256",
            pii_hmac_sha256,
            [str, str],
            str,
            null_handling="special",
        )
