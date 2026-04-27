{% macro format_duration_from_seconds(seconds_expr) %}
    case
        when {{ seconds_expr }} is null or {{ seconds_expr }} < 0 then null
        else printf(
            '%d:%02d',
            cast(floor(round({{ seconds_expr }}) / 60) as integer),
            cast(mod(round({{ seconds_expr }}), 60) as integer)
        )
    end
{% endmacro %}
