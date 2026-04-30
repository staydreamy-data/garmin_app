import os

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pathlib import Path

import duckdb

app = FastAPI()

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:4b")


DUCKDB_PATH = Path(__file__).resolve().parents[2] / "astro/include/data/duckdb/garmin_db.duckdb"


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
    message: str

@app.get("/health")
def health():
    return {"status": "ok", "model": OLLAMA_MODEL}


@app.post("/chat")
def chat(request: ChatRequest):
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
                    "num_predict": 120,
                    "temperature": 0.3,
                },
            },
            timeout=60,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Ollama request failed: {exc}") from exc

    data = response.json()
    return {"answer": data["response"]}
