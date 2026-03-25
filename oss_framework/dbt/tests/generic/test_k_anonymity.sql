
{% test k_anonymity(model, quasi_identifiers, k=5) %}

WITH quasi_identifier_groups AS (
    SELECT
        {% for qi in quasi_identifiers %}
        {{ qi }}{{ "," if not loop.last else "" }}
        {% endfor %},
        COUNT(*) as group_size
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
        {{ k }} - group_size as deficit
    FROM quasi_identifier_groups
    WHERE group_size < {{ k }}
)
SELECT
    *,
    'K-anonymity violation: group size ' || group_size || ' is less than k=' || {{ k }} as violation_message
FROM violations

{% endtest %}

