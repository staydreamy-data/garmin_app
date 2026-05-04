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
    get_messages_by_session,
    update_llm_run_failure,
    update_llm_run_success,
)
from src.api.db.session import get_db

import duckdb

app = FastAPI()

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:4b")


DUCKDB_PATH = (
    Path(__file__).resolve().parents[2] / "astro/include/data/duckdb/garmin_db.duckdb"
)


def get_latest_training_context() -> str:
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
    session_id: UUID | None = None
    message: str

class ChatResponse(BaseModel):
    session_id: UUID
    answer: str


@app.get("/health")
def health():
    return {"status": "ok", "model": OLLAMA_MODEL}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, db: Session = Depends(get_db)):
    if request.session_id is None:
        chat_session = create_chat_session(db)
    else:
        chat_session = get_chat_session(db, request.session_id)
        if chat_session is None:
            raise HTTPException(status_code=404, detail="Session not found")

    user_message = create_chat_message(
        db=db,
        session_id=chat_session.id,
        role="user",
        content=request.message,
    )

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
If the context is incomplete, say what assumption you are making.
Do not invent Garmin metrics that were not provided.
Answer in 4 short bullet points max.

Training context:
{training_context}

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
            if data.get("prompt_eval_count") is not None or data.get("eval_count") is not None
            else None
        ),
        duration_ms=duration_ms,
    )


    return {"session_id": chat_session.id, "answer": answer}


