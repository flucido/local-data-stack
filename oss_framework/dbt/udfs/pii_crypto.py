"""DuckDB Python UDFs: AES-256-GCM encryption for PII fields.

Key management:
  - ``PII_ENCRYPTION_KEY`` must be at least 32 characters and not match any
    known example placeholder.
  - Derived via ``hashlib.scrypt`` (N=16384, r=8, p=1, dklen=32).
  - ``aes_decrypt_pii`` emits a structured ``PII_DECRYPT_AUDIT`` warning event
    whenever invoked and is only registered when ``LFED_ENABLE_PII_DECRYPT=1``.
"""

from __future__ import annotations

import base64
import functools
import getpass
import hashlib
import logging
import os
from datetime import UTC, datetime

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger(__name__)

_NONCE_BYTES = 12
_KDF_SALT = b"lfed_pii_aes256_kdf_v1"
_PLACEHOLDER_SECRETS = {
    "replace_with_your_secure_random_salt",
    "replace_with_your_encryption_key",
    "your_encryption_key_here",
    "your-secret-salt-here",
}


@functools.lru_cache(maxsize=8)
def _derive_key(secret: str) -> bytes:
    """Validate and stretch a secret into a 256-bit AES key using scrypt."""
    cleaned = secret.strip()
    if (
        len(cleaned) < 32
        or cleaned.lower() in _PLACEHOLDER_SECRETS
        or cleaned.lower().startswith("replace_with_")
    ):
        raise ValueError(
            "PII_ENCRYPTION_KEY must be at least 32 characters and must not use a placeholder value."
        )
    return hashlib.scrypt(
        cleaned.encode("utf-8"),
        salt=_KDF_SALT,
        n=16384,
        r=8,
        p=1,
        dklen=32,
    )


def _aes_key() -> bytes:
    """Read PII_ENCRYPTION_KEY from the environment and derive the AES-256 key."""
    secret = os.environ.get("PII_ENCRYPTION_KEY")
    if not secret:
        raise RuntimeError(
            "PII_ENCRYPTION_KEY environment variable is not set — refusing to "
            "process PII without an encryption key."
        )
    return _derive_key(secret)


def aes_encrypt_pii(value: str | None) -> str | None:
    """Encrypt a PII string with AES-256-GCM. Returns a base64 token or None."""
    if value is None:
        return None
    nonce = os.urandom(_NONCE_BYTES)
    ciphertext = AESGCM(_aes_key()).encrypt(nonce, str(value).encode("utf-8"), None)
    return base64.b64encode(nonce + ciphertext).decode("ascii")


def aes_decrypt_pii(token: str | None) -> str | None:
    """Decrypt a base64 AES-256-GCM token and emit a mandatory audit log entry."""
    if token is None:
        return None
    try:
        actor = getpass.getuser()
    except Exception:
        actor = "unknown"
    logger.warning(
        "PII_DECRYPT_AUDIT user=%s timestamp=%s",
        actor,
        datetime.now(UTC).isoformat(),
    )
    raw = base64.b64decode(token.encode("ascii"))
    nonce, ciphertext = raw[:_NONCE_BYTES], raw[_NONCE_BYTES:]
    return AESGCM(_aes_key()).decrypt(nonce, ciphertext, None).decode("utf-8")
