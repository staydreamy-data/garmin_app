select 
    a.activity_id,
    a.run_date,
    a.distance_m,
    a.duration_sec,
    {{ format_pace_from_speed('a.average_speed') }} as average_pace
from {{ ref('running_trainings') }} as a
