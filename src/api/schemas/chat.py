from pydantic import BaseModel
from uuid import UUID


class ChatRequest(BaseModel):
    """Incoming chat payload with optional persisted session continuity."""

    session_id: UUID | None = None
    message: str


class ChatResponse(BaseModel):
    """API response that returns both the answer and active session identifier."""

    session_id: UUID
    answer: str


class SessionSummaryResponse(BaseModel):
    """Lightweight session metadata for session-list views."""

    session_id: UUID
    title: str | None
    summary: str | None


class ChatMessageResponse(BaseModel):
    """One persisted message returned for a session transcript."""

    role: str
    content: str
