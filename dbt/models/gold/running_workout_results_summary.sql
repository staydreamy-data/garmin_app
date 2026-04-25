{{ 
    config(
        materialized = 'incremental',
        unique_key = 'activity_id'
    )
}}


with workout_split_summary as (
select
    *,
    case
        when step_type = 'warmup' then
            concat(
                'Warmup: ',
                cast(round(distance_m / 1000.0, 2) as varchar), ' km for ',
                split_pace
            )

        when step_type = 'cooldown' then
            concat(
                'Cooldown: ',
                cast(round(distance_m / 1000.0, 2) as varchar), ' km for ',
                split_pace
            )

        when step_type = 'interval' then
            concat(
                'pace ',
                split_pace, ', distance: ', cast(distance_km as varchar), ' km.'
            )

        else null
    end as split_summary
from {{ ref('running_workout_results') }}
where 1 = 1
    {% if is_incremental() %}
        and run_date >= date '{{ start_date }}'
        and run_date <= date '{{ end_date }}'
    {% endif %}
),

workout_step_summary as 
(select 
activity_id,
workout_id,
run_date,
case 
when target_goal is not null then 
concat(                
'Target: ',
                case
                    when target_goal = 'time' then concat(target_time_min, ' min')
                    when target_goal = 'distance' then concat(cast(target_distance_km as varchar), ' km')
                    else ' NULL '
                end,
                case
                    when target_pace_lower_range is not null
                     and target_pace_upper_range is not null
                    then concat(
                        ' (target pace ',
                        target_pace_lower_range,
                        ' - ',
                        target_pace_upper_range,
                        ')'
                    )
                    else ''
                end)
                else ''
end
as target_summary,
concat(
case when target_goal is not null
then chr(10) || 'Actual: ' || chr(10)
else ''
end,

 string_agg(split_summary, chr(10) order by split_index) 
)  as interval_summary,

workout_step_index
from workout_split_summary
group by activity_id,workout_id,run_date,workout_step_index, target_goal,target_time_min,target_distance_km,
target_pace_lower_range, target_pace_upper_range

)


select 
activity_id,
workout_id,
run_date,
string_agg(
concat(target_summary, interval_summary)

, chr(10) || chr(10) order by workout_step_index) as activity_summary
from workout_step_summary
group by activity_id,workout_id,run_date