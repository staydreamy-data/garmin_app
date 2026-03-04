from pathlib import Path
import json
import logging

def read_raw_json(source_path: str) -> list:
    pass

def iter_source_files(source_path: str, file_mask: str):
    pattern = f"{source_path}/{file_mask}"
    for p in sorted(Path(source_path).glob(file_mask)):
        if p.is_file():
            yield p

def process_entity_to_stage(run_date: str, config: dict, entity: str):

    source_path = config["source_path"]
    entity_config = config["assets"][entity]
    source_folder = entity_config["source_folder"]
    # target_folder = entity_config["target_folder"]
    # column_mapping = entity_config["column_mapping"]

    # Read raw JSON files from the source folder
    full_source_path = f"{source_path}/{source_folder}/dt={run_date}"
    logging.info(f"Reading raw JSON files from: {full_source_path}")
    raw_data = read_raw_json(full_source_path)

    files = iter_source_files(full_source_path, file_mask="*.json")

    for file_path in files:
        logging.info(f"Processing file: {file_path}")
        # raw_data = read_raw_json(file_path)

    # Transform and validate the data
    # transformed_data = transform_data(raw_data, column_mapping)
    # validate_data(transformed_data, column_mapping)

    # # Write the staged Parquet files
    # write_staged_parquet(transformed_data, target_folder)
