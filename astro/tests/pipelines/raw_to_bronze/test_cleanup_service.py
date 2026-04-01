from pathlib import Path

import pytest

from include.pipelines.raw_to_bronze.cleanup_service import cleanup_stage_batch


def test_cleanup_deletes_only_requested_partition(tmp_path: Path):
    run_date = "2026-03-18"
    other_date = "2026-03-19"
    staging_root = tmp_path / "stage"

    to_delete = staging_root / "activities" / f"dt={run_date}"
    to_keep = staging_root / "activities" / f"dt={other_date}"
    to_delete.mkdir(parents=True, exist_ok=True)
    to_keep.mkdir(parents=True, exist_ok=True)
    (to_delete / "part-1.parquet").write_text("x", encoding="utf-8")
    (to_keep / "part-2.parquet").write_text("y", encoding="utf-8")

    result = cleanup_stage_batch(
        run_date=run_date,
        asset_names=["activities"],
        raw_config={"staging_path": str(staging_root)},
    )

    assert result["deleted_files"] == 1
    assert str(to_delete.resolve()) in result["deleted_paths"]
    assert not to_delete.exists()
    assert to_keep.exists()


def test_cleanup_safety_guard_rejects_unsafe_asset_path(tmp_path: Path):
    staging_root = tmp_path / "stage"
    staging_root.mkdir(parents=True, exist_ok=True)

    with pytest.raises(ValueError, match="Unsafe cleanup path"):
        cleanup_stage_batch(
            run_date="2026-03-18",
            asset_names=["../../escape"],
            raw_config={"staging_path": str(staging_root)},
        )


def test_cleanup_handles_missing_partition_without_failing(tmp_path: Path):
    staging_root = tmp_path / "stage"
    staging_root.mkdir(parents=True, exist_ok=True)

    result = cleanup_stage_batch(
        run_date="2026-03-18",
        asset_names=["activities"],
        raw_config={"staging_path": str(staging_root)},
    )

    assert result["deleted_files"] == 0
    assert result["deleted_paths"] == []
