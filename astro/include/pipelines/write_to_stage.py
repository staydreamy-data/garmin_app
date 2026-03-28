from pathlib import Path
import json
import logging
from typing import Iterator
import polars as pl
import pandera.polars as pa
import duckdb
from datetime import datetime
from include.pipelines.validation import get_pandera_schema, validate_dataframe

DUCKDB_TYPE_MAP = {
    "string": "VARCHAR",
    "int64": "BIGINT",
    "float64": "DOUBLE",
    "boolean": "BOOLEAN",
}

DUCKDB_METADATA_COLUMNS = [
    {"name": "ingested_at", "duckdb_type": "TIMESTAMP"},
    {"name": "ingestion_date", "duckdb_type": "DATE"},
    {"name": "source_file", "duckdb_type": "VARCHAR"},
]

def iter_source_files(source_path: str, file_mask: str) -> Iterator[Path]:
    for p in sorted(Path(source_path).glob(file_mask)):
        if p.is_file():
            yield p

def map_raw_to_staged(records: list, columns_mapping: dict) -> list:

    mapped_records = []
    for record in records:

        mapped_record = {}
        for column_mapping in columns_mapping:
            source_split = column_mapping["source"].split(".")
            target_column = column_mapping["target"]
            source_column_value = record.get(source_split[0])
            for i in range(1, len(source_split)):
                source_column_value = source_column_value.get(source_split[i])
            # if source_column_value:
            mapped_record[target_column] = source_column_value
        mapped_records.append(mapped_record)

    return mapped_records

def resolve_raw_data(raw_data: dict | list, resolve_config: dict):
    if resolve_config["payload_kind"] == "object":
        return raw_data[resolve_config["records_path"]]
    elif resolve_config["payload_kind"] == "list":
        return raw_data

def get_duckdb_columns_from_mapping(column_mapping: list[dict]) -> list[tuple[str, str]]:
    columns = []
    for column in column_mapping:
        target = column["target"]
        dtype = column["dtype"]
        duckdb_type = DUCKDB_TYPE_MAP[dtype]
        columns.append((target, duckdb_type))
    return columns


def model_duckdb_bronze_columns(column_mapping: list[dict]) -> list[tuple[str, str]]:
    source_columns = [(column["target"], DUCKDB_TYPE_MAP[column["dtype"]]) for column in column_mapping]
    metadata_columns = [(column["name"], column["duckdb_type"]) for column in DUCKDB_METADATA_COLUMNS]
    return source_columns + metadata_columns

def list_files_in_folder(folder_path: str, extension: str) -> list[Path]:
    base = Path(folder_path)
    if not base.exists():
        return []

    ext = extension if extension.startswith(".") else f".{extension}"
    pattern = f"*{ext}"

    files = [p for p in base.glob(pattern) if p.is_file()]
    return sorted(files, key=lambda p: p.name, reverse=True)

def duckdb_append_files_to_table(duckdb_path: str, schema_name: str, table_name: str, parquet_files_path: str, column_mapping: list):
    logging.info(f"Writing raw data for {table_name} from {parquet_files_path} to {duckdb_path}")

    db_file = Path(duckdb_path)
    db_file.parent.mkdir(parents=True, exist_ok=True)

    duckdb_columns = model_duckdb_bronze_columns(column_mapping=column_mapping)
    with duckdb.connect(str(db_file)) as con:
        
        columns_ddl = ", ".join(f'"{n}" {t}' for n, t in duckdb_columns)
        column_names = ", ".join(f'"{n}"' for n, _ in duckdb_columns)

        con.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"')

        logging.info(f"Loading the files from {parquet_files_path}")

        latest_parquet_file = con.execute("""
            SELECT max(file) AS filename
            FROM glob(?)
        """, [f"{parquet_files_path}/*.parquet"]).fetchone()[0]
        logging.info(f"Loading the file from {latest_parquet_file}")

        con.execute(f'CREATE TABLE IF NOT EXISTS "{schema_name}"."{table_name}" ({columns_ddl})')
        con.execute(
            f'INSERT INTO "{schema_name}"."{table_name}" ({column_names}) '
            f'SELECT {column_names} FROM read_parquet(?)',
            [latest_parquet_file],
        )

        # temporary debug check
        row_count = con.execute(
            f'SELECT COUNT(*) FROM "{schema_name}"."{table_name}"'
        ).fetchone()[0]
        logging.info("DuckDB %s.%s row_count=%s", schema_name, table_name, row_count)


def write_to_parquet(df: pl.DataFrame, filepath: str):
    logging.info(f"Writing the parquet data into {filepath}")
    output_path = Path(filepath)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    tmp = output_path.with_suffix(output_path.suffix + ".tmp")
    df.write_parquet(tmp)
    tmp.replace(output_path)

def enrich_df_with_ingestion_metadata(
    pl_df: pl.DataFrame,
    source_file: Path,
    ingestion_datetime: datetime,
) -> pl.DataFrame:
    dt = ingestion_datetime
    return pl_df.with_columns(
        pl.lit(dt.date().isoformat()).alias("ingestion_date"),   # e.g. 2026-03-28
        pl.lit(dt.isoformat()).alias("ingested_at"),             # e.g. 2026-03-28T10:15:30+00:00
        pl.lit(source_file.name).alias("source_file"),     # filename only
    )

def process_entity_to_stage(run_date: str, config: dict, entity: str):

    source_path = config["source_path"]

    logging.info(f"{config['assets'].keys()}")
    entity_config = config["assets"][entity]
    source_folder = entity_config["source_folder"]
    column_mapping = entity_config["column_mapping"]

    staging_path = config["staging_path"]

    mapping_json = json.dumps(column_mapping, sort_keys=True)
    pandera_schema = get_pandera_schema(entity, mapping_json)

    # Read raw JSON files from the source folder
    full_source_path = f"{source_path}/{source_folder}/dt={run_date}"
    logging.info(f"Reading raw JSON files from: {full_source_path}")

    extract_config = entity_config["extract"]    
    context_key = extract_config.get("context_key")

    files = iter_source_files(full_source_path, file_mask="*.json")

    ingestion_datetime = datetime.now()

    for file_path in files:
        logging.info(f"Processing file: {file_path}")
        with open(file_path, 'r', encoding = 'utf-8') as f:
            raw_data = json.load(f)

            logging.info(f"Loaded {len(raw_data)} records from {file_path} file into memory")

            records = resolve_raw_data(raw_data, extract_config)

            mapped_records = map_raw_to_staged(records, column_mapping)
            if context_key:
                context_key_value = raw_data[context_key["source"]]
                for row in mapped_records:
                    row[context_key["target"]] = context_key_value

            pl_df = pl.DataFrame(mapped_records)
            validate_dataframe(entity=entity, df = pl_df, pandera_schema=pandera_schema)

            pl_df = enrich_df_with_ingestion_metadata(pl_df=pl_df, source_file=file_path, ingestion_datetime=ingestion_datetime)

            logging.info(f"{pl_df[:2]}")
            full_staging_path = f"{staging_path}/{entity}/dt={run_date}/{file_path.stem}.parquet"
            write_to_parquet(pl_df, full_staging_path)
