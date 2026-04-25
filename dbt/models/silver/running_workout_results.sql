{% set start_date = var("start_date", run_started_at.strftime("%Y-%m-%d")) %}
{% set end_date = var("end_date", start_date) %}

{{ 
    config(
        materialized = 'incremental',
        unique_key = ['activity_id', 'split_index']
    )
}}

with running_splits_batch as (
    select * from {{ ref('running_splits') }}
    where 
1 = 1
{% if is_incremental() %}
    and run_date >= date '{{ start_date }}'
    and run_date <= date '{{ end_date }}'
{% endif %}
),


warmup_cooldown as (
    select
        activity_id,
        workout_id,
        run_date,
        step_type,
        workout_step_index,
        avg(average_speed_ms) as average_speed_ms,
        max(split_index) as split_index,
        sum(duration_sec) as duration_sec,
        sum(distance_m) as distance_m,
        avg(average_hr) as average_hr
    from running_splits_batch
    where step_type in ('warmup', 'cooldown')
    group by activity_id, workout_id, run_date, step_type, workout_step_index
),

intervals as (select 
s.activity_id,
s.run_date,
s.workout_id,
w.workout_name,
s.distance_m,
s.duration_sec,
s.split_index,
s.split_pace,
s.workout_step_index,
w.step_type,
w.target_goal,
w.target_distance_m,
w.target_time_sec,
w.target_pace_lower_range,
w.target_pace_upper_range,
s.average_hr
from running_splits_batch as s
inner join {{ ref('running_workouts') }} as w
    on s.workout_id = w.workout_id
    and s.workout_step_index = w.garmin_step_index
where s.step_type not in ('warmup', 'cooldown')
),

splits_union as (select
    activity_id,
    workout_id,
    run_date,
    (select distinct workout_name from {{ ref('running_workouts') }} where workout_id = w.workout_id) as workout_name,
    distance_m,
    duration_sec,
    case when step_type = 'warmup' then 0 else split_index end as split_index,
    {{format_pace_from_speed('average_speed_ms')}} as split_pace,
    case when step_type = 'warmup' then 0 else workout_step_index end as workout_step_index,
    step_type,
    null::varchar as target_goal,
    null::double as target_distance_m,
    null::double as target_time_sec,
    null::varchar as target_pace_lower_range,
    null::varchar as target_pace_upper_range,
    average_hr
from warmup_cooldown w

union all

select
    activity_id,
    workout_id,
    run_date,
    workout_name,
    distance_m,
    duration_sec,
    split_index,
    split_pace,
    workout_step_index,
    step_type,
    target_goal,
    target_distance_m,
    target_time_sec,
    target_pace_lower_range,
    target_pace_upper_range,
    average_hr
from intervals
)

select
    activity_id,
    workout_id,
    run_date,
    workout_name,
    distance_m,
    round(distance_m / 1000, 2) as distance_km,
    duration_sec,
    {{format_duration_from_seconds('duration_sec')}} as duration_min,
    split_index,
    split_pace,
    workout_step_index,
    step_type,
    target_goal,
    target_distance_m,
    round(target_distance_m / 1000, 2) as target_distance_km,
    target_time_sec,
    {{format_duration_from_seconds('target_time_sec')}} as target_time_min,
    target_pace_lower_range,
    target_pace_upper_range,
    average_hr
from splits_union

--case when s.include_hr then s.average_hr else null end as average_hr,