{% macro format_pace_min_per_km(pace_expr) -%}
case
    when {{ pace_expr }} is null then null
    else
        cast(cast(floor({{ pace_expr }}) as bigint) as varchar)
        || ':'
        || cast(cast(({{ pace_expr }} - floor({{ pace_expr }})) * 60 as bigint) as varchar)
end
{%- endmacro %}
