{{ 
    config(
        materialized = 'incremental',
        unique_key = ['workout_id', 'step_order']
    )
}}

with workouts as (
    select
        workout_id,
        workout_name,
        cast(workout_segments as json) as workout_segments_json
    from {{ ref('workouts') }}
),

segments as (
    select
        w.workout_id,
        w.workout_name,
        cast(s.value ->> '$.segmentOrder' as integer) as segment_order,
        s.value as segment_json
    from workouts as w,
        json_each(w.workout_segments_json) as s
),

top_level_steps as (
    select
        s.workout_id,
        s.workout_name,
        -- Subtract 1 from step order to align with splits
        cast(ws.value ->> '$.stepOrder' as integer) as step_order,
        cast(ws.value ->> '$.stepType.stepTypeKey' as varchar) as step_type,
        cast(ws.value ->> '$.numberOfIterations' as integer)
            as number_of_iterations,
        cast(ws.value ->> '$.endCondition.conditionTypeKey' as varchar)
            as end_condition_type_key,
        cast(ws.value ->> '$.endConditionValue' as double)
            as end_condition_value,
        cast(ws.value ->> '$.targetType.workoutTargetTypeKey' as string)
            as target_type,
        cast(ws.value ->> '$.targetValueOne' as double) as target_value_one,
        cast(ws.value ->> '$.targetValueTwo' as double) as target_value_two,
        cast(ws.value ->> '$.workoutSteps' as json) as nested_workout_steps,
        false as is_nested_step,
        ws.value ->> '$.type' as step_dto_type,
        ws.value ->> '$.stepType.stepTypeKey' as step_type_key
    from segments as s,
        json_each(s.segment_json, '$.workoutSteps') as ws
),

nested_steps as (
    select
        s.workout_id,
        s.workout_name,
        -- Subtract 1 from step order to align with splits
        cast(ns.value ->> '$.stepOrder' as integer) as step_order,
        cast(ns.value ->> '$.stepType.stepTypeKey' as varchar) as step_type,
        cast(ns.value ->> '$.endCondition.conditionTypeKey' as varchar)
            as end_condition_type_key,
        cast(ns.value ->> '$.endConditionValue' as double)
            as end_condition_value,
        cast(ns.value ->> '$.targetType.workoutTargetTypeKey' as string)
            as target_type,
        cast(ns.value ->> '$.targetValueOne' as double) as target_value_one,
        cast(ns.value ->> '$.targetValueTwo' as double) as target_value_two,
        true as is_nested_step,
        ns.value ->> '$.type' as step_dto_type,
        ns.value ->> '$.stepType.stepTypeKey' as step_type_key
    from top_level_steps as s,
        json_each(nested_workout_steps) as ns
    where s.step_dto_type = 'RepeatGroupDTO'
),

all_steps as (
    select
        workout_id,
        workout_name,
        step_order,
        number_of_iterations,
        step_dto_type,
        step_type,
        end_condition_type_key,
        end_condition_value,
        target_type,
        target_value_one,
        target_value_two,
        is_nested_step
    from top_level_steps

    union all

    select
        workout_id,
        workout_name,
        step_order,
        null as number_of_iterations,
        step_dto_type,
        step_type,
        end_condition_type_key,
        end_condition_value,
        target_type,
        target_value_one,
        target_value_two,
        is_nested_step
    from nested_steps
),

enriched_targets as (
    select
        *,
        end_condition_type_key as target_goal,
        case
            when end_condition_type_key = 'distance' then end_condition_value
        end as target_distance_m,
        case
            when end_condition_type_key = 'time' then end_condition_value
        end as target_time_sec,
        case
            when
                target_type = 'pace.zone'
                then {{ format_pace_from_speed('target_value_one') }}
            else null
        end as target_pace_lower_range,
        case
            when
                target_type = 'pace.zone'
                then {{ format_pace_from_speed('target_value_two') }}
            else null
        end as target_pace_upper_range
    from all_steps
),

indexed as (
    select
        *,
        row_number() over (
            partition by workout_id
            order by step_order
        ) - 1 as flattened_row_number_all,
        case
            when
                step_dto_type = 'ExecutableStepDTO' and is_nested_step = false
                then step_order - 1
            when
                step_dto_type = 'ExecutableStepDTO' and is_nested_step = true
                then step_order - 2
        end as garmin_step_index
    from enriched_targets
)

select
    workout_id,
    workout_name,
    step_order,
    number_of_iterations,
    step_type,
    target_goal,
    target_distance_m,
    target_time_sec,
    target_pace_lower_range,
    target_pace_upper_range,
    garmin_step_index
from indexed
