import os

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:4b")


class ChatRequest(BaseModel):
    message: str

@app.get("/health")
def health():
    return {"status": "ok", "model": OLLAMA_MODEL}


@app.post("/chat")
def chat(request: ChatRequest):
    training_context = """
- Last 7 days: 32 km total
- 3 runs completed
- Longest run: 14 km
- Most recent run: 8 km easy
- No injury data available
""".strip()

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
