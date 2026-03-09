{% test is_greater_or_equal_to_zero(model, column_name) %}

    SELECT *
    FROM {{ model }}
    WHERE {{ column_name }} < 0

{% endtest %}