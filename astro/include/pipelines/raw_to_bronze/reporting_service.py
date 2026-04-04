# astro/include/pipelines/raw_to_bronze/reporting_service.py
from __future__ import annotations

import logging
from typing import Any
from airflow.exceptions import AirflowFailException


def log_run_summary(
    transform_results: list[dict[str, Any]] | None,
    load_results: list[dict[str, Any]] | None,
    cleanup_result: dict[str, Any] | None,
) -> dict[str, Any]:
    transform_results = transform_results or []
    load_results = load_results or []
    cleanup_result = cleanup_result or {}

    logging.info("========================================")
    logging.info("RAW_TO_BRONZE SUMMARY")
    logging.info("========================================")

    logging.info("Transform task results:")
    if transform_results:
        for r in sorted(transform_results, key=lambda x: x.get("asset", "")):
            logging.info(
                "  asset=%s | files_seen=%d | staged_files=%d | rows_valid=%d | rows_invalid=%d",
                r.get("asset"),
                int(r.get("files_seen") or 0),
                int(r.get("staged_files") or 0),
                int(r.get("rows_valid") or 0),
                int(r.get("rows_invalid") or 0),
            )
    else:
        logging.info("  (no transform results)")

    logging.info("Load task results:")
    if load_results:
        for r in sorted(load_results, key=lambda x: x.get("asset", "")):
            logging.info(
                "  asset=%s | files_found=%d | rows_loaded=%d",
                r.get("asset"),
                int(r.get("files_found") or 0),
                int(r.get("rows_loaded") or 0),
            )
    else:
        logging.info("  (no load results)")

    logging.info(
        "Cleanup task result: deleted_files=%d | deleted_paths=%s",
        int(cleanup_result.get("deleted_files") or 0),
        cleanup_result.get("deleted_paths", []),
    )

    total_valid = sum(int(r.get("rows_valid") or 0) for r in transform_results)
    total_invalid = sum(int(r.get("rows_invalid") or 0) for r in transform_results)
    total_quarantine_files = sum(
        int(r.get("quarantine_files") or 0) for r in transform_results
    )
    total_loaded = sum(int(r.get("rows_loaded") or 0) for r in load_results)

    summary = {
        "assets": [r.get("asset") for r in transform_results],
        "rows_valid": total_valid,
        "rows_invalid": total_invalid,
        "quarantine_files": total_quarantine_files,
        "rows_loaded": total_loaded,
        "cleanup_deleted_files": int(cleanup_result.get("deleted_files") or 0),
    }

    logging.info("Totals: %s", summary)

    problems: list[str] = []
    if total_invalid > 0:
        problems.append(f"invalid_rows={total_invalid}")
    if total_quarantine_files > 0:
        problems.append(f"quarantine_files={total_quarantine_files}")
    if total_loaded != total_valid:
        problems.append(f"rows_loaded({total_loaded}) != rows_valid({total_valid})")

    if problems:
        logging.info("QUALITY GATE FAILED: %s", "; ".join(problems))
        raise AirflowFailException("Quality gate failed: " + "; ".join(problems))

    logging.info("QUALITY GATE PASSED")
    return summary
