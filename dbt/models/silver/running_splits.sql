{{ 
    config(
        materialized = 'incremental',
        unique_key = ['activity_id', 'message_index']
    )
}}

select
    s.activity_id,
    s.start_time_gmt,
    s.intensity_type,
    s.distance as distance_m,
    s.duration as duration_sec,
    s.average_speed as average_speed_kmh,
    s.average_hr,
    s.message_index,
    s.run_date,
    (s.distance / 1000) as distance_km,
    (s.duration / 60) as duration_min,
    (s.duration / 60) / (s.distance / 1000) as average_pace_min_per_km,
    (a.device_id is not null) as include_hr
from {{ ref('splits') }} as s
inner join {{ ref('running_activities') }} as a
    on s.activity_id = a.activity_id

{% if is_incremental() %}
    and s.run_date >= date '{{ start_date }}'
    and s.run_date <= date '{{ end_date }}'
{% endif %}