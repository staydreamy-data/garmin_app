from fastapi import APIRouter
from src.api.core.settings import get_settings

settings = get_settings()

router = APIRouter()


@router.get("/health")
def health():
    """Return a lightweight health response for the API and selected model.

    Returns:
        A status payload with the configured Ollama model name.
    """
    return {"status": "ok", "model": settings.ollama_model}
