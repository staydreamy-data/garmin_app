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
        d.metric_value,
        d.run_date
    from {{ ref('activity_details') }} as d
    inner join {{ ref('running_trainings') }} as a
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

        {% if is_incremental() %}

            and d.run_date
            >= (
                select max(run_date) - interval '{{ var("lookback_days") }} day'
                from {{ this }}
            )
        {% endif %}
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
    run_date,
    directtimestamp as timestamp_raw,
    sumdistance as distance_m,
    sumduration as duration_sec,
    sumelapsedduration as elapsed_duration_sec,
    summovingduration as moving_duration_sec,
    directspeed as speed_mps,
    directheartrate as heart_rate_bpm

from pivoted
