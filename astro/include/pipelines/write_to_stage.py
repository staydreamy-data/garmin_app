from pathlib import Path
import json
import logging

def read_raw_json(source_path: str) -> list:
    pass

def iter_source_files(source_path: str, file_mask: str):
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
            if source_column_value:
                mapped_record[target_column] = source_column_value
        mapped_records.append(mapped_record)

    return mapped_records

def process_entity_to_stage(run_date: str, config: dict, entity: str):

    source_path = config["source_path"]

    logging.info(f"{config['assets'].keys()}")
    entity_config = config["assets"][entity]
    source_folder = entity_config["source_folder"]
    source_type = entity_config["source_type"]
    column_mapping = entity_config["column_mapping"]
    # target_folder = entity_config["target_folder"]
    # column_mapping = entity_config["column_mapping"]

    # Read raw JSON files from the source folder
    full_source_path = f"{source_path}/{source_folder}/dt={run_date}"
    logging.info(f"Reading raw JSON files from: {full_source_path}")
    
    files = iter_source_files(full_source_path, file_mask="*.json")


    for file_path in files:
        logging.info(f"Processing file: {file_path}")
        with open(file_path, 'r', encoding = 'utf-8') as f:
            raw_data = json.load(f)

            logging.info(f"Loaded {len(raw_data)} records from {file_path} file into memory")


            records = []
            if source_type == "list_of_json":
                records = raw_data
            elif source_type == "nested_list":
                # Assuming the nested list is under a key called "data"
                nested_list_path = entity_config.get("nested_list_path")
                records = raw_data.get(nested_list_path, [])
            else:
                continue

            mapped_df = map_raw_to_staged(records, column_mapping)

            logging.info(f"Mapped {len(mapped_df)} records from {file_path} file into staged format")
            logging.info(f"What I mapped: {mapped_df[0]}")

            

        # raw_data = read_raw_json(file_path)

    # Transform and validate the data
    # transformed_data = transform_data(raw_data, column_mapping)
    # validate_data(transformed_data, column_mapping)

    # # Write the staged Parquet files
    # write_staged_parquet(transformed_data, target_folder)
