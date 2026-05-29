import requests
import logging
from sqlalchemy.orm import Session
from src.api.schemas.chat import ChatResponse, ChatRequest
from fastapi import APIRouter, HTTPException, Depends
from src.api.db.session import get_db
from src.api.db.crud import (
    get_messages_by_session,
    create_chat_message,
    create_chat_session,
    get_chat_session,
    update_chat_session_title,
    create_llm_run,
    update_llm_run_success,
    update_llm_run_failure,
    update_chat_session_summary,
)
from src.api.services.training_context import training_context_service
from src.api.clients.ollama import OllamaClient
import time


RECENT_RAW_MESSAGE_LIMIT = 6
COMPACTION_TRIGGER_MESSAGE_COUNT = 12
SUMMARY_NUM_PREDICT = 350
LLM_TEMPERATURE = 0.1

router = APIRouter()


ollama_client = OllamaClient()


def build_session_title(message: str, max_length: int = 60) -> str:
    """Derive a short session label from the first user prompt.

    Args:
        message: Raw user text from the opening turn of a chat session.
        max_length: Maximum allowed title length before truncation.

    Returns:
        A cleaned, human-readable title suitable for later session lists.
    """
    cleaned = " ".join(message.strip().split())
    if not cleaned:
        return "New chat"

    if len(cleaned) <= max_length:
        return cleaned

    return cleaned[: max_length - 3].rstrip() + "..."


def build_summary_prompt(
    existing_summary: str | None,
    messages_to_compact,
) -> str:
    """Build the prompt used to update long-term session memory."""
    prior_summary = existing_summary or "No previous summary."
    history_to_compact = format_conversation_history(messages_to_compact)

    return f"""
You maintain long-term memory for a running coach chat.

Update the session summary using:
- the previous summary
- the older conversation turns that are being compacted

Keep only durable and useful facts such as:
- user goals
- race targets
- training phase
- preferences
- injury or recovery notes
- constraints
- conclusions already reached
- unresolved follow-ups

Do not include filler or repeated phrasing.
Do not invent facts.
Keep the summary concise and factual.

Previous summary:
{prior_summary}

Older conversation to compact:
{history_to_compact}

Return only the updated session summary.
""".strip()


def generate_session_summary(existing_summary: str | None, messages_to_compact) -> str:
    """Generate an updated compacted summary for older session history."""
    prompt = build_summary_prompt(existing_summary, messages_to_compact)
    data = ollama_client.generate(
        prompt=prompt,
        num_predict=SUMMARY_NUM_PREDICT,
        temperature=LLM_TEMPERATURE,
    )
    return data["response"].strip()


def format_conversation_history(messages) -> str:
    """Convert persisted chat messages into a plain-text transcript for Ollama.

    Args:
        messages: Chronologically ordered chat messages loaded from PostgreSQL.

    Returns:
        A plain-text transcript that can be appended to the local LLM prompt.
    """
    if not messages:
        return "No previous conversation."

    lines = []
    for message in messages:
        role = "User" if message.role == "user" else "Assistant"
        lines.append(f"{role}: {message.content}")

    return "\n".join(lines)


def maybe_compact_session_context(db: Session, chat_session) -> None:
    """Compact older chat turns into a stored session summary.

    This runs after a successful assistant response. It never deletes raw messages.
    """
    all_messages = list(get_messages_by_session(db, chat_session.id))
    total_messages = len(all_messages)

    if total_messages <= COMPACTION_TRIGGER_MESSAGE_COUNT:
        return

    unsummarized_messages = all_messages[chat_session.summarized_message_count :]

    if len(unsummarized_messages) <= RECENT_RAW_MESSAGE_LIMIT:
        return

    messages_to_compact = unsummarized_messages[:-RECENT_RAW_MESSAGE_LIMIT]
    if not messages_to_compact:
        return

    updated_summary = generate_session_summary(
        chat_session.summary, messages_to_compact
    )

    update_chat_session_summary(
        db=db,
        session=chat_session,
        summary=updated_summary,
        summarized_message_count=chat_session.summarized_message_count
        + len(messages_to_compact),
    )


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
    if request.session_id is None:
        chat_session = create_chat_session(db)
    else:
        chat_session = get_chat_session(db, request.session_id)
        if chat_session is None:
            raise HTTPException(status_code=404, detail="Session not found")

    all_session_messages = list(get_messages_by_session(db, chat_session.id))
    unsummarized_messages = all_session_messages[
        chat_session.summarized_message_count :
    ]
    recent_messages = unsummarized_messages[-RECENT_RAW_MESSAGE_LIMIT:]

    conversation_history = format_conversation_history(recent_messages)
    session_summary = chat_session.summary or "No previous summary."

    user_message = create_chat_message(
        db=db,
        session_id=chat_session.id,
        role="user",
        content=request.message,
    )

    if not chat_session.title:
        title = build_session_title(request.message)
        chat_session = update_chat_session_title(db, chat_session, title)

    llm_run = create_llm_run(
        db=db,
        session_id=chat_session.id,
        user_message_id=user_message.id,
        model_name=ollama_client.model,
    )

    started_at = time.perf_counter()

    training_context = training_context_service.get_latest_training_context()

    prompt = f"""
    You are a concise running coach.
    Use the training context when answering.
    Use the session summary and recent conversation to preserve continuity.
    If the context is incomplete, say what assumption you are making.
    Do not invent Garmin metrics that were not provided.
    Answer in 4 short bullet points max.

    Training context:
    {training_context}

    Session summary:
    {session_summary}

    Recent conversation:
    {conversation_history}

    User question:
    {request.message}
    """.strip()

    try:
        data = ollama_client.generate(
            prompt=prompt,
            num_predict=1000,
            temperature=0.3,
        )
    except requests.RequestException as exc:
        duration_ms = int((time.perf_counter() - started_at) * 1000)

        update_llm_run_failure(
            db=db,
            llm_run=llm_run,
            error_message=str(exc),
            duration_ms=duration_ms,
        )

        raise HTTPException(
            status_code=502, detail=f"Ollama request failed: {exc}"
        ) from exc

    answer = data["response"]

    assistant_message = create_chat_message(
        db=db,
        session_id=chat_session.id,
        role="assistant",
        content=answer,
    )

    duration_ms = int((time.perf_counter() - started_at) * 1000)

    update_llm_run_success(
        db=db,
        llm_run=llm_run,
        assistant_message_id=assistant_message.id,
        prompt_tokens=data.get("prompt_eval_count"),
        completion_tokens=data.get("eval_count"),
        total_tokens=(
            (data.get("prompt_eval_count") or 0) + (data.get("eval_count") or 0)
            if data.get("prompt_eval_count") is not None
            or data.get("eval_count") is not None
            else None
        ),
        duration_ms=duration_ms,
    )

    try:
        maybe_compact_session_context(db, chat_session)
    except requests.RequestException:
        logging.exception(
            "Session compaction failed because the summarization call to Ollama failed."
        )
    except Exception:
        logging.exception("Session compaction failed unexpectedly.")

    return {"session_id": chat_session.id, "answer": answer}
