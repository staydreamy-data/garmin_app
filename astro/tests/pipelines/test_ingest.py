from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

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
