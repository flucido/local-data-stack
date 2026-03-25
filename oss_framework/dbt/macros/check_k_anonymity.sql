
{#
  Macro: check_k_anonymity
  
  Validates k-anonymity by finding groups with fewer than k records.
  Used to ensure FERPA compliance (k >= 5 for educational data).
  
  K-anonymity protects against re-identification by ensuring every
  combination of quasi-identifiers appears in at least k records.
  
  Args:
    model_name: The model/table to check (string, not ref())
    quasi_identifiers: List of column names that are quasi-identifiers
    k_threshold: Minimum group size (default: 5 for FERPA)
  
  Returns:
    Rows where group_size < k_threshold (violations)
    Empty result = k-anonymity is satisfied
  
  Quasi-Identifiers for Educational Data:
  - Demographics: grade_level, gender, ethnicity, age
  - Geographic: school_id, zip_code_prefix
  - Special populations: special_education_flag, ell_status
  
  Example Usage:
    {{ check_k_anonymity('dim_student_demographics', 
                         ['grade_level', 'gender', 'ethnicity'],
                         5) }}
  
  Returns columns:
    - All quasi-identifier values
    - group_size (number of records in this combination)
    
  Use in dbt tests:
    {% test k_anonymity(model, quasi_identifiers, k=5) %}
        {{ check_k_anonymity(model, quasi_identifiers, k) }}
    {% endtest %}
#}

{%- macro check_k_anonymity(model_name, quasi_identifiers, k_threshold=5) -%}
    SELECT
        {% for qi in quasi_identifiers %}
        {{ qi }}{{ "," if not loop.last else "" }}
        {% endfor %},
        COUNT(*) as group_size
    FROM {{ ref(model_name) }}
    GROUP BY 
        {% for qi in quasi_identifiers %}
        {{ qi }}{{ "," if not loop.last else "" }}
        {% endfor %}
    HAVING COUNT(*) < {{ k_threshold }}
{%- endmacro -%}

