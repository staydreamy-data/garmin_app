select 
    a.activity_id,
    a.run_date,
    a.distance_km,
    a.duration_min,
    {{ format_pace_min_per_km('a.average_pace_min_per_km') }} as average_pace_min_per_km    
from {{ ref('running_activities') }} as a
