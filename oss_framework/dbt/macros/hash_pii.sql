
{#
  Macro: hash_pii

  Deterministically hashes PII for pseudonymization.
  Uses SHA-256 with a salt to create reproducible hashes
  that enable record linkage while protecting identity.

  Security Improvements:
  - Upgraded from MD5 to SHA-256 (256-bit vs 128-bit)
  - FIPS 140-2 aligned
  - Aligns with SmarterApp Consortium guidelines

  Args:
    column_name: The column to hash (e.g., 'student_id')
    salt: Salt value from dbt var (defaults to var('salt_pii'))

  Returns:
    VARCHAR - SHA-256 hash as lowercase hexadecimal string (64 chars)

  Example:
    SELECT {{ hash_pii('student_id') }} FROM students
    SELECT {{ hash_pii('email', 'custom_salt') }} FROM contacts
#}

{%- macro hash_pii(column_name, salt=var('salt_pii')) -%}
    sha256(CONCAT(COALESCE({{ column_name }}::VARCHAR, ''), '{{ salt }}'))
{%- endmacro -%}
