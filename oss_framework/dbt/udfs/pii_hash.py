"""DuckDB Python UDF: HMAC-SHA256 pseudonymization hash for PII fields.

Mirrors ``scripts/anonymize_aeries.py``: HMAC-SHA256 (RFC 2104) with the
secret salt used as the HMAC key, producing a 64-character lowercase hex
digest. Every warehouse hash column produced by the ``hash_pii`` /
``hash_pii_secure`` dbt macros goes through this UDF, so all join paths share
one scheme and one salt.

Key management:
  - The salt must be at least 16 characters and must not match a known
    placeholder; the UDF **fails fast** otherwise (same posture as
    ``Pseudonymizer`` and ``anonymize_aeries._require_env_salt``).
  - dbt macros pass ``var('salt_pii')``, sourced from the ``PII_SALT`` env
    var, so every hashed identifier is reproducible per deployment.
  - To hash interoperably with ``anonymize_aeries.py``, set
    ``LFED_STUDENT_SALT``/``LFED_STAFF_SALT`` to the same ``PII_SALT`` value.

Value normalization (documented divergence from ``anonymize_aeries.py``):
  - NULL values hash as the empty string (constant digest), matching the
    prior ``sha256(CONCAT(COALESCE(col, ''), salt))`` linkage semantics so
    joins that relied on the old behavior remain reproducible.
  - Values are NOT whitespace-stripped; ``anonymize_aeries.py`` strips and
    maps blank values to ``""`` — feed it already-stripped identifiers if
    cross-scheme equality matters.
"""

from __future__ import annotations

import hashlib
import hmac

_PLACEHOLDER_SALTS = {
    "replace_with_your_secure_random_salt",
    "replace_with_your_aeries_api_key",
    "your_encryption_key_here",
    "your-secret-salt-here",
    "your-secret-salt-here-do-not-commit",
    "default_oss_framework_salt",
    "oea_2026",
}


def pii_hmac_sha256(value: str | None, salt: str) -> str:
    """Return the HMAC-SHA256 hex digest of ``value`` using ``salt`` as key.

    Raises ``ValueError`` when the salt is shorter than 16 characters or is a
    known placeholder, so a misconfigured deployment fails closed instead of
    silently producing weakly-salted hashes.
    """
    if (
        len(salt) < 16
        or salt.lower() in _PLACEHOLDER_SALTS
        or salt.lower().startswith("replace_with_")
    ):
        raise ValueError(
            "PII salt must be at least 16 characters and must not use a placeholder value."
        )
    return hmac.new(
        salt.encode("utf-8"),
        (value or "").encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
