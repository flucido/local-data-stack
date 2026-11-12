
{#
  Macro: hash_pii_secure

  Securely hashes PII using HMAC-SHA256 (RFC 2104) with the secret salt as
  the HMAC key, producing reproducible hashes that enable record linkage
  while protecting identity. Implemented via the ``pii_hmac_sha256`` UDF
  (udfs/pii_hash.py, registered by pii_hash_plugin) so the dbt layer matches
  scripts/anonymize_aeries.py exactly.

  Security Improvements:
  - HMAC-SHA256 instead of plain salted SHA-256 or MD5 (256-bit, keyless-
    forgery resistant: the salt is never revealed by the digest)
  - Salt must be >= 16 characters and non-placeholder (UDF fails closed)
  - FIPS 140-2 aligned; aligns with SmarterApp Consortium guidelines

  Args:
    column_name: The column to hash (e.g., 'student_id_raw')
    salt: Salt value from dbt var (defaults to var('salt_pii'), sourced from
      the PII_SALT environment variable)

  Returns:
    VARCHAR - HMAC-SHA256 hash as lowercase hexadecimal string (64 chars)

  Example:
    SELECT {{ hash_pii_secure('student_id_raw') }} FROM students
    SELECT {{ hash_pii_secure('email', 'custom_salt') }} FROM contacts
#}

{%- macro hash_pii_secure(column_name, salt=var('salt_pii')) -%}
    pii_hmac_sha256(COALESCE({{ column_name }}::VARCHAR, ''), '{{ salt }}')
{%- endmacro -%}
