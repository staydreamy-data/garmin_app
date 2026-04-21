select 
s.activity_id,
s.run_date,
s.workout_id,
w.workout_name,
s.distance_m,
s.duration_sec,
case when s.include_hr then s.average_hr else null end as average_hr,
s.split_index,
s.split_pace,
w.step_order,
w.step_type,
w.target_goal,
w.target_distance_m,
w.target_time_sec,
w.target_pace_lower_range,
w.target_pace_upper_range,
from {{ ref('running_splits') }} as s
inner join {{ ref('running_workouts') }} as w
    on s.workout_id = w.workout_id
    and s.workout_step_index = w.garmin_step_index
where 
1 = 1
{% if is_incremental() %}
    and s.run_date >= date '{{ start_date }}'
    and s.run_date <= date '{{ end_date }}'
{% endif %}