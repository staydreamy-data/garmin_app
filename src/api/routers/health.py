from fastapi import APIRouter
import os

router = APIRouter()

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:4b")


@router.get("/health")
def health():
    """Return a lightweight health response for the API and selected model.

    Returns:
        A status payload with the configured Ollama model name.
    """
    return {"status": "ok", "model": OLLAMA_MODEL}
