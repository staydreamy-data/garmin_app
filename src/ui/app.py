import streamlit as st
import requests

st.title("Personal AI Trainer")

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

if prompt := st.chat_input("Ask about your training"):
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.write(prompt)

    response = requests.post(
        "http://localhost:8000/chat",
        json={"message": prompt},
        timeout=30,
    )
    answer = response.json()["answer"]

    st.session_state.messages.append({"role": "assistant", "content": answer})

    with st.chat_message("assistant"):
        st.write(answer)
