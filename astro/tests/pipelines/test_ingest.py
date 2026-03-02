from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import json

from include.pipelines import ingest


def test_get_garmin_client_success(monkeypatch):
    conn = SimpleNamespace(login="user@example.com", password="secret")
    mock_get_connection = MagicMock(return_value=conn)
    mock_client = MagicMock()
    mock_garmin_ctor = MagicMock(return_value=mock_client)

    monkeypatch.setattr(ingest.BaseHook, "get_connection", mock_get_connection)
    monkeypatch.setattr(ingest, "Garmin", mock_garmin_ctor)

    result = ingest.get_garmin_client("garmin_default")

    assert result is mock_client
    mock_get_connection.assert_called_once_with("garmin_default")
    mock_garmin_ctor.assert_called_once_with("user@example.com", "secret")
    mock_client.login.assert_called_once_with()


def test_get_garmin_client_wraps_login_errors(monkeypatch):
    conn = SimpleNamespace(login="user@example.com", password="wrong")
    mock_get_connection = MagicMock(return_value=conn)
    mock_client = MagicMock()
    mock_client.login.side_effect = ValueError("invalid credentials")
    mock_garmin_ctor = MagicMock(return_value=mock_client)

    monkeypatch.setattr(ingest.BaseHook, "get_connection", mock_get_connection)
    monkeypatch.setattr(ingest, "Garmin", mock_garmin_ctor)

    with pytest.raises(RuntimeError, match="Failed to login to Garmin Connect") as exc:
        ingest.get_garmin_client("garmin_default")

    assert isinstance(exc.value.__cause__, ValueError)


def _build_mock_client(activities):
    client = MagicMock()
    client.get_activities_by_date.return_value = activities
    client.get_activity_hr_in_timezones.side_effect = (
        lambda activity_id: {"type": "heartrate", "activity_id": activity_id}
    )
    client.get_activity_splits.side_effect = (
        lambda activity_id: {"type": "splits", "activity_id": activity_id}
    )
    return client


def _build_assets(*, heartrate_enabled=True, splits_enabled=True, overwrite=True):
    return [
        {
            "key": "heartrate",
            "enabled": heartrate_enabled,
            "output_folder": "heartrate",
            "overwrite": overwrite,
        },
        {
            "key": "splits",
            "enabled": splits_enabled,
            "output_folder": "splits",
            "overwrite": overwrite,
        },
    ]


def test_ingest_by_date_writes_raw_and_asset_files(monkeypatch, tmp_path):
    activities = [{"activityId": 1001}, {"activityId": 1002}]
    client = _build_mock_client(activities)
    mock_get_client = MagicMock(return_value=client)
    monkeypatch.setattr(ingest, "get_garmin_client", mock_get_client)

    ingest.ingest_garmin_activities_by_date(
        conn_id="garmin_default",
        activity_date="2026-03-01",
        storage_root=str(tmp_path),
        activities_folder="activities",
        assets=_build_assets(overwrite=True),
    )

    mock_get_client.assert_called_once_with("garmin_default")
    client.get_activities_by_date.assert_called_once_with("2026-03-01")
    assert client.get_activity_hr_in_timezones.call_count == 2
    assert client.get_activity_splits.call_count == 2

    raw_dir = tmp_path / "activities" / "dt=2026-03-01"
    raw_files = list(raw_dir.glob("activities_*.json"))
    assert len(raw_files) == 1
    assert json.loads(raw_files[0].read_text(encoding="utf-8")) == activities

    hr_1001 = tmp_path / "heartrate" / "dt=2026-03-01" / "heartrate_1001.json"
    hr_1002 = tmp_path / "heartrate" / "dt=2026-03-01" / "heartrate_1002.json"
    splits_1001 = tmp_path / "splits" / "dt=2026-03-01" / "splits_1001.json"
    splits_1002 = tmp_path / "splits" / "dt=2026-03-01" / "splits_1002.json"

    assert hr_1001.exists()
    assert hr_1002.exists()
    assert splits_1001.exists()
    assert splits_1002.exists()
    assert json.loads(hr_1001.read_text(encoding="utf-8")) == {
        "type": "heartrate",
        "activity_id": 1001,
    }
    assert json.loads(splits_1002.read_text(encoding="utf-8")) == {
        "type": "splits",
        "activity_id": 1002,
    }


