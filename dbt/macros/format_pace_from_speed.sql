{% macro format_pace_from_speed(speed_mps_expr) %}
    case
        when {{ speed_mps_expr }} is null or {{ speed_mps_expr }} <= 0 then null
        else printf(
            '%d:%02d',
            cast(floor(round(1000.0 / {{ speed_mps_expr }}) / 60) as integer),
            cast(mod(round(1000.0 / {{ speed_mps_expr }}), 60) as integer)
        )
    end
{% endmacro %}
