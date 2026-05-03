import uuid
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.db.models import ChatMessage, ChatSession, LLMRun


def create_chat_session(db: Session, title: str | None = None) -> ChatSession:
    session = ChatSession(title=title)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_chat_session(db: Session, session_id: uuid.UUID) -> ChatSession | None:
    stmt = select(ChatSession).where(ChatSession.id == session_id)
    return db.scalar(stmt)


def list_chat_sessions(db: Session) -> Sequence[ChatSession]:
    stmt = select(ChatSession).order_by(ChatSession.updated_at.desc())
    return db.scalars(stmt).all()


def update_chat_session_title(
    db: Session,
    session: ChatSession,
    title: str | None,
) -> ChatSession:
    session.title = title
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def create_chat_message(
    db: Session,
    session_id: uuid.UUID,
    role: str,
    content: str,
) -> ChatMessage:
    message = ChatMessage(
        session_id=session_id,
        role=role,
        content=content,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def get_messages_by_session(
    db: Session,
    session_id: uuid.UUID,
    limit: int | None = None,
) -> Sequence[ChatMessage]:
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc())
    )

    if limit is not None:
        stmt = stmt.limit(limit)

    return db.scalars(stmt).all()


def create_llm_run(
    db: Session,
    session_id: uuid.UUID,
    user_message_id: uuid.UUID,
    model_name: str,
    provider: str = "ollama",
    status: str = "started",
) -> LLMRun:
    llm_run = LLMRun(
        session_id=session_id,
        user_message_id=user_message_id,
        model_name=model_name,
        provider=provider,
        status=status,
    )
    db.add(llm_run)
    db.commit()
    db.refresh(llm_run)
    return llm_run


def update_llm_run_success(
    db: Session,
    llm_run: LLMRun,
    assistant_message_id: uuid.UUID,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    total_tokens: int | None = None,
    duration_ms: int | None = None,
) -> LLMRun:
    llm_run.assistant_message_id = assistant_message_id
    llm_run.prompt_tokens = prompt_tokens
    llm_run.completion_tokens = completion_tokens
    llm_run.total_tokens = total_tokens
    llm_run.duration_ms = duration_ms
    llm_run.status = "completed"

    db.add(llm_run)
    db.commit()
    db.refresh(llm_run)
    return llm_run


def update_llm_run_failure(
    db: Session,
    llm_run: LLMRun,
    error_message: str,
    duration_ms: int | None = None,
) -> LLMRun:
    llm_run.status = "failed"
    llm_run.error_message = error_message
    llm_run.duration_ms = duration_ms

    db.add(llm_run)
    db.commit()
    db.refresh(llm_run)
    return llm_run
