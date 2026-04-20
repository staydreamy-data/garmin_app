select *
from {{ ref('running_splits') }} as s
inner join {{ ref('running_workouts') }} as w
    on s.workout_id = w.workout_id

