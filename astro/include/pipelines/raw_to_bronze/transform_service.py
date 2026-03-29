# astro/include/pipelines/raw_to_bronze/transform_service.py
from dataclasses import asdict
from .contracts import TransformResult
from .config_parser import parse_pipeline_config, ConfigError
from pathlib import Path
from include.pipelines.validation import get_pandera_schema, validate_dataframe
import json
import logging
import polars as pl
from datetime import datetime

def _resolve_records(raw_data: dict | list, extract_config: dict) -> list:
    kind = extract_config["payload_kind"]
    if kind == "list":
        return raw_data if isinstance(raw_data, list) else []
    if kind == "object":
        path = extract_config.get("records_path")
        if not isinstance(raw_data, dict) or not path:
            return []
        return raw_data.get(path, [])
    raise ConfigError(f"Unsupported payload_kind: {kind}")

def _get_nested(record: dict, path: str):
    value = record
    for key in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(key)
        if value is None:
            return None
    return value

def _map_raw_to_staged(records: list, columns_mapping: dict) -> list:

    mapped_records = []
    for record in records:

        mapped_record = {}
        for column_mapping in columns_mapping:
            target_column = column_mapping["target"]
            source_column_value = _get_nested(record, column_mapping["source"])

            mapped_record[target_column] = source_column_value
        mapped_records.append(mapped_record)

    return mapped_records

def _write_to_parquet(df: pl.DataFrame, filepath: str):
    logging.info(f"Writing the parquet data into {filepath}")
    output_path = Path(filepath)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    tmp = output_path.with_suffix(output_path.suffix + ".tmp")
    df.write_parquet(tmp)
    tmp.replace(output_path)

def stage_asset_batch(run_date: str, asset_name: str, raw_config: dict) -> dict:
    config = parse_pipeline_config(raw_config)
    asset_config = config["assets"][asset_name]
    extract_config = asset_config["extract"]
    context_key = extract_config.get("context_key")

    source_dir = Path(config["source_path"]) / asset_config["source_folder"] / f"dt={run_date}"
    stage_dir = Path(config["staging_path"]) / asset_name / f"dt={run_date}"
    quarantine_dir = Path(config["quarantine_dir"]) / asset_name / f"dt={run_date}"

    stage_dir.mkdir(parents=True, exist_ok=True)
    quarantine_dir.mkdir(parents=True, exist_ok=True)

    column_mapping = asset_config["column_mapping"]

    pandera_schema = get_pandera_schema(asset_name, json.dumps(column_mapping, sort_keys=True))

    files_seen = 0
    rows_valid = 0
    rows_invalid = 0
    staged_files = 0

    ingestion_datetime = datetime.now()

    for json_file in sorted(source_dir.glob("*.json")):
        files_seen += 1
        raw_data = json.loads(json_file.read_text(encoding="utf-8"))

        records = _resolve_records(raw_data, extract_config)
        logging.info(f"{records}")
        mapped_rows = _map_raw_to_staged(records, column_mapping)
        logging.info(f"{mapped_rows}")
        if context_key:
            context_key_value = raw_data[context_key["source"]]
            for row in mapped_rows:
                row[context_key["target"]] = context_key_value

        df = pl.DataFrame(mapped_rows)
        if df.is_empty():
            logging.info(f"No records to process in file: {json_file}")
            continue

        try:
            validate_dataframe(entity=asset_name, df=df, pandera_schema=pandera_schema)
            valid_df = df
            invalid_df = pl.DataFrame(schema=df.schema)
        except Exception:
            valid_df = pl.DataFrame(schema=df.schema)
            invalid_df = df

        if valid_df.height > 0:
            out_df = valid_df.with_columns(
                pl.lit(ingestion_datetime.isoformat()).alias("ingested_at"),
                pl.lit(ingestion_datetime.date().isoformat()).alias("ingestion_date"),
                pl.lit(run_date).alias("run_date"),
                pl.lit(json_file.name).alias("source_file"),
            )
            _write_to_parquet(out_df, str(stage_dir / f"{json_file.stem}.parquet"))
            staged_files += 1
            rows_valid += out_df.height    

        if invalid_df.height > 0:
            _write_to_parquet(invalid_df, str(quarantine_dir / f"{json_file.stem}.parquet"))
            rows_invalid += invalid_df.height

    return asdict(
        TransformResult(
            asset=asset_name,
            files_seen=files_seen,
            rows_valid=rows_valid,
            rows_invalid=rows_invalid,
            staged_files=staged_files,
        )
    )    