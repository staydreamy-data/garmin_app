with workouts as (
    select *
    from {{ ref('running_workouts') }}
),

repeat_rows as (
    -- Find each repeat block and the next repeat step in the same workout.
    -- The next repeat step acts as the end boundary of the current repeat block.
    select
        w.workout_id,
        w.workout_name,
        w.step_order as repeat_step_order,
        w.number_of_iterations,
        min(n.step_order) as next_repeat_step_order
    from workouts w
    left join workouts n
        on n.workout_id = w.workout_id
       and n.step_type = 'repeat'
       and n.step_order > w.step_order
    where w.step_type = 'repeat'
    group by 1, 2, 3, 4
),

repeat_blocks as (
    -- Collect the steps that belong to each repeat block.
    -- We assume steps after the repeat row belong to that block
    -- until the next repeat row starts.
    select
        r.workout_id,
        r.workout_name,
        r.repeat_step_order,
        r.number_of_iterations,

        max(case when s.step_type = 'interval' then s.target_distance_m end) as interval_distance_m,
        max(case when s.step_type = 'interval' then s.target_time_sec end) as interval_time_sec,
        max(case when s.step_type = 'interval' then s.target_pace_lower_range end) as interval_pace_lower_range,
        max(case when s.step_type = 'interval' then s.target_pace_upper_range end) as interval_pace_upper_range,

        max(case when s.step_type = 'recovery' then s.target_distance_m end) as recovery_distance_m,
        max(case when s.step_type = 'recovery' then s.target_time_sec end) as recovery_time_sec
    from repeat_rows r
    left join workouts s
        on s.workout_id = r.workout_id
       and s.step_order > r.repeat_step_order
       and (
            r.next_repeat_step_order is null
            or s.step_order < r.next_repeat_step_order
       )
       and s.step_type in ('interval', 'recovery')
    group by 1, 2, 3, 4
)

-- Build a readable description for each repeat block.
select
    workout_id,
    workout_name,
    repeat_step_order,
    number_of_iterations,
    interval_distance_m,
    recovery_distance_m,
    interval_pace_lower_range,
    interval_pace_upper_range,
    concat(
        cast(number_of_iterations as varchar),
        ' x ',
        cast(cast(interval_distance_m as integer) as varchar),
        'm',
        case
            when recovery_distance_m is not null then
                concat(
                    ' with ',
                    cast(cast(recovery_distance_m as integer) as varchar),
                    'm recovery'
                )
            when recovery_time_sec is not null then
                concat(
                    ' with ',
                    cast(cast(recovery_time_sec as integer) as varchar),
                    's recovery'
                )
            else ''
        end,
        case
            when interval_pace_lower_range is not null
             and interval_pace_upper_range is not null then
                concat(
                    ' @ ',
                    interval_pace_lower_range,
                    '-',
                    interval_pace_upper_range
                )
            else ''
        end
    ) as repeat_description
from repeat_blocks
order by workout_id, repeat_step_order
