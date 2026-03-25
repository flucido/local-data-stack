
{#
  Macro: mask_name
  
  Masks name fields by showing only the first N characters and replacing
  the rest with asterisks. Provides irreversible PII suppression while
  maintaining some readability for data validation.
  
  Args:
    column_name: The name column to mask (e.g., 'first_name_raw')
    visible_chars: Number of characters to show (default: 1)
  
  Returns:
    VARCHAR - Masked name (e.g., "Johnson" -> "J******")
  
  Examples:
    {{ mask_name('first_name_raw') }} -- Shows 1 char
    {{ mask_name('last_name_raw', 2) }} -- Shows 2 chars
    
  Output examples:
    "Maria" -> "M****" (visible_chars=1)
    "Johnson" -> "Jo*****" (visible_chars=2)
#}

{%- macro mask_name(column_name, visible_chars=1) -%}
    CASE 
        WHEN {{ column_name }} IS NULL THEN NULL
        WHEN LENGTH({{ column_name }}) <= {{ visible_chars }} THEN REPEAT('*', LENGTH({{ column_name }}))
        ELSE CONCAT(
            SUBSTRING({{ column_name }}, 1, {{ visible_chars }}),
            REPEAT('*', LENGTH({{ column_name }}) - {{ visible_chars }})
        )
    END
{%- endmacro -%}

