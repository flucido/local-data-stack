
{#
  Macro: hash_pii_secure
  
  Securely hashes PII using SHA256 (upgrade from MD5).
  Uses SHA-256 with a salt to create reproducible hashes
  that enable record linkage while protecting identity.
  
  Security Improvements:
  - SHA-256 instead of MD5 (256-bit vs 128-bit)
  - FIPS 140-2 aligned
  - Aligns with SmarterApp Consortium guidelines
  
  Args:
    column_name: The column to hash (e.g., 'student_id_raw')
    salt: Salt value from dbt var (defaults to 'oea_2026')
  
  Returns:
    VARCHAR - SHA256 hash as lowercase hexadecimal string (64 chars)
  
  Example:
    SELECT {{ hash_pii_secure('student_id_raw') }} FROM students
    SELECT {{ hash_pii_secure('email', 'custom_salt') }} FROM contacts
#}

{%- macro hash_pii_secure(column_name, salt=var('salt_pii', 'oea_2026')) -%}
    sha256(CONCAT('{{ salt }}', COALESCE({{ column_name }}::VARCHAR, '')))
{%- endmacro -%}

