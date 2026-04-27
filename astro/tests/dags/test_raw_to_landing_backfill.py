import importlib
from pathlib import Path
from unittest.mock import MagicMock

import pytest


def _load_dag_module():
    module = importlib.import_module("dags.raw_to_landing_backfill")
    return module, module.raw_to_landing_backfill()


def test_raw_to_landing_backfill_dag_metadata():
    _, dag = _load_dag_module()

    assert dag.dag_id == "raw_to_landing_backfill"
    assert dag.catchup is False
    assert dag.max_active_runs == 1
    assert "garmin" in dag.tags
    assert "backfill" in dag.tags
    assert dag.default_args.get("retries") == 0
    assert "start_date" in dag.params
    assert "end_date" in dag.params

    assert {task.task_id for task in dag.tasks} == {
        "get_config",
        "get_enabled_assets",
        "build_run_dates",
        "process_run_date",
        "summarize_run",
    }


def test_raw_to_landing_backfill_uses_templated_params():
    _, dag = _load_dag_module()
    task = dag.get_task("build_run_dates")

    assert task.op_args[:2] == ("{{ params.start_date }}", "{{ params.end_date }}")


def test_get_config_delegates_to_loader(monkeypatch):
    module, dag = _load_dag_module()
    task = dag.get_task("get_config")

    fake_config = {"assets": {"activities": {"enabled": True}}}
    mock_load_config = MagicMock(return_value=fake_config)
    monkeypatch.setattr(module, "load_config", mock_load_config)

    result = task.python_callable()

    mock_load_config.assert_called_once_with("raw_to_landing")
    assert result == fake_config


def test_build_run_dates_returns_inclusive_range():
    _, dag = _load_dag_module()
    task = dag.get_task("build_run_dates")

    result = task.python_callable(
        start_date="2026-03-01",
        end_date="2026-03-03",
        asset_names=[],
        config={},
    )

    assert result == ["2026-03-01", "2026-03-02", "2026-03-03"]


def test_build_run_dates_requires_both_params():
    _, dag = _load_dag_module()
    task = dag.get_task("build_run_dates")

    with pytest.raises(
        ValueError, match="Both start_date and end_date params are required."
    ):
        task.python_callable(start_date="", end_date="2026-03-03")


def test_build_run_dates_rejects_invalid_range():
    _, dag = _load_dag_module()
    task = dag.get_task("build_run_dates")

    with pytest.raises(
        ValueError, match="start_date must be less than or equal to end_date."
    ):
        task.python_callable(start_date="2026-03-04", end_date="2026-03-03")


def test_build_run_dates_filters_to_existing_raw_partitions(tmp_path: Path):
    _, dag = _load_dag_module()
    task = dag.get_task("build_run_dates")

    (tmp_path / "activities" / "dt=2026-03-02").mkdir(parents=True)
    (tmp_path / "splits" / "dt=2026-03-03").mkdir(parents=True)
    (tmp_path / "workouts" / "dt=2026-04-01").mkdir(parents=True)

    config = {
        "source_path": str(tmp_path),
        "assets": {
            "activities": {"source_folder": "activities", "enabled": True},
            "splits": {"source_folder": "splits", "enabled": True},
            "workouts": {"source_folder": "workouts", "enabled": True},
        },
    }

    result = task.python_callable(
        start_date="2026-03-01",
        end_date="2026-03-04",
        asset_names=["activities", "splits", "workouts"],
        config=config,
    )

    assert result == ["2026-03-02", "2026-03-03"]


def test_build_run_dates_returns_empty_when_no_matching_partitions(tmp_path: Path):
    _, dag = _load_dag_module()
    task = dag.get_task("build_run_dates")

    (tmp_path / "activities" / "dt=2026-04-01").mkdir(parents=True)
    config = {
        "source_path": str(tmp_path),
        "assets": {
            "activities": {"source_folder": "activities", "enabled": True},
        },
    }

    result = task.python_callable(
        start_date="2026-03-01",
        end_date="2026-03-03",
        asset_names=["activities"],
        config=config,
    )

    assert result == []


def test_process_run_date_delegates_to_stage_service(monkeypatch):
    module, dag = _load_dag_module()
    task = dag.get_task("process_run_date")

    staged_activity = {"asset": "activities", "rows_valid": 10}
    staged_splits = {"asset": "splits", "rows_valid": 20}
    mock_transform = MagicMock(side_effect=[staged_activity, staged_splits])
    monkeypatch.setattr(module, "stage_asset_batch", mock_transform)

    config = {"assets": {"activities": {"enabled": True}, "splits": {"enabled": True}}}
    result = task.python_callable(
        run_date="2026-03-02",
        asset_names=["activities", "splits"],
        config=config,
    )

    assert mock_transform.call_count == 2
    mock_transform.assert_any_call(
        run_date="2026-03-02", asset_name="activities", raw_config=config
    )
    mock_transform.assert_any_call(
        run_date="2026-03-02", asset_name="splits", raw_config=config
    )
    assert result == [staged_activity, staged_splits]


def test_summarize_run_flattens_results_before_reporting(monkeypatch):
    module, dag = _load_dag_module()
    task = dag.get_task("summarize_run")

    mock_summary = MagicMock(return_value={"rows_valid": 3, "staged_files": 2})
    monkeypatch.setattr(module, "log_run_summary", mock_summary)

    transform_results_by_date = [
        [{"asset": "activities", "rows_valid": 1, "rows_invalid": 0}],
        [{"asset": "splits", "rows_valid": 2, "rows_invalid": 0}],
    ]

    result = task.python_callable(transform_results_by_date=transform_results_by_date)

    mock_summary.assert_called_once_with(
        [
            {"asset": "activities", "rows_valid": 1, "rows_invalid": 0},
            {"asset": "splits", "rows_valid": 2, "rows_invalid": 0},
        ]
    )
    assert result == {"rows_valid": 3, "staged_files": 2}
