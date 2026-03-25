
{#
  Macro: mask_address
  
  Completely redacts address fields for maximum privacy protection.
  Unlike other masking functions, this provides zero information
  about the original address.
  
  Args:
    column_name: The address column to mask
  
  Returns:
    VARCHAR - Fixed redaction string or NULL
  
  Examples:
    "123 Main Street" -> "***REDACTED***"
    "Apt 4B, 789 Oak Ave" -> "***REDACTED***"
    NULL -> NULL
    
  Rationale:
  - Street addresses are highly identifying (quasi-identifier)
  - Even partial addresses can enable re-identification
  - FERPA requires complete suppression for small populations
  - Use ZIP code prefix (3 digits) for geographic analysis instead
#}

{%- macro mask_address(column_name) -%}
    CASE 
        WHEN {{ column_name }} IS NULL THEN NULL
        ELSE '***REDACTED***'
    END
{%- endmacro -%}

