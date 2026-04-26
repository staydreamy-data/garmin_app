{% set start_date = var("start_date", run_started_at.strftime("%Y-%m-%d")) %}
{% set end_date = var("end_date", start_date) %}



{{ 
    config(
        materialized = 'incremental',
        unique_key = 'activity_id'
    )
}}
select
    tr.activity_id,
    tr.workout_id,
    tr.run_date,
    concat(
        'Total distance: ',
        cast(distance_km as varchar),
        ' km, time: ',
        cast(duration_min as varchar)
    ) as training_summary
from
    {{ ref('running_trainings') }} as tr
    {% if is_incremental() %}
        and tr.run_date >= date '{{ start_date }}'
        and tr.run_date <= date '{{ end_date }}'
    {% endif %}