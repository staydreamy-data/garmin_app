
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


def build_chat_prompt(training_context: str, session_summary: str, conversation_history: str, user_message: str) -> str:
    return f"""
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
    {user_message}
    """.strip()