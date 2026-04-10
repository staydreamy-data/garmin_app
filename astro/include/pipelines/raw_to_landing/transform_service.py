# astro/include/pipelines/raw_to_landing/transform_service.py
from dataclasses import asdict
from .contracts import TransformResult
from .config_parser import parse_pipeline_config, ConfigError
from pathlib import Path
from include.pipelines.validation import validate_dataframe
import json
import logging
import pandera.polars as pa
import polars as pl
from datetime import datetime

DTYPE_MAP = {
    "string": pl.Utf8,
    "int64": pl.Int64,
    "float64": pl.Float64,
    "boolean": pl.Boolean,
}


def _get_pandera_schema(entity: str, mapping_json: str) -> pa.DataFrameSchema:
    logging.info(f"Building pandera schema for {entity}")

    column_mapping = json.loads(mapping_json)
    cols = {}
    for c in column_mapping:
        required = c.get("required", False)
        cols[c["target"]] = pa.Column(
            DTYPE_MAP[c["dtype"]],
            required=required,
            nullable=not required,
        )
    return pa.DataFrameSchema(cols, strict=False, coerce=True)


def _resolve_records(raw_data: dict | list, extract_config: dict) -> list:
    kind = extract_config["payload_kind"]
    if kind == "list":
        return raw_data if isinstance(raw_data, list) else []
    if kind == "object":
        path = extract_config.get("records_path")
        if not isinstance(raw_data, dict) or not path:
            return []
        return raw_data.get(path, [])
    if kind == "descriptor_metrics":
        return _resolve_descriptor_metrics(raw_data, extract_config)
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


def _resolve_descriptor_metrics(raw_data: dict, extract_config: dict) -> list[dict]:
    if not isinstance(raw_data, dict):
        return []

    schema_path = extract_config.get("schema_path")
    schema_index_field = extract_config.get("schema_index_field")
    schema_key_field = extract_config.get("schema_key_field")
    schema_unit_path = extract_config.get("schema_unit_path")
    records_path = extract_config.get("records_path")
    values_path = extract_config.get("values_path")

    if not all(
        [schema_path, schema_index_field, schema_key_field, records_path, values_path]
    ):
        raise ConfigError(
            "descriptor_metrics requires: schema_path, schema_index_field, "
            "schema_key_field, records_path, values_path"
        )

    descriptors = raw_data.get(schema_path, [])
    measurements = raw_data.get(records_path, [])
    if not isinstance(descriptors, list) or not isinstance(measurements, list):
        return []

    descriptor_by_index: dict[int, dict] = {}
    for descriptor in descriptors:
        if not isinstance(descriptor, dict):
            continue
        descriptor_index = descriptor.get(schema_index_field)
        try:
            if descriptor_index is None:
                continue
            descriptor_by_index[int(descriptor_index)] = descriptor
        except (TypeError, ValueError):
            continue

    resolved_rows: list[dict] = []
    for measurement_index, measurement in enumerate(measurements):
        if not isinstance(measurement, dict):
            continue
        metric_values = measurement.get(values_path, [])
        if not isinstance(metric_values, list):
            continue

        for metric_index, metric_value in enumerate(metric_values):
            descriptor = descriptor_by_index.get(metric_index, {})
            metric_key = (
                descriptor.get(schema_key_field)
                if isinstance(descriptor, dict)
                else None
            )

            unit = {}
            if schema_unit_path and isinstance(descriptor, dict):
                unit_value = _get_nested(descriptor, schema_unit_path)
                if isinstance(unit_value, dict):
                    unit = unit_value

            resolved_rows.append(
                {
                    "measurement_index": measurement_index,
                    "metric_index": metric_index,
                    "metric_key": metric_key,
                    "metric_value": metric_value,
                    "unit_key": unit.get("key"),
                    "unit_factor": unit.get("factor"),
                }
            )

    return resolved_rows


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


def _iter_source_files(source_dir: Path, payload_kind: str) -> list[Path]:
    json_files = sorted(source_dir.glob("*.json"))
    if payload_kind == "list" and json_files:
        # Treat list payloads as a daily snapshot and keep only the latest file.
        return [json_files[-1]]
    return json_files


def _write_to_parquet(df: pl.DataFrame, filepath: str):
    logging.info(f"Writing the parquet data into {filepath}")
    output_path = Path(filepath)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    tmp = output_path.with_suffix(output_path.suffix + ".tmp")
    df.write_parquet(tmp)
    tmp.replace(output_path)


