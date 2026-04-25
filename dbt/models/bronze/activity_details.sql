{% set start_date = var("start_date", run_started_at.strftime("%Y-%m-%d")) %}
{% set end_date = var("end_date", start_date) %}

{{ 
    config(
        materialized = 'incremental',
        unique_key = ['activity_id', 'measurement_index', 'metric_index']
    )
}}

select distinct *
from
    read_parquet(
        '{{ var("landing_root") }}/activity_details/dt=*/*.parquet',
        hive_partitioning = true,
        union_by_name = true
    )
where
    1 = 1
    {% if is_incremental() %}
        and dt >= date '{{ start_date }}'
        and dt <= date '{{ end_date }}'
    {% endif %}
