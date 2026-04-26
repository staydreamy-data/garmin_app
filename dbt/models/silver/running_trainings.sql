{{ 
    config(
        materialized = 'incremental',
        unique_key = 'activity_id'
    )
}}

select
    activity_id,
    start_time_gmt,
    distance as distance_m,
    round(distance / 1000, 2) as distance_km,
    duration as duration_sec,
    {{ format_duration_from_seconds('duration') }} as duration_min,
    average_speed as average_speed_ms,
    average_hr,
    has_splits,
    device_id,
    workout_id,
    run_date,
    {{ format_pace_from_speed('average_speed') }} as training_pace,
    (device_id is not null) as include_hr
from {{ ref('activities') }}
where
    activity_type = 'running'
    {% if is_incremental() %}
        and run_date
        >= (
            select max(run_date) - interval '{{ var("lookback_days") }} day'
            from {{ this }}
        )
    {% endif %}
