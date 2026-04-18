{% set start_date = var("start_date", run_started_at.strftime("%Y-%m-%d")) %}
{% set end_date = var("end_date", start_date) %}

{{ 
    config(
        materialized = 'incremental',
        unique_key = 'workout_id'
    )
}}

select distinct *
from read_parquet(
  '{{ var("landing_root") }}/workouts/dt=*/*.parquet',
  hive_partitioning = true,
  union_by_name = true
)
where
1 = 1 
{% if is_incremental() %}
    and dt >= date '{{ start_date }}'
    and dt <= date '{{ end_date }}'
{% endif %}
qualify row_number() over (partition by workout_id order by run_date desc) = 1