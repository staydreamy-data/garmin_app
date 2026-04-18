{{ 
    config(
        materialized = 'incremental',
        unique_key = ['activity_id', 'measurement_index']
    )
}}


with base as (
    select
        d.activity_id,
        d.measurement_index,
        d.metric_key,
        d.metric_value
    from {{ ref('activity_details') }} as d
    inner join {{ ref('running_activities') }} as a
        on d.activity_id = a.activity_id
    where
        d.metric_key in (
            'directTimestamp',
            'sumDistance',
            'sumDuration',
            'sumElapsedDuration',
            'sumMovingDuration',
            'directSpeed',
            'directHeartRate'
        )
),

pivoted as (
    select *
    from base
    pivot (
        max(metric_value)
        for metric_key in (
            'directTimestamp',
            'sumDistance',
            'sumDuration',
            'sumElapsedDuration',
            'sumMovingDuration',
            'directSpeed',
            'directHeartRate'
        )
    )
)

select
    activity_id,
    measurement_index,
    directtimestamp as timestamp_raw,
    sumdistance as distance_m,
    sumduration as duration_sec,
    sumelapsedduration as elapsed_duration_sec,
    summovingduration as moving_duration_sec,
    directspeed as speed_mps,
    directheartrate as heart_rate_bpm,
    (summovingduration / 60 ) / sumdistance * 1000 as pace_min_per_km

from pivoted
