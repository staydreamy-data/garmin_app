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
            ' pace, ', cast(split_duration_min as varchar), ' duration.'
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
    concat(
        'Total distance: ',
        cast(distance_km as varchar),
        ' km, time: ',
        cast(duration_min as varchar)
    ) as training_summary
from
    {{ ref('running_trainings') }} as tr
inner join derived_splits_summary as ds
    on tr.activity_id = ds.activity_id
where
    tr.workout_id is null
    {% if is_incremental() %}
        and tr.run_date >= date '{{ start_date }}'
        and tr.run_date <= date '{{ end_date }}'
    {% endif %}
