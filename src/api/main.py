import os
from uuid import UUID

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
)
from src.api.db.session import get_db

import duckdb

app = FastAPI()

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:4b")


DUCKDB_PATH = (
    Path(__file__).resolve().parents[2] / "astro/include/data/duckdb/garmin_db.duckdb"
)


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


@app.get("/health")
def health():
    """Return a lightweight health response for the API and selected model.

    Returns:
        A status payload with the configured Ollama model name.
    """
    return {"status": "ok", "model": OLLAMA_MODEL}


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

    recent_messages = get_messages_by_session(db, chat_session.id, limit=20)

    conversation_history = format_conversation_history(recent_messages)

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
    Use the conversation history to preserve continuity across the session.
    If the context is incomplete, say what assumption you are making.
    Do not invent Garmin metrics that were not provided.
    Answer in 4 short bullet points max.

    Training context:
    {training_context}

    Conversation history:
    {conversation_history}

    User question:
    {request.message}
    """.strip()

    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": 1000,
                    "temperature": 0.3,
                },
            },
            timeout=60,
        )
        response.raise_for_status()
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

    data = response.json()

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

    return {"session_id": chat_session.id, "answer": answer}
