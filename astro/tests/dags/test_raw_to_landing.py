import importlib
from unittest.mock import MagicMock


def _load_dag_module():
    module = importlib.import_module("dags.raw_to_landing")
    return module, module.raw_to_landing()


def test_raw_to_landing_dag_metadata():
    _, dag = _load_dag_module()

    assert dag.dag_id == "raw_to_landing"
    assert dag.catchup is False
    assert dag.max_active_runs == 1
    assert "garmin" in dag.tags
    assert dag.default_args.get("retries") == 0

    assert {task.task_id for task in dag.tasks} == {
        "get_config",
        "get_enabled_assets",
        "transform_asset",
        "summarize_run",
    }


def test_raw_to_landing_task_topology_contract():
    _, dag = _load_dag_module()

    get_config = dag.get_task("get_config")
    get_enabled_assets = dag.get_task("get_enabled_assets")
    transform_asset = dag.get_task("transform_asset")
    summarize_run = dag.get_task("summarize_run")

    assert get_enabled_assets.task_id in get_config.downstream_task_ids
    assert transform_asset.task_id in get_enabled_assets.downstream_task_ids
    assert summarize_run.task_id in transform_asset.downstream_task_ids


def test_get_config_delegates_to_loader(monkeypatch):
    module, dag = _load_dag_module()
    task = dag.get_task("get_config")

    fake_config = {"assets": {"activities": {"enabled": True}}}
    mock_load_config = MagicMock(return_value=fake_config)
    monkeypatch.setattr(module, "load_config", mock_load_config)

    result = task.python_callable()

    mock_load_config.assert_called_once_with("raw_to_landing")
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


def test_summarize_run_delegates_to_reporting_service(monkeypatch):
    module, dag = _load_dag_module()
    task = dag.get_task("summarize_run")

    mock_summary = MagicMock(return_value={"rows_valid": 2, "staged_files": 1})
    monkeypatch.setattr(module, "log_run_summary", mock_summary)

    transform_results = [{"asset": "activities", "rows_valid": 2, "rows_invalid": 0}]

    result = task.python_callable(transform_results=transform_results)

    mock_summary.assert_called_once_with(transform_results)
    assert result == {"rows_valid": 2, "staged_files": 1}
