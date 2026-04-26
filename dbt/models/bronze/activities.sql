{{ 
    config(
        materialized = 'incremental',
        unique_key = 'activity_id'
    )
}}

select distinct *
from
    read_parquet(
        '{{ var("landing_root") }}/activities/dt=*/*.parquet',
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
