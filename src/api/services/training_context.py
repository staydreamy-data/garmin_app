import duckdb
import os
from pathlib import Path

# very custom path, needs to be fixed later
DEFAULT_DUCKDB_PATH = (
    Path(__file__).resolve().parents[3] / "astro/include/data/duckdb/garmin_db.duckdb"
)


def get_duckdb_path() -> Path:
    return Path(os.getenv("DUCKDB_PATH", DEFAULT_DUCKDB_PATH))


class TrainingContextService:
    def __init__(self, duckdb_path: Path) -> None:
        self.duckdb_path = duckdb_path

    def get_latest_training_context(self) -> str:
        con = duckdb.connect(str(self.duckdb_path), read_only=True)
        try:
            row = con.execute(
                """
                SELECT run_date, training_summary
                FROM dev_gold.running_trainings_summary
                ORDER BY run_date DESC, activity_id DESC
                LIMIT 1
                """
            ).fetchone()
        finally:
            con.close()

        if row is None:
            return "No training summary available."

        run_date, training_summary = row
        return f"Latest run on {run_date}: {training_summary}"


training_context_service = TrainingContextService(get_duckdb_path())
