import duckdb
from .config_parser import parse_pipeline_config, ConfigError
from pathlib import Path
from dataclasses import asdict
from .contracts import LoadResult

DUCKDB_TYPE_MAP = {
    "string": "VARCHAR",
    "int64": "BIGINT",
    "float64": "DOUBLE",
    "boolean": "BOOLEAN",
}

METADATA_COLUMNS = [
    ("ingested_at", "TIMESTAMP"),
    ("ingestion_date", "DATE"),
    ("run_date", "DATE"),
    ("source_file", "VARCHAR"),
]

def _build_duckdb_columns(column_mapping: list) -> list[tuple[str, str]]:
    cols = [(c["target"], DUCKDB_TYPE_MAP[c["dtype"]]) for c in column_mapping]
    return cols + METADATA_COLUMNS


def append_to_bronze(run_date: str, asset_name: str, raw_config: dict) -> dict:
    config = parse_pipeline_config(raw_config)

    asset_config = config["assets"].get(asset_name)
    if not asset_config:
        raise ConfigError(f"Asset '{asset_name}' not found in raw_to_bronze.assets")

    table_name = asset_config["target"]["target_table"]
    schema_name = "bronze"

    stage_glob = f'{config["staging_path"]}/{asset_name}/dt={run_date}/*.parquet'

    db_file = Path(config["duckdb_path"])
    db_file.parent.mkdir(parents=True, exist_ok=True)

    duckdb_columns = _build_duckdb_columns(asset_config["column_mapping"])
    columns_ddl = ", ".join(f'"{name}" {dtype}' for name, dtype in duckdb_columns)
    column_names = ", ".join(f'"{name}"' for name, _ in duckdb_columns)

    with duckdb.connect(str(db_file)) as con:
        con.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"')
        con.execute(
            f'CREATE TABLE IF NOT EXISTS "{schema_name}"."{table_name}" ({columns_ddl})'
        )

        file_count = con.execute(
            "SELECT COUNT(*) FROM glob(?)", [stage_glob]
        ).fetchone()[0]
        if file_count == 0:
            return asdict(
                LoadResult(asset=asset_name, files_found=0, rows_loaded=0)
            )

        rows_loaded = con.execute(
            "SELECT COUNT(*) FROM read_parquet(?)", [stage_glob]
        ).fetchone()[0]

        con.execute(
            f'INSERT INTO "{schema_name}"."{table_name}" ({column_names}) '
            f"SELECT {column_names} FROM read_parquet(?)",
            [stage_glob],
        )

    return asdict(
        LoadResult(asset=asset_name, files_found=file_count, rows_loaded=rows_loaded)
    )