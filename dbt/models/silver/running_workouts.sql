{{ 
    config(
        materialized = 'incremental',
        unique_key = ['workout_id', 'step_id']
    )
}}

with workouts as (
    select
        workout_id,
        cast(workout_segments as json) as workout_segments_json
    from {{ ref('workouts') }}
),

segments as (
    select
        w.workout_id,
        cast(s.value ->> '$.segmentOrder' as integer) as segment_order,
        s.value as segment_json
    from workouts w,
    json_each(w.workout_segments_json) as s
),

segment_steps as (
    select
        s.workout_id,
        cast(ws.value ->> '$.stepId' as bigint) as step_id,
        cast(ws.value ->> '$.stepOrder' as integer) as step_order,
        cast(ws.value ->> '$.stepType.stepTypeKey' as varchar) as step_type,
        ws.value ->> '$.type' as step_dto_type,
        ws.value ->> '$.stepType.stepTypeKey' as step_type_key, 
        cast(ws.value ->> '$.endCondition.conditionTypeKey' as varchar) as end_condition_type_key,
        cast(ws.value ->> '$.endConditionValue' as double) as end_condition_value,
        cast(ws.value ->> '$.workoutSteps' as json) as nested_workout_steps
    from segments s,
    json_each(s.segment_json, '$.workoutSteps') as ws
),

nested_segment_steps as 
(select 
        s.workout_id,
        cast(ns.value ->> '$.stepId' as bigint) as step_id,
        cast(ns.value ->> '$.stepOrder' as integer) as step_order,
        cast(ns.value ->> '$.stepType.stepTypeKey' as varchar) as step_type,
        ns.value ->> '$.type' as step_dto_type,
        ns.value ->> '$.stepType.stepTypeKey' as step_type_key,
        cast(ns.value ->> '$.endCondition.conditionTypeKey' as varchar) as end_condition_type_key,
        cast(ns.value ->> '$.endConditionValue' as double) as end_condition_value

    from segment_steps s,
    json_each(nested_workout_steps) as ns
)

select * exclude(nested_workout_steps) from segment_steps
union all
select * from nested_segment_steps
