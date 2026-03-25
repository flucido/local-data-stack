
{#
  Macro: mask_email
  
  Masks email addresses while preserving structure for validation.
  Shows first 2 characters of local part and domain, masks the rest.
  
  Args:
    column_name: The email column to mask
  
  Returns:
    VARCHAR - Masked email preserving @ symbol
  
  Examples:
    "student@school.edu" -> "st*****@sc******"
    "john.doe@university.org" -> "jo**********@un**********"
    "invalid-email" -> "*************" (no @ found)
    NULL -> NULL
    
  Use Cases:
  - Displaying email domains for validation
  - Audit logs where structure matters
  - Data quality checks
#}

{%- macro mask_email(column_name) -%}
    CASE 
        WHEN {{ column_name }} IS NULL THEN NULL
        WHEN {{ column_name }} NOT LIKE '%@%' THEN REPEAT('*', LENGTH({{ column_name }}))
        ELSE CONCAT(
            SUBSTRING({{ column_name }}, 1, 2),
            REPEAT('*', LENGTH(SPLIT_PART({{ column_name }}, '@', 1)) - 2),
            '@',
            SUBSTRING(SPLIT_PART({{ column_name }}, '@', 2), 1, 2),
            REPEAT('*', LENGTH(SPLIT_PART({{ column_name }}, '@', 2)) - 2)
        )
    END
{%- endmacro -%}

