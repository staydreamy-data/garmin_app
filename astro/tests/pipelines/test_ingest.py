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
    client.get_activity_details.side_effect = lambda activity_id: {
        "type": "activity_details",
        "activity_id": activity_id,
    }
    client.get_activity_splits.side_effect = lambda activity_id: {
        "type": "splits",
        "activity_id": activity_id,
    }
    client.get_workout_by_id.side_effect = lambda workout_id: {
        "type": "workout",
        "workout_id": workout_id,
    }
    return client


def _build_assets(
    *,
    details_enabled=True,
    splits_enabled=True,
    workouts_enabled=False,
    overwrite=True,
):
    return [
        {
            "key": "activity_details",
            "enabled": details_enabled,
            "output_folder": "activity_details",
            "overwrite": overwrite,
            "source": "activity",
        },
        {
            "key": "splits",
            "enabled": splits_enabled,
            "output_folder": "splits",
            "overwrite": overwrite,
            "source": "activity",
        },
        {
            "key": "workouts",
            "enabled": workouts_enabled,
            "output_folder": "workouts",
            "overwrite": overwrite,
            "source": "reference",
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
    client.get_activities_by_date.assert_called_once_with(
        startdate="2026-03-01", enddate="2026-03-01"
    )
    assert client.get_activity_details.call_count == 2
    assert client.get_activity_splits.call_count == 2

    raw_dir = tmp_path / "activities" / "dt=2026-03-01"
    raw_files = list(raw_dir.glob("activities_*.json"))
    assert len(raw_files) == 1
    assert json.loads(raw_files[0].read_text(encoding="utf-8")) == activities

    details_1001 = (
        tmp_path / "activity_details" / "dt=2026-03-01" / "activity_details_1001.json"
    )
    details_1002 = (
        tmp_path / "activity_details" / "dt=2026-03-01" / "activity_details_1002.json"
    )
    splits_1001 = tmp_path / "splits" / "dt=2026-03-01" / "splits_1001.json"
    splits_1002 = tmp_path / "splits" / "dt=2026-03-01" / "splits_1002.json"

    assert details_1001.exists()
    assert details_1002.exists()
    assert splits_1001.exists()
    assert splits_1002.exists()
    assert json.loads(details_1001.read_text(encoding="utf-8")) == {
        "type": "activity_details",
        "activity_id": 1001,
    }
    assert json.loads(splits_1002.read_text(encoding="utf-8")) == {
        "type": "splits",
        "activity_id": 1002,
    }


def test_ingest_fetches_reference_assets_from_activity_fields(monkeypatch, tmp_path):
    activities = [
        {"activityId": 1001, "workoutId": 9001},
        {"activityId": 1002, "workoutId": 9002},
    ]
    client = _build_mock_client(activities)
    monkeypatch.setattr(ingest, "get_garmin_client", MagicMock(return_value=client))

    ingest.ingest_garmin_activities_by_date(
        conn_id="garmin_default",
        activity_date="2026-03-01",
        storage_root=str(tmp_path),
        activities_folder="activities",
        assets=_build_assets(
            details_enabled=False,
            splits_enabled=False,
            workouts_enabled=True,
            overwrite=True,
        ),
    )

    client.get_workout_by_id.assert_any_call(9001)
    client.get_workout_by_id.assert_any_call(9002)
    assert client.get_workout_by_id.call_count == 2

    workout_1001 = tmp_path / "workouts" / "dt=2026-03-01" / "workouts_1001.json"
    workout_1002 = tmp_path / "workouts" / "dt=2026-03-01" / "workouts_1002.json"

    assert workout_1001.exists()
    assert workout_1002.exists()
    assert json.loads(workout_1001.read_text(encoding="utf-8")) == {
        "type": "workout",
        "workout_id": 9001,
    }


def test_ingest_skips_reference_asset_when_reference_id_missing(
    monkeypatch, tmp_path, caplog
):
    activities = [{"activityId": 1001}]
    client = _build_mock_client(activities)
    monkeypatch.setattr(ingest, "get_garmin_client", MagicMock(return_value=client))

    with caplog.at_level("INFO"):
        ingest.ingest_garmin_activities_by_date(
            conn_id="garmin_default",
            activity_date="2026-03-01",
            storage_root=str(tmp_path),
            activities_folder="activities",
            assets=_build_assets(
                details_enabled=False,
                splits_enabled=False,
                workouts_enabled=True,
                overwrite=True,
            ),
        )

    client.get_workout_by_id.assert_not_called()
    assert (
        "No workoutId found for activity 1001. Skipping workout asset." in caplog.text
    )
    assert not (tmp_path / "workouts" / "dt=2026-03-01" / "workouts_1001.json").exists()


def test_ingest_skips_disabled_assets(monkeypatch, tmp_path):
    activities = [{"activityId": 1001}]
    client = _build_mock_client(activities)
    monkeypatch.setattr(ingest, "get_garmin_client", MagicMock(return_value=client))

    ingest.ingest_garmin_activities_by_date(
        conn_id="garmin_default",
        activity_date="2026-03-01",
        storage_root=str(tmp_path),
        activities_folder="activities",
        assets=_build_assets(
            details_enabled=True, splits_enabled=False, overwrite=True
        ),
    )

    client.get_activity_details.assert_called_once_with(1001)
    client.get_activity_splits.assert_not_called()
    assert (
        tmp_path / "activity_details" / "dt=2026-03-01" / "activity_details_1001.json"
    ).exists()
    assert not (tmp_path / "splits" / "dt=2026-03-01" / "splits_1001.json").exists()


def test_ingest_respects_overwrite_false_for_existing_output(monkeypatch, tmp_path):
    activities = [{"activityId": 1001}]
    client = _build_mock_client(activities)
    monkeypatch.setattr(ingest, "get_garmin_client", MagicMock(return_value=client))

    existing_output = (
        tmp_path / "activity_details" / "dt=2026-03-01" / "activity_details_1001.json"
    )
    existing_output.parent.mkdir(parents=True, exist_ok=True)
    existing_output.write_text('{"preexisting": true}', encoding="utf-8")

    ingest.ingest_garmin_activities_by_date(
        conn_id="garmin_default",
        activity_date="2026-03-01",
        storage_root=str(tmp_path),
        activities_folder="activities",
        assets=[
            {
                "key": "activity_details",
                "enabled": True,
                "output_folder": "activity_details",
                "overwrite": False,
                "source": "activity",
            }
        ],
    )

    client.get_activity_details.assert_not_called()
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
                    "source": "activity",
                }
            ],
        )

    assert "No Garmin method found for key: unknown_asset. Skipping." in caplog.text
    client.get_activity_details.assert_not_called()
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

    client.get_activities_by_date.assert_called_once_with(
        startdate="2026-03-01", enddate="2026-03-01"
    )
    client.get_activity_details.assert_not_called()
    client.get_activity_splits.assert_not_called()

    raw_dir = tmp_path / "activities" / "dt=2026-03-01"
    raw_files = list(raw_dir.glob("activities_*.json"))
    assert len(raw_files) == 1
    assert json.loads(raw_files[0].read_text(encoding="utf-8")) == []

    assert not list((tmp_path / "activity_details" / "dt=2026-03-01").glob("*.json"))
    assert not list((tmp_path / "splits" / "dt=2026-03-01").glob("*.json"))


