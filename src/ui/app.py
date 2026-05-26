import requests
import streamlit as st
from api_client import (
    fetch_sessions,
    fetch_session_messages,
    send_chat_message,
)


DEFAULT_SESSION_STATE = {
    "messages": [],
    "session_id": None,
    "loaded_session_id": None,
}


def initialize_state():

    for key, value in DEFAULT_SESSION_STATE.items():
        if key not in st.session_state:
            st.session_state[key] = value


def start_new_chat():
    for key, value in DEFAULT_SESSION_STATE.items():
        st.session_state[key] = value


def render_messages():
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])


def render_sidebar():
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

        options = [None] + list(session_options.keys())

        current_index = (
            options.index(st.session_state.loaded_session_id)
            if st.session_state.loaded_session_id in options
            else 0
        )

        selected_session_id = st.radio(
            "Resume a session",
            options=options,
            index=current_index,
            format_func=lambda session_id: (
                "Current chat" if session_id is None else session_options[session_id]
            ),
        )

        return selected_session_id


st.title("Personal AI Trainer")

initialize_state()

if st.button("New chat"):
    start_new_chat()
    st.rerun()

selected_session_id = render_sidebar()

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


render_messages()

if prompt := st.chat_input("Ask about your training"):
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.write(prompt)

    try:
        payload = send_chat_message(
            {"session_id": st.session_state.session_id, "message": prompt}
        )
        st.session_state.session_id = payload["session_id"]
        answer = payload["answer"]

    except requests.RequestException as exc:
        st.error(f"Backend error: {exc}")

    else:
        st.session_state.messages.append({"role": "assistant", "content": answer})

        with st.chat_message("assistant"):
            st.write(answer)
