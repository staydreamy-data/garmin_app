import os

import requests
import streamlit as st

API_URL = os.getenv("TRAINER_API_URL", "http://localhost:8000")

def fetch_sessions():
    response = requests.get(f"{API_URL}/sessions", timeout=30)
    response.raise_for_status()
    return response.json()


def fetch_session_messages(session_id: str):
    response = requests.get(f"{API_URL}/sessions/{session_id}/messages", timeout=30)
    response.raise_for_status()
    return response.json()


st.title("Personal AI Trainer")

# state initialization
if "messages" not in st.session_state:
    st.session_state.messages = []

if "session_id" not in st.session_state:
    st.session_state.session_id = None

if "loaded_session_id" not in st.session_state:
    st.session_state.loaded_session_id = None

if st.button("New chat"):
    st.session_state.session_id = None
    st.session_state.loaded_session_id = None
    st.session_state.messages = []
    st.rerun()

with st.sidebar:
    st.subheader("Saved sessions")

    try:
        sessions = fetch_sessions()
    except requests.RequestException as exc:
        sessions = []
        st.error(f"Could not load sessions: {exc}")

    session_options = {
        session["session_id"]: session["title"] or "Untitled session"
        for session in sessions
    }

    selected_session_id = st.radio(
        "Resume a session",
        options=[None] + list(session_options.keys()),
        format_func=lambda session_id: (
            "Current chat"
            if session_id is None
            else session_options[session_id]
        ),
    )

if (
    selected_session_id is not None
    and selected_session_id != st.session_state.loaded_session_id
):
    try:
        stored_messages = fetch_session_messages(selected_session_id)
        st.session_state.messages = stored_messages
        st.session_state.session_id = selected_session_id
        st.session_state.loaded_session_id = selected_session_id
        st.rerun()
    except requests.RequestException as exc:
        st.error(f"Could not load session messages: {exc}")

st.caption(f"Current session: {st.session_state.session_id}")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

if prompt := st.chat_input("Ask about your training"):
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.write(prompt)

    try:
        response = requests.post(
            f"{API_URL}/chat",
            json={"session_id": st.session_state.session_id, "message": prompt},
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        st.session_state.session_id = payload["session_id"]
        answer = payload["answer"]

    except requests.RequestException as exc:
        answer = f"Backend error: {exc}"

    st.session_state.messages.append({"role": "assistant", "content": answer})

    with st.chat_message("assistant"):
        st.write(answer)
