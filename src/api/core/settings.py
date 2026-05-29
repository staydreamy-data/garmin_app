from pathlib import Path
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DUCKDB_PATH = (
    Path(__file__).resolve().parents[3]
    / "astro/include/data/duckdb/garmin_db.duckdb"
)

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "gemma3:4b"
    duckdb_path: Path = DEFAULT_DUCKDB_PATH

    recent_raw_message_limit: int = 6
    compaction_trigger_message_count: int = 12
    summary_num_predict: int = 350

    summary_temperature: float = 0.1
    chat_num_predict: int = 1000
    chat_temperature: float = 0.3

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()