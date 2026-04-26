{{ 
    config(
        materialized = 'incremental',
        unique_key = ['activity_id', 'distance_km_bucket']
    )
}}

with base as (
select 
*,
cast(ceil(distance_m / 1000) as integer) as distance_km_bucket
from {{ ref('running_activity_details') }}
where distance_m > 0 and speed_mps > 0
    {% if is_incremental() %}
        and d.run_date >= date '{{ start_date }}'
        and d.run_date <= date '{{ end_date }}'
    {% endif %}
),

bucket_endpoints as (
    select *
    from (
        select
            *,
            row_number() over (
                partition by activity_id, distance_km_bucket
                order by measurement_index desc
            ) as rn
        from base
    )
    where rn = 1
),

bucket_aggregates as (
    select
        activity_id,
        distance_km_bucket,
        avg(speed_mps) as avg_speed_mps,
        avg(heart_rate_bpm) as avg_heart_rate_bpm
    from base
    group by activity_id, distance_km_bucket
),

bucket_last_values as (
    select
        e.activity_id,
        e.distance_km_bucket,
        e.moving_duration_sec
            - coalesce(lag(e.moving_duration_sec) over (
                partition by e.activity_id
                order by e.distance_km_bucket
              ), 0) as split_duration_sec
    from bucket_endpoints e
)

select
    s.activity_id,
    s.distance_km_bucket,
    s.split_duration_sec,
    a.avg_speed_mps,
    a.avg_heart_rate_bpm,
    {{format_duration_from_seconds('s.split_duration_sec')}} as split_duration_min,
    {{format_pace_from_speed('a.avg_speed_mps')}} as split_pace
from bucket_last_values s
left join bucket_aggregates a
    on s.activity_id = a.activity_id
   and s.distance_km_bucket = a.distance_km_bucket