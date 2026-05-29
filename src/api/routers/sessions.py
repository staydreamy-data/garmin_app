from uuid import UUID
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from src.api.schemas.chat import SessionSummaryResponse, ChatMessageResponse
from src.api.db.session import get_db
from src.api.db.crud import (
    list_chat_sessions,
    get_chat_session,
    get_messages_by_session,
)

router = APIRouter()


@router.get("/sessions", response_model=list[SessionSummaryResponse])
def get_sessions(db: Session = Depends(get_db)):
    """List saved chat sessions for resume flows.

    Args:
        db: Request-scoped SQLAlchemy session injected by FastAPI.

    Returns:
        Saved chat sessions ordered by most recent activity first.
    """
    sessions = list_chat_sessions(db)

    return [
        SessionSummaryResponse(
            session_id=session.id,
            title=session.title,
            summary=session.summary,
        )
        for session in sessions
    ]


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageResponse])
def get_session_messages(session_id: UUID, db: Session = Depends(get_db)):
    """Return the stored transcript for one chat session.

    Args:
        session_id: Persisted chat session identifier.
        db: Request-scoped SQLAlchemy session injected by FastAPI.

    Returns:
        The full stored message history for the session.

    Raises:
        HTTPException: If the session does not exist.
    """
    chat_session = get_chat_session(db, session_id)
    if chat_session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = get_messages_by_session(db, session_id)

    return [
        ChatMessageResponse(
            role=message.role,
            content=message.content,
        )
        for message in messages
    ]
