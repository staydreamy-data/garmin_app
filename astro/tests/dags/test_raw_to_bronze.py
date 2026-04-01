import importlib
from unittest.mock import MagicMock


def _load_dag_module():
    module = importlib.import_module("dags.raw_to_bronze")
    return module, module.raw_to_bronze()


def test_raw_to_bronze_dag_metadata():
    _, dag = _load_dag_module()

    assert dag.dag_id == "raw_to_bronze"
    assert dag.schedule == "@daily"
    assert dag.catchup is False
    assert dag.max_active_runs == 1
    assert "garmin" in dag.tags
    assert dag.default_args.get("retries") == 0

    assert {task.task_id for task in dag.tasks} == {
        "get_config",
        "get_enabled_assets",
        "transform_asset",
        "merge_assets",
        "cleanup_staged_parquet",
        "summarize_run",
    }


def test_raw_to_bronze_task_topology_contract():
    _, dag = _load_dag_module()

    get_config = dag.get_task("get_config")
    get_enabled_assets = dag.get_task("get_enabled_assets")
    transform_asset = dag.get_task("transform_asset")
    merge_assets = dag.get_task("merge_assets")
    cleanup_staged_parquet = dag.get_task("cleanup_staged_parquet")
    summarize_run = dag.get_task("summarize_run")

    assert get_enabled_assets.task_id in get_config.downstream_task_ids
    assert transform_asset.task_id in get_enabled_assets.downstream_task_ids
    assert merge_assets.task_id in transform_asset.downstream_task_ids
    assert cleanup_staged_parquet.task_id in merge_assets.downstream_task_ids
    assert summarize_run.task_id in cleanup_staged_parquet.downstream_task_ids


def test_get_config_delegates_to_loader(monkeypatch):
    module, dag = _load_dag_module()
    task = dag.get_task("get_config")

    fake_config = {"assets": {"activities": {"enabled": True}}}
    mock_load_config = MagicMock(return_value=fake_config)
    monkeypatch.setattr(module, "load_config", mock_load_config)

    result = task.python_callable()

    mock_load_config.assert_called_once_with("raw_to_bronze")
    assert result == fake_config


def test_get_enabled_assets_filters_disabled():
    _, dag = _load_dag_module()
    task = dag.get_task("get_enabled_assets")

    config = {
        "assets": {
            "activities": {"enabled": True},
            "splits": {"enabled": False},
            "activity_details": {},
        }
    }

    result = task.python_callable(config=config)

    assert result == ["activities", "activity_details"]


def test_transform_asset_delegates_to_service(monkeypatch):
    module, dag = _load_dag_module()
    task = dag.get_task("transform_asset")

    fake_result = {
        "asset": "activities",
        "files_seen": 1,
        "rows_valid": 2,
        "rows_invalid": 0,
        "staged_files": 1,
    }
    mock_transform = MagicMock(return_value=fake_result)
    monkeypatch.setattr(module, "stage_asset_batch", mock_transform)

    config = {"assets": {"activities": {"enabled": True}}}
    result = task.python_callable(
        run_date="2026-03-18",
        asset_name="activities",
        config=config,
    )

    mock_transform.assert_called_once_with(
        run_date="2026-03-18", asset_name="activities", raw_config=config
    )
    assert result == fake_result


def test_merge_assets_delegates_and_returns_results(monkeypatch):
    module, dag = _load_dag_module()
    task = dag.get_task("merge_assets")

    mock_append = MagicMock(
        side_effect=[
            {"asset": "activities", "files_found": 1, "rows_loaded": 2},
            {"asset": "splits", "files_found": 1, "rows_loaded": 6},
        ]
    )
    monkeypatch.setattr(module, "append_to_bronze", mock_append)

    config = {"assets": {}}
    result = task.python_callable(
        run_date="2026-03-18",
        asset_names=["activities", "splits"],
        config=config,
    )

    assert result == [
        {"asset": "activities", "files_found": 1, "rows_loaded": 2},
        {"asset": "splits", "files_found": 1, "rows_loaded": 6},
    ]
    assert mock_append.call_count == 2


def test_cleanup_delegates_to_service(monkeypatch):
    module, dag = _load_dag_module()
    task = dag.get_task("cleanup_staged_parquet")

    fake_result = {"run_date": "2026-03-18", "deleted_files": 4, "deleted_paths": []}
    mock_cleanup = MagicMock(return_value=fake_result)
    monkeypatch.setattr(module, "cleanup_stage_batch", mock_cleanup)

    config = {"staging_path": "include/data/stage/raw_to_bronze"}
    result = task.python_callable(
        run_date="2026-03-18",
        asset_names=["activities"],
        config=config,
    )

    mock_cleanup.assert_called_once_with(
        run_date="2026-03-18",
        asset_names=["activities"],
        raw_config=config,
    )
    assert result == fake_result


def test_summarize_run_delegates_to_reporting_service(monkeypatch):
    module, dag = _load_dag_module()
    task = dag.get_task("summarize_run")

    mock_summary = MagicMock(return_value={"rows_valid": 2, "rows_loaded": 2})
    monkeypatch.setattr(module, "log_run_summary", mock_summary)

    transform_results = [{"asset": "activities", "rows_valid": 2, "rows_invalid": 0}]
    load_results = [{"asset": "activities", "rows_loaded": 2}]
    cleanup_result = {"deleted_files": 1}

    result = task.python_callable(
        transform_results=transform_results,
        load_results=load_results,
        cleanup_result=cleanup_result,
    )

    mock_summary.assert_called_once_with(transform_results, load_results, cleanup_result)
    assert result == {"rows_valid": 2, "rows_loaded": 2}
