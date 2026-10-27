"""dbt-duckdb plugin: registers AES-256-GCM PII crypto UDFs on every connection.

dbt-duckdb 1.10 has no ``udfs:`` profile key; Python UDFs are registered via
the plugin API. Enabled in ``profiles.yml`` with:

    module_paths:
      - udfs
    plugins:
      - module: pii_crypto_plugin

The actual crypto lives in ``pii_crypto.py`` (shared with any non-dbt callers).
"""

from typing import Any

from dbt.adapters.duckdb.credentials import DuckDBCredentials
from dbt.adapters.duckdb.plugins import BasePlugin
from duckdb import DuckDBPyConnection
from pii_crypto import aes_decrypt_pii, aes_encrypt_pii


class Plugin(BasePlugin):
    """Registers aes_encrypt_pii / aes_decrypt_pii scalar UDFs on connect."""

    def __init__(
        self,
        name: str,
        plugin_config: dict[str, Any],
        credentials: DuckDBCredentials | None = None,
    ):
        super().__init__(name=name, plugin_config=plugin_config, credentials=credentials)

    def configure_connection(self, conn: DuckDBPyConnection):
        conn.create_function(
            "aes_encrypt_pii",
            aes_encrypt_pii,
            [str],
            str,
            null_handling="special",
        )
        conn.create_function(
            "aes_decrypt_pii",
            aes_decrypt_pii,
            [str],
            str,
            null_handling="special",
        )
