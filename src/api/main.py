import os
from uuid import UUID
import logging

import requests
import time

from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from pathlib import Path
from src.api.db.crud import (
    create_chat_message,
    create_chat_session,
    create_llm_run,
    get_chat_session,
    update_llm_run_failure,
    update_llm_run_success,
    get_messages_by_session,
    update_chat_session_title,
    update_chat_session_summary,
    list_chat_sessions,
)
from src.api.db.session import get_db

import duckdb

app = FastAPI()

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:4b")

RECENT_RAW_MESSAGE_LIMIT = 6
COMPACTION_TRIGGER_MESSAGE_COUNT = 12
SUMMARY_NUM_PREDICT = 350


DUCKDB_PATH = (
    Path(__file__).resolve().parents[2] / "astro/include/data/duckdb/garmin_db.duckdb"
)


def call_ollama(prompt: str, num_predict: int = 1000, temperature: float = 0.3) -> dict:
    """Send a prompt to the configured local Ollama model.

    Args:
        prompt: Fully assembled prompt text for the model.
        num_predict: Maximum number of output tokens to generate.
        temperature: Sampling temperature for the model.

    Returns:
        The parsed JSON response returned by Ollama.

    Raises:
        requests.RequestException: If the Ollama HTTP call fails.
    """
    response = requests.post(
        f"{OLLAMA_URL}/api/generate",
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": num_predict,
                "temperature": temperature,
            },
        },
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


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
    data = call_ollama(
        prompt=prompt,
        num_predict=SUMMARY_NUM_PREDICT,
        temperature=0.1,
    )
    return data["response"].strip()


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


def get_latest_training_context() -> str:
    """Load the newest dbt-generated training summary from DuckDB.

    Returns:
        A short summary of the latest training context for prompt injection.
    """
    con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
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


@app.get("/health")
def health():
    """Return a lightweight health response for the API and selected model.

    Returns:
        A status payload with the configured Ollama model name.
    """
    return {"status": "ok", "model": OLLAMA_MODEL}


@app.get("/sessions", response_model=list[SessionSummaryResponse])
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


@app.get("/sessions/{session_id}/messages", response_model=list[ChatMessageResponse])
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


@app.post("/chat", response_model=ChatResponse)
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
        model_name=OLLAMA_MODEL,
    )

    started_at = time.perf_counter()

    training_context = get_latest_training_context()

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
        data = call_ollama(
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
