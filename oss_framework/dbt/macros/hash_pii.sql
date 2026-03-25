
{#
  Macro: hash_pii
  
  Deterministically hashes PII for pseudonymization.
  Uses MD5 with a salt to create reproducible hashes
  that enable record linkage while protecting identity.
  
  Args:
    column_name: The column to hash (e.g., 'student_id')
    salt: Optional salt value (defaults to 'oea_2026')
  
  Returns:
    VARCHAR - MD5 hash of column + salt
  
  Example:
    SELECT {{ hash_pii('student_id') }} FROM students
    SELECT {{ hash_pii('email', 'custom_salt') }} FROM contacts
#}

{%- macro hash_pii(column_name, salt=var('salt_pii', 'oea_2026')) -%}
    MD5(CONCAT(COALESCE({{ column_name }}::VARCHAR, ''), '{{ salt }}'))
{%- endmacro -%}

