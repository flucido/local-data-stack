"""SIS Connector module — vendor-neutral ingestion abstraction.

Usage:
    from oss_framework.connectors import get_sis_connector

    connector = get_sis_connector("aeries", test_mode=True)
    for student in connector.get_students():
        print(student["student_id"])

Environment:
    Set SIS_CONNECTOR to the connector name (aeries, powerschool, csv, etc.).
    Falls back to "aeries" when unset.
"""

import importlib
import os
from typing import Optional

from oss_framework.connectors.base import SISConnector


_CONNECTOR_REGISTRY = {
    "aeries": "oss_framework.connectors.aeries",
}


def get_sis_connector(
    name: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    test_mode: Optional[bool] = None,
    **kwargs,
) -> SISConnector:
    """Factory: return a SISConnector instance by name.

    Args:
        name: Connector name (e.g. 'aeries', 'csv').  Defaults to the
              SIS_CONNECTOR environment variable, falling back to 'aeries'.
        base_url: API base URL (connector-specific).
        api_key: API key or token (connector-specific).
        test_mode: Force synthetic-data mode.
        **kwargs: Forwarded to the connector constructor.

    Returns:
        A concrete SISConnector instance.

    Raises:
        ValueError: If the connector name is unknown.
    """
    name = name or os.getenv("SIS_CONNECTOR", "aeries")

    module_path = _CONNECTOR_REGISTRY.get(name)
    if module_path is None:
        raise ValueError(
            f"Unknown SIS connector '{name}'. "
            f"Available connectors: {', '.join(sorted(_CONNECTOR_REGISTRY))}"
        )

    module = importlib.import_module(module_path)
    factory = getattr(module, "create_connector")
    return factory(
        base_url=base_url,
        api_key=api_key,
        test_mode=test_mode,
        **kwargs,
    )
