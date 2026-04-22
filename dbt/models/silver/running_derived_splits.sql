{{ 
    config(
        materialized = 'incremental',
        unique_key = ['activity_id', 'distance_km_bucket']
    )
}}

with bucketing as (
select 
*,
cast(floor(distance_m / 1000) as integer) + 1 as distance_km_bucket
from {{ ref('running_activity_details') }}

    {% if is_incremental() %}
        and d.run_date >= date '{{ start_date }}'
        and d.run_date <= date '{{ end_date }}'
    {% endif %}
),

grouped_by_bucket as (select 
activity_id,
run_date,
distance_km_bucket,
max(duration_sec) as duration_sec,
avg(speed_mps) as speed_mps,
avg(heart_rate_bpm) as heart_rate_bpm
from bucketing
group by activity_id, run_date, distance_km_bucket
)

select *,
{{format_duration_from_seconds('duration_sec')}} as split_duration_min,
{{format_pace_from_speed('speed_mps')}} as split_pace
from
grouped_by_bucket
