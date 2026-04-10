import pytest
from airflow.exceptions import AirflowFailException

from include.pipelines.raw_to_landing.reporting_service import log_run_summary


def test_log_run_summary_returns_totals_when_quality_gate_passes():
    transform_results = [
        {"asset": "activities", "rows_valid": 2, "rows_invalid": 0, "staged_files": 1},
        {"asset": "splits", "rows_valid": 3, "rows_invalid": 0, "staged_files": 1},
    ]

    summary = log_run_summary(transform_results)

    assert summary == {
        "assets": ["activities", "splits"],
        "rows_valid": 5,
        "rows_invalid": 0,
        "quarantine_files": 0,
        "staged_files": 2,
    }


def test_log_run_summary_fails_when_invalid_rows_exist():
    with pytest.raises(AirflowFailException, match="invalid_rows=1"):
        log_run_summary(
            transform_results=[
                {"asset": "activities", "rows_valid": 1, "rows_invalid": 1}
            ]
        )


def test_log_run_summary_fails_when_quarantine_files_exist():
    with pytest.raises(AirflowFailException, match="quarantine_files=1"):
        log_run_summary(
            transform_results=[
                {
                    "asset": "activities",
                    "rows_valid": 1,
                    "rows_invalid": 0,
                    "quarantine_files": 1,
                }
            ]
        )
