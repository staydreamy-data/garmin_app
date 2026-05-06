import os

import requests
import streamlit as st

API_URL = os.getenv("TRAINER_API_URL", "http://localhost:8000")


st.title("Personal AI Trainer")

if "messages" not in st.session_state:
    st.session_state.messages = []

if "session_id" not in st.session_state:
    st.session_state.session_id = None

if st.button("New chat"):
    # Reset the UI state so the next prompt creates a new persisted chat session.
    st.session_state.session_id = None
    st.session_state.messages = []
    st.rerun()

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
