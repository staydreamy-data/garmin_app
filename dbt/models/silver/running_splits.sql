{% set start_date = var("start_date", run_started_at.strftime("%Y-%m-%d")) %}
{% set end_date = var("end_date", start_date) %}


{{ 
    config(
        materialized = 'incremental',
        unique_key = ['activity_id', 'split_index']
    )
}}

select
    s.activity_id,
    s.start_time_gmt,
    lower(s.intensity_type) as step_type,
    s.distance as distance_m,
    s.duration as duration_sec,
    s.average_speed as average_speed_ms,
    s.average_hr,
    s.message_index as split_index,
    a.workout_id,
    s.workout_step_index,
    s.run_date,
    {{ format_pace_from_speed('s.average_speed') }} as split_pace,
    a.include_hr
from {{ ref('splits') }} as s
inner join {{ ref('running_trainings') }} as a
    on
        s.activity_id = a.activity_id

        {% if is_incremental() %}
            and s.run_date >= date '{{ start_date }}'
            and s.run_date <= date '{{ end_date }}'
        {% endif %}
