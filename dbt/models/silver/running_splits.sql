select
    s.activity_id,
    s.start_time_gmt,
    s.intensity_type,
    s.distance as distance_m,
    (s.distance / 1000) as distance_km,
    s.duration as duration_sec,
    (s.duration / 60) as duration_min,
    s.average_speed as average_speed_kmh,
    (s.duration / s.distance * 60) as average_pace_min_per_km,
    s.average_hr,
    s.message_index,
    s.run_date
from {{ ref('splits') }} as s
inner join {{ ref('running_activities') }} as a
    on s.activity_id = a.activity_id
