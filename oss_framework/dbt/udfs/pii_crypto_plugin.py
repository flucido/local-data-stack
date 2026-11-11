"""dbt-duckdb plugin: registers AES-256-GCM PII crypto UDFs on connection.

During standard dbt builds, only ``aes_encrypt_pii`` is registered.
Break-glass ``aes_decrypt_pii`` registration requires ``LFED_ENABLE_PII_DECRYPT=1``.
"""

import os
from typing import Any

from dbt.adapters.duckdb.credentials import DuckDBCredentials
from dbt.adapters.duckdb.plugins import BasePlugin
from duckdb import DuckDBPyConnection
from pii_crypto import aes_decrypt_pii, aes_encrypt_pii


class Plugin(BasePlugin):
    """Registers aes_encrypt_pii (and break-glass aes_decrypt_pii) scalar UDFs."""

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
        if os.environ.get("LFED_ENABLE_PII_DECRYPT") == "1":
            conn.create_function(
                "aes_decrypt_pii",
                aes_decrypt_pii,
                [str],
                str,
                null_handling="special",
            )
