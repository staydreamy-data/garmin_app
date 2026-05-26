
import requests
import os

API_URL = os.getenv("TRAINER_API_URL", "http://localhost:8000")

def api_get(path: str):
    """Helper to make GET requests to the backend API."""
    response = requests.get(f"{API_URL}{path}", timeout=30)
    response.raise_for_status()
    return response.json()

def api_post(payload: dict):
    """Helper to make POST requests to the backend API."""
    response = requests.post(
        f"{API_URL}/chat",
        json=payload,
        timeout=180,
    )
    response.raise_for_status()
    return response.json()

def fetch_sessions() -> list:
    """Fetch available chat sessions from the persistent memory."""
    return api_get("/sessions")

def fetch_session_messages(session_id: str) -> list:
    """Fetch messages from a specific chat session."""
    return api_get(f"/sessions/{session_id}/messages")

def send_chat_message(payload: dict):
    return api_post(payload)