def test_ingest_skips_disabled_assets(monkeypatch, tmp_path):
    activities = [{"activityId": 1001}]
    client = _build_mock_client(activities)
    monkeypatch.setattr(ingest, "get_garmin_client", MagicMock(return_value=client))

    ingest.ingest_garmin_activities_by_date(
        conn_id="garmin_default",
        activity_date="2026-03-01",
        storage_root=str(tmp_path),
        activities_folder="activities",
        assets=_build_assets(heartrate_enabled=True, splits_enabled=False, overwrite=True),
    )

    client.get_activity_hr_in_timezones.assert_called_once_with(1001)
    client.get_activity_splits.assert_not_called()
    assert (tmp_path / "heartrate" / "dt=2026-03-01" / "heartrate_1001.json").exists()
    assert not (tmp_path / "splits" / "dt=2026-03-01" / "splits_1001.json").exists()


def test_ingest_respects_overwrite_false_for_existing_output(monkeypatch, tmp_path):
    activities = [{"activityId": 1001}]
    client = _build_mock_client(activities)
    monkeypatch.setattr(ingest, "get_garmin_client", MagicMock(return_value=client))

    existing_output = tmp_path / "heartrate" / "dt=2026-03-01" / "heartrate_1001.json"
    existing_output.parent.mkdir(parents=True, exist_ok=True)
    existing_output.write_text('{"preexisting": true}', encoding="utf-8")

    ingest.ingest_garmin_activities_by_date(
        conn_id="garmin_default",
        activity_date="2026-03-01",
        storage_root=str(tmp_path),
        activities_folder="activities",
        assets=[
            {
                "key": "heartrate",
                "enabled": True,
                "output_folder": "heartrate",
                "overwrite": False,
            }
        ],
    )

    client.get_activity_hr_in_timezones.assert_not_called()
    assert existing_output.read_text(encoding="utf-8") == '{"preexisting": true}'


def test_ingest_skips_unknown_method_key(monkeypatch, tmp_path, caplog):
    activities = [{"activityId": 1001}]
    client = _build_mock_client(activities)
    monkeypatch.setattr(ingest, "get_garmin_client", MagicMock(return_value=client))

    with caplog.at_level("WARNING"):
        ingest.ingest_garmin_activities_by_date(
            conn_id="garmin_default",
            activity_date="2026-03-01",
            storage_root=str(tmp_path),
            activities_folder="activities",
            assets=[
                {
                    "key": "unknown_asset",
                    "enabled": True,
                    "output_folder": "unknown",
                    "overwrite": True,
                }
            ],
        )

    assert "No Garmin method found for key: unknown_asset. Skipping." in caplog.text
    client.get_activity_hr_in_timezones.assert_not_called()
    client.get_activity_splits.assert_not_called()
    assert not list((tmp_path / "unknown" / "dt=2026-03-01").glob("*.json"))


def test_ingest_handles_empty_activity_list(monkeypatch, tmp_path):
    activities = []
    client = _build_mock_client(activities)
    monkeypatch.setattr(ingest, "get_garmin_client", MagicMock(return_value=client))

    ingest.ingest_garmin_activities_by_date(
        conn_id="garmin_default",
        activity_date="2026-03-01",
        storage_root=str(tmp_path),
        activities_folder="activities",
        assets=_build_assets(overwrite=True),
    )

    client.get_activities_by_date.assert_called_once_with("2026-03-01")
    client.get_activity_hr_in_timezones.assert_not_called()
    client.get_activity_splits.assert_not_called()

    raw_dir = tmp_path / "activities" / "dt=2026-03-01"
    raw_files = list(raw_dir.glob("activities_*.json"))
    assert len(raw_files) == 1
    assert json.loads(raw_files[0].read_text(encoding="utf-8")) == []

    assert not list((tmp_path / "heartrate" / "dt=2026-03-01").glob("*.json"))
    assert not list((tmp_path / "splits" / "dt=2026-03-01").glob("*.json"))
