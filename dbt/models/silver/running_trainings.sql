{% set start_date = var("start_date", run_started_at.strftime("%Y-%m-%d")) %}
{% set end_date = var("end_date", start_date) %}

{{ 
    config(
        materialized = 'incremental',
        unique_key = 'activity_id'
    )
}}

select
    activity_id,
    start_time_gmt,
    distance,
    distance as distance_m,
    duration as duration_sec,
    average_speed as average_speed_ms,
    average_hr,
    has_splits,
    device_id,
    workout_id,
    run_date,
    {{format_pace_from_speed('average_speed')}} as training_pace,
    (device_id is not null) as include_hr
from {{ ref('activities') }}
where activity_type = 'running'
{% if is_incremental() %}
    and run_date >= date '{{ start_date }}'
    and run_date <= date '{{ end_date }}'
{% endif %}