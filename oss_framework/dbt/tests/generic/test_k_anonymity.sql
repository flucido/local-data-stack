{% test k_anonymity(model, column_name=None, min_k=5, quasi_identifiers=None, k=5) %}

{% if column_name is not none %}
SELECT
    {{ column_name }} AS group_size,
    {{ min_k }} - {{ column_name }} AS deficit,
    'K-anonymity violation: cohort count ' || {{ column_name }} || ' is less than min_k=' || {{ min_k }} AS violation_message
FROM {{ model }}
WHERE {{ column_name }} IS NOT NULL
  AND {{ column_name }} < {{ min_k }}
{% else %}
WITH quasi_identifier_groups AS (
    SELECT
        {% for qi in quasi_identifiers %}
        {{ qi }}{{ "," if not loop.last else "" }}
        {% endfor %},
        COUNT(*) AS group_size
    FROM {{ model }}
    GROUP BY
        {% for qi in quasi_identifiers %}
        {{ qi }}{{ "," if not loop.last else "" }}
        {% endfor %}
),
violations AS (
    SELECT
        {% for qi in quasi_identifiers %}
        {{ qi }}{{ "," if not loop.last else "" }}
        {% endfor %},
        group_size,
        {{ k }} - group_size AS deficit
    FROM quasi_identifier_groups
    WHERE group_size < {{ k }}
)
SELECT
    *,
    'K-anonymity violation: group size ' || group_size || ' is less than k=' || {{ k }} AS violation_message
FROM violations
{% endif %}

{% endtest %}

{% test test_k_anonymity(model, column_name='student_count', min_k=5) %}
SELECT
    {{ column_name }} AS group_size,
    {{ min_k }} - {{ column_name }} AS deficit,
    'K-anonymity violation: cohort count ' || {{ column_name }} || ' is less than min_k=' || {{ min_k }} AS violation_message
FROM {{ model }}
WHERE {{ column_name }} IS NOT NULL
  AND {{ column_name }} < {{ min_k }}
{% endtest %}
