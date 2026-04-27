{{ 
    config(
        materialized = 'incremental',
        unique_key = 'workout_id'
    )
}}

select distinct *
from
    read_parquet(
        '{{ var("landing_root") }}/workouts/dt=*/*.parquet',
        hive_partitioning = true,
        union_by_name = true
    )
where
    1 = 1
    {% if is_incremental() %}
        and dt
        >= (
            select max(dt) - interval '{{ var("lookback_days") }} day'
            from {{ this }}
        )
    {% endif %}
qualify row_number() over (partition by workout_id order by run_date desc) = 1
