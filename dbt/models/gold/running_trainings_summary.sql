{{ 
    config(
        materialized = 'incremental',
        unique_key = 'activity_id'
    )
}}
select
    tr.activity_id,
    tr.workout_id,
    tr.run_date::DATE as run_date,
    concat(
        'Total distance: ',
        cast(distance_km as varchar),
        ' km, time: ',
        cast(duration_min as varchar)
    ) as training_summary
from
    {{ ref('running_trainings') }} as tr
where
    1 = 1
    {% if is_incremental() %}
        and tr.run_date >= (
            select max(run_date) - interval '{{ var("lookback_days") }} day'
            from {{ this }}
        )
    {% endif %}