def test_ingest_by_date_range_writes_daily_partitions(monkeypatch, tmp_path):
    activities = [
        {"activityId": 1001, "startTimeLocal": "2026-03-01 08:00:00"},
        {"activityId": 1002, "startTimeLocal": "2026-03-02 09:00:00"},
        {"activityId": 1003, "startTimeLocal": "2026-03-02 18:30:00"},
    ]
    client = _build_mock_client(activities)
    mock_get_client = MagicMock(return_value=client)
    monkeypatch.setattr(ingest, "get_garmin_client", mock_get_client)

    ingest.ingest_garmin_activities_by_date_range(
        conn_id="garmin_default",
        start_date="2026-03-01",
        end_date="2026-03-31",
        storage_root=str(tmp_path),
        activities_folder="activities",
        assets=_build_assets(overwrite=True),
    )

    mock_get_client.assert_called_once_with("garmin_default")
    client.get_activities_by_date.assert_called_once_with(
        startdate="2026-03-01", enddate="2026-03-31"
    )
    assert client.get_activity_details.call_count == 3
    assert client.get_activity_splits.call_count == 3

    march_1_raw_dir = tmp_path / "activities" / "dt=2026-03-01"
    march_2_raw_dir = tmp_path / "activities" / "dt=2026-03-02"
    march_1_raw_files = list(march_1_raw_dir.glob("activities_*.json"))
    march_2_raw_files = list(march_2_raw_dir.glob("activities_*.json"))

    assert len(march_1_raw_files) == 1
    assert len(march_2_raw_files) == 1
    assert json.loads(march_1_raw_files[0].read_text(encoding="utf-8")) == [
        {"activityId": 1001, "startTimeLocal": "2026-03-01 08:00:00"}
    ]
    assert json.loads(march_2_raw_files[0].read_text(encoding="utf-8")) == [
        {"activityId": 1002, "startTimeLocal": "2026-03-02 09:00:00"},
        {"activityId": 1003, "startTimeLocal": "2026-03-02 18:30:00"},
    ]

    assert (
        tmp_path / "activity_details" / "dt=2026-03-01" / "activity_details_1001.json"
    ).exists()
    assert (
        tmp_path / "activity_details" / "dt=2026-03-02" / "activity_details_1002.json"
    ).exists()
    assert (tmp_path / "splits" / "dt=2026-03-02" / "splits_1003.json").exists()


def test_ingest_by_date_range_falls_back_to_start_date_when_activity_date_missing(
    monkeypatch, tmp_path
):
    activities = [{"activityId": 1001}]
    client = _build_mock_client(activities)
    monkeypatch.setattr(ingest, "get_garmin_client", MagicMock(return_value=client))

    ingest.ingest_garmin_activities_by_date_range(
        conn_id="garmin_default",
        start_date="2026-03-01",
        end_date="2026-03-31",
        storage_root=str(tmp_path),
        activities_folder="activities",
        assets=[],
    )

    raw_dir = tmp_path / "activities" / "dt=2026-03-01"
    raw_files = list(raw_dir.glob("activities_*.json"))

    assert len(raw_files) == 1
    assert json.loads(raw_files[0].read_text(encoding="utf-8")) == activities
