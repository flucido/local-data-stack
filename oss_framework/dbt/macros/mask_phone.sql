
{#
  Macro: mask_phone
  
  Masks phone numbers by showing first 6 characters and replacing
  the rest with asterisks. Works with various phone formats.
  
  Args:
    column_name: The phone number column to mask
  
  Returns:
    VARCHAR - Masked phone number
  
  Examples:
    "555-123-4567" -> "555-12****"
    "(555) 123-4567" -> "(555) ****"
    "5551234567" -> "555123****"
    "123" -> "***" (too short, fully masked)
    NULL -> NULL
    
  Logic:
  - Extracts digits only to check length
  - If >= 10 digits (valid phone): shows first 6 chars
  - If < 10 digits (invalid): fully masks
#}

{%- macro mask_phone(column_name) -%}
    CASE 
        WHEN {{ column_name }} IS NULL THEN NULL
        WHEN LENGTH(REGEXP_REPLACE({{ column_name }}, '[^0-9]', '', 'g')) >= 10
            THEN CONCAT(SUBSTRING({{ column_name }}, 1, 6), '****')
        ELSE REPEAT('*', LENGTH({{ column_name }}))
    END
{%- endmacro -%}

