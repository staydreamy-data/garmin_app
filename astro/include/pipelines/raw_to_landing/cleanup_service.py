from pathlib import Path
import shutil
import logging


def cleanup_stage_batch(
    run_date: str, asset_names: list[str], raw_config: dict
) -> dict:
    staging_root = Path(raw_config["landing_path"]).resolve()
    deleted_paths = []
    deleted_files = 0

    for asset in asset_names:
        target = (staging_root / asset / f"dt={run_date}").resolve()

        # safety guard: never delete outside staging root
        if staging_root not in target.parents:
            raise ValueError(f"Unsafe cleanup path: {target}")

        if not target.exists():
            continue

        deleted_files += sum(1 for p in target.rglob("*") if p.is_file())
        shutil.rmtree(target)
        deleted_paths.append(str(target))

        logging.info(f"Deleted staged batch at {target} with {deleted_files} files")

    return {
        "run_date": run_date,
        "assets": asset_names,
        "deleted_paths": deleted_paths,
        "deleted_files": deleted_files,
    }
