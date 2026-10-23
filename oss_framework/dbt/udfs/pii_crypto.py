"""DuckDB Python UDFs: AES-256-GCM encryption for PII fields.

Registered via the ``udfs:`` section of ``profiles.yml`` (dbt-duckdb) so SQL
models can call ``aes_encrypt_pii(value)`` / ``aes_decrypt_pii(token)``.

Key management:
  - The master secret is read from the ``PII_ENCRYPTION_KEY`` environment
    variable and stretched to a 256-bit key with SHA-256.
  - The UDFs fail fast when the key is absent: PII must never be written in
    plaintext just because the environment was misconfigured.

Wire format: ``base64(nonce[12] || ciphertext || tag[16])`` — AES-256-GCM
provides authenticated encryption, so tampering is detected on decrypt.
"""

from __future__ import annotations

import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_NONCE_BYTES = 12


def _aes_key() -> bytes:
    """Derive the AES-256 key from the PII_ENCRYPTION_KEY secret."""
    secret = os.environ.get("PII_ENCRYPTION_KEY")
    if not secret:
        raise RuntimeError(
            "PII_ENCRYPTION_KEY environment variable is not set — refusing to "
            "process PII without an encryption key."
        )
    return hashlib.sha256(secret.encode("utf-8")).digest()


def aes_encrypt_pii(value: str) -> str:
    """Encrypt a PII string with AES-256-GCM. Returns a base64 token or None."""
    if value is None:
        return None
    nonce = os.urandom(_NONCE_BYTES)
    ciphertext = AESGCM(_aes_key()).encrypt(nonce, str(value).encode("utf-8"), None)
    return base64.b64encode(nonce + ciphertext).decode("ascii")


def aes_decrypt_pii(token: str) -> str:
    """Decrypt a base64 AES-256-GCM token produced by aes_encrypt_pii."""
    if token is None:
        return None
    raw = base64.b64decode(token.encode("ascii"))
    nonce, ciphertext = raw[:_NONCE_BYTES], raw[_NONCE_BYTES:]
    return AESGCM(_aes_key()).decrypt(nonce, ciphertext, None).decode("utf-8")
