### How to open my duckdb file in ui
duckdb -ui /workspaces/garmin_app/astro/include/data/duckdb/garmin_db.duckdb
### Raw to landing output
Validated parquet is kept under `astro/include/data/landing/<asset>/dt=<YYYY-MM-DD>/<asset>.parquet` for dbt/DuckDB to consume later.
### To run tests again after container reloading:
uv sync --extra airflow-tests --cache-dir .uv-cache
