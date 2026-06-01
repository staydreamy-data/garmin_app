import duckdb
from pathlib import Path
from src.api.core.settings import get_settings

settings = get_settings()


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


training_context_service = TrainingContextService(settings.duckdb_path)