def _cast_dataframe_to_schema(
    df: pl.DataFrame, column_mapping: list[dict]
) -> pl.DataFrame:
    # Keep parquet schemas stable across files: optional columns like
    # intensity_type may be all NULL in one batch and strings in another.
    cast_expressions = [
        pl.col(column["target"])
        .cast(DTYPE_MAP[column["dtype"]], strict=False)
        .alias(column["target"])
        for column in column_mapping
    ]
    return df.with_columns(cast_expressions)


def _attach_metadata(
    df: pl.DataFrame, run_date: str, source_file: str, ingestion_datetime: datetime
) -> pl.DataFrame:
    return df.with_columns(
        pl.lit(ingestion_datetime.isoformat()).alias("ingested_at"),
        pl.lit(ingestion_datetime.date().isoformat()).alias("ingestion_date"),
        pl.lit(run_date).alias("run_date"),
        pl.lit(source_file).alias("source_file"),
    )


def stage_asset_batch(run_date: str, asset_name: str, raw_config: dict) -> dict:
    config = parse_pipeline_config(raw_config)
    asset_config = config["assets"][asset_name]
    extract_config = asset_config["extract"]
    context_key = extract_config.get("context_key")

    source_dir = (
        Path(config["source_path"]) / asset_config["source_folder"] / f"dt={run_date}"
    )
    stage_dir = Path(config["landing_path"]) / asset_name / f"dt={run_date}"
    quarantine_dir = Path(config["quarantine_dir"]) / asset_name / f"dt={run_date}"

    column_mapping = asset_config["column_mapping"]

    pandera_schema = _get_pandera_schema(
        asset_name, json.dumps(column_mapping, sort_keys=True)
    )

    files_seen = 0
    rows_valid = 0
    rows_invalid = 0
    staged_output = stage_dir / f"{asset_name}.parquet"
    quarantine_output = quarantine_dir / f"{asset_name}.parquet"
    valid_batches: list[pl.DataFrame] = []
    invalid_batches: list[pl.DataFrame] = []

    ingestion_datetime = datetime.now()

    for json_file in _iter_source_files(source_dir, extract_config["payload_kind"]):
        files_seen += 1
        raw_data = json.loads(json_file.read_text(encoding="utf-8"))

        records = _resolve_records(raw_data, extract_config)
        mapped_rows = _map_raw_to_staged(records, column_mapping)
        if context_key:
            context_source = context_key.get("source")
            context_target = context_key.get("target")
            context_key_value = (
                _get_nested(raw_data, context_source) if context_source else None
            )
            if context_target:
                for row in mapped_rows:
                    row[context_target] = context_key_value

        df = _cast_dataframe_to_schema(pl.DataFrame(mapped_rows), column_mapping)
        if df.is_empty():
            logging.info(f"No records to process in file: {json_file}")
            continue

        enriched_df = _attach_metadata(df, run_date, json_file.name, ingestion_datetime)

        try:
            validate_dataframe(entity=asset_name, df=df, pandera_schema=pandera_schema)
            valid_df = enriched_df
            invalid_df = pl.DataFrame(schema=enriched_df.schema)
        except Exception:
            valid_df = pl.DataFrame(schema=enriched_df.schema)
            invalid_df = enriched_df

        if valid_df.height > 0:
            valid_batches.append(valid_df)
            rows_valid += valid_df.height

        if invalid_df.height > 0:
            invalid_batches.append(invalid_df)
            rows_invalid += invalid_df.height

    staged_files = 0
    if valid_batches:
        staged_df = pl.concat(valid_batches, how="vertical_relaxed")
        _write_to_parquet(staged_df, str(staged_output))
        staged_files = 1
    elif staged_output.exists():
        staged_output.unlink()

    if invalid_batches:
        quarantine_df = pl.concat(invalid_batches, how="vertical_relaxed")
        _write_to_parquet(quarantine_df, str(quarantine_output))
    elif quarantine_output.exists():
        quarantine_output.unlink()

    return asdict(
        TransformResult(
            asset=asset_name,
            files_seen=files_seen,
            rows_valid=rows_valid,
            rows_invalid=rows_invalid,
            staged_files=staged_files,
        )
    )
