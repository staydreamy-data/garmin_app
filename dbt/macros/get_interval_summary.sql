{% macro get_interval_summary(interval_name, distance_km, pace_min_per_km, average_hr, include_hr) -%}
'{{ interval_name }}' || ': ' || {{ distance_km }} || ' km with pace ' || {{ pace_min_per_km }} || ' min/km' || case
            when {{ include_hr }} then ' and avg HR ' || {{ average_hr }}
            else ''
            end

{%- endmacro %}
