{% set start_date = var("start_date", run_started_at.strftime("%Y-%m-%d")) %}
{% set end_date = var("end_date", start_date) %}



{{ 
    config(
        materialized = 'incremental',
        unique_key = 'activity_id'
    )
}}

with base_derived_splits as (
    select
        activity_id,
        distance_km_bucket,
        concat( 
            cast(distance_km_bucket as varchar),
            ' km: ',
            cast(split_pace as varchar),
            ' pace.'
        ) as split_summary
    from {{ ref('running_derived_splits') }}
    where
        1 = 1
        {% if is_incremental() %}
            and run_date >= date '{{ start_date }}'
            and run_date <= date '{{ end_date }}'
        {% endif %}
),

derived_splits_summary as (
    select
        activity_id,
        string_agg(split_summary, chr(10) order by distance_km_bucket)
            as full_summary
    from base_derived_splits
    group by activity_id
)

select
    tr.activity_id,
    tr.run_date,
    ds.full_summary,
    tr.training_summary
from derived_splits_summary as ds
inner join {{ ref('running_trainings_summary') }} as tr
    on tr.activity_id = ds.activity_id
where
    tr.workout_id is null
