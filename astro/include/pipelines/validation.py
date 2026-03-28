import pandera.polars as pa
import polars as pl
import json
import logging
from pandera.errors import SchemaErrors

DTYPE_MAP = {
    "string": pl.Utf8,
    "int64": pl.Int64,
    "float64": pl.Float64,
    "boolean": pl.Boolean,
}

def get_pandera_schema(entity: str, mapping_json: str) -> pa.DataFrameSchema:
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

def validate_dataframe(entity: str, df: pl.DataFrame, pandera_schema: pa.DataFrameSchema):
    try:
        pandera_schema.validate(df, lazy=True)
        logging.info(f"The data for entity {entity} passed the validation")
    except SchemaErrors as e:
        logging.error(f"Schema validation failed for entity '{entity}': {e}")
        raise
    except Exception as e:
        logging.error(f"Error happened during the validation. Please check the logs. {e}")
        raise