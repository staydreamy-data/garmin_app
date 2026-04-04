import pytest
from airflow.exceptions import AirflowFailException

from include.pipelines.raw_to_bronze.reporting_service import log_run_summary


def test_log_run_summary_returns_totals_when_quality_gate_passes():
    transform_results = [
        {"asset": "activities", "rows_valid": 2, "rows_invalid": 0, "staged_files": 1},
        {"asset": "splits", "rows_valid": 3, "rows_invalid": 0, "staged_files": 1},
    ]
    load_results = [
        {"asset": "activities", "files_found": 1, "rows_loaded": 2},
        {"asset": "splits", "files_found": 1, "rows_loaded": 3},
    ]
    cleanup_result = {"deleted_files": 2, "deleted_paths": ["/tmp/x", "/tmp/y"]}

    summary = log_run_summary(transform_results, load_results, cleanup_result)

    assert summary == {
        "assets": ["activities", "splits"],
        "rows_valid": 5,
        "rows_invalid": 0,
        "quarantine_files": 0,
        "rows_loaded": 5,
        "cleanup_deleted_files": 2,
    }


def test_log_run_summary_fails_when_invalid_rows_exist():
    with pytest.raises(AirflowFailException, match="invalid_rows=1"):
        log_run_summary(
            transform_results=[
                {"asset": "activities", "rows_valid": 1, "rows_invalid": 1}
            ],
            load_results=[{"asset": "activities", "rows_loaded": 1}],
            cleanup_result={"deleted_files": 1},
        )


def test_log_run_summary_fails_when_loaded_does_not_match_valid():
    with pytest.raises(
        AirflowFailException, match="rows_loaded\\(1\\) != rows_valid\\(2\\)"
    ):
        log_run_summary(
            transform_results=[
                {"asset": "activities", "rows_valid": 2, "rows_invalid": 0}
            ],
            load_results=[{"asset": "activities", "rows_loaded": 1}],
            cleanup_result={"deleted_files": 1},
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
            ],
            load_results=[{"asset": "activities", "rows_loaded": 1}],
            cleanup_result={"deleted_files": 1},
        )
