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
    average_speed as average_speed_kmh,
    average_hr,
    has_splits,
    device_id,
    run_date,
    (duration / 60) as duration_min,
    (distance / 1000) as distance_km,
    (duration / 60) / (distance / 1000) as average_pace_min_per_km
from {{ ref('activities') }}
where activity_type = 'running'
