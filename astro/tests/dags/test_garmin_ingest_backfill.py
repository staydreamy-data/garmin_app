import importlib
from unittest.mock import MagicMock

import pytest


def _load_dag_module():
    module = importlib.import_module("dags.garmin_ingest_backfill")
    return module, module.garmin_ingest_backfill()


def test_garmin_ingest_backfill_dag_metadata():
    _, dag = _load_dag_module()

    assert dag.dag_id == "garmin_ingest_backfill"
    assert dag.catchup is False
    assert "garmin" in dag.tags
    assert "backfill" in dag.tags
    assert dag.default_args.get("retries") == 0
    assert "start_date" in dag.params
    assert "end_date" in dag.params
    assert [task.task_id for task in dag.tasks] == ["ingest_activities"]


def test_garmin_ingest_backfill_uses_templated_params():
    _, dag = _load_dag_module()
    task = dag.get_task("ingest_activities")

    assert task.op_args == ("{{ params.start_date }}", "{{ params.end_date }}")


def test_garmin_ingest_backfill_task_calls_config_and_pipeline(monkeypatch):
    module, dag = _load_dag_module()
    task = dag.get_task("ingest_activities")

    fake_config = {
        "assets": [
            {
                "key": "splits",
                "enabled": True,
                "output_folder": "splits",
                "overwrite": True,
                "source": "activity",
            }
        ],
        "storage_root": "include/data/raw/garmin",
        "activities_folder": "activities",
    }
    mock_load_config = MagicMock(return_value=fake_config)
    mock_ingest = MagicMock()

    monkeypatch.setattr(module, "load_config", mock_load_config)
    monkeypatch.setattr(module, "ingest_garmin_activities_by_date_range", mock_ingest)

    task.python_callable(start_date="2026-01-01", end_date="2026-12-31")

    mock_load_config.assert_called_once_with("garmin_ingest")
    mock_ingest.assert_called_once_with(
        "garmin_default",
        "2026-01-01",
        "2026-12-31",
        "include/data/raw/garmin",
        "activities",
        fake_config["assets"],
    )


def test_garmin_ingest_backfill_requires_both_params():
    _, dag = _load_dag_module()
    task = dag.get_task("ingest_activities")

    with pytest.raises(
        ValueError, match="Both start_date and end_date params are required."
    ):
        task.python_callable(start_date="", end_date="2026-12-31")
