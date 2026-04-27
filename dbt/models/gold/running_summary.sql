select * from {{ ref('running_workout_results_summary') }}
union all
select * from {{ ref('running_derived_splits_summary') }}
