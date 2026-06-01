from sqlalchemy.orm import Session
from fastapi import APIRouter, HTTPException, Depends
from src.api.db.session import get_db
from src.api.schemas.chat import ChatResponse, ChatRequest
from src.api.services.chat_service import (
    ChatService,
    SessionNotFoundError,
    LLMProviderError,
)

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, db: Session = Depends(get_db)):
    """Handle one chat turn, persist it, and call the local Ollama model.

    Args:
        request: Incoming user message with an optional persisted session ID.
        db: Request-scoped SQLAlchemy session injected by FastAPI.

    Returns:
        The assistant answer together with the active session identifier.

    Raises:
        HTTPException: If the requested session does not exist or Ollama fails.
    """
    service = ChatService(db=db)

    try:
        return service.handle_chat_turn(request)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
    except LLMProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
