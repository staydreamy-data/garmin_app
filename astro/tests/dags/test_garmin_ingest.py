import importlib
from unittest.mock import MagicMock


def _load_dag_module():
    module = importlib.import_module("dags.garmin_ingest")
    return module, module.garmin_ingest()


def test_garmin_ingest_dag_metadata():
    _, dag = _load_dag_module()

    assert dag.dag_id == "garmin_ingest"
    assert dag.schedule == "@daily"
    assert dag.catchup is True
    assert "garmin" in dag.tags
    assert dag.default_args.get("retries") == 0
    assert [task.task_id for task in dag.tasks] == ["ingest_activities"]


def test_garmin_ingest_uses_templated_ds_arg():
    _, dag = _load_dag_module()
    task = dag.get_task("ingest_activities")

    assert task.op_args == ("{{ ds }}",)


def test_garmin_ingest_task_calls_config_and_pipeline(monkeypatch):
    module, dag = _load_dag_module()
    task = dag.get_task("ingest_activities")

    fake_config = {
        "assets": [{"key": "heartrate", "enabled": True, "output_folder": "heartrate", "overwrite": True}],
        "storage_root": "include/data/raw/garmin",
        "activities_folder": "activities",
    }
    mock_load_config = MagicMock(return_value=fake_config)
    mock_ingest = MagicMock()

    monkeypatch.setattr(module, "load_config", mock_load_config)
    monkeypatch.setattr(module, "ingest_garmin_activities_by_date", mock_ingest)

    task.python_callable(run_date="2026-03-01")

    mock_load_config.assert_called_once_with("garmin_ingest")
    mock_ingest.assert_called_once_with(
        "2026-03-01",
        "include/data/raw/garmin",
        "activities",
        fake_config["assets"],
    )
