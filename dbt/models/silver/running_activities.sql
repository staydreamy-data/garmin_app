select 
  activity_id,
  start_time_gmt,
  distance,
  distance as distance_m,
  duration as duration_sec,
  (duration / 60) as duration_min,
  (distance / 1000) as distance_km,
  average_speed as average_speed_kmh,
  (duration / distance * 60) as average_pace_min_per_km,
  average_hr,
  has_splits,
  device_id,
  run_date,
  from {{ ref('activities') }}
where activity_type = 'running'