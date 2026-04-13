with base as (select
	d.activity_id,
  d.measurement_index,
  d.metric_key,
  d.metric_value
from {{ ref('activity_details') }} d
    inner join {{ ref('running_activities') }} a
        on d.activity_id = a.activity_id
   where d.metric_key in (
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
"directTimestamp" as timestamp_raw,
"sumDistance" as distance_m,
"sumDuration" as duration_sec,
"sumElapsedDuration" as elapsed_duration_sec,
"sumMovingDuration" as moving_duration_sec,
"directSpeed" as speed_mps,
"sumMovingDuration" / "sumDistance" * 1000 as pace_min_per_km,
"directHeartRate" as heart_rate_bpm

from pivoted