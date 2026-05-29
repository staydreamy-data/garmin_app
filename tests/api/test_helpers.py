from types import SimpleNamespace

from src.api.routers.chat import build_session_title, format_conversation_history


def test_build_session_title_returns_fallback_for_blank_message() -> None:
    assert build_session_title("   ") == "New chat"


def test_build_session_title_truncates_long_message() -> None:
    message = "This is a very long message that should be truncated for a session title"

    result = build_session_title(message, max_length=20)

    assert result == "This is a very lo..."
    assert len(result) == 20


def test_format_conversation_history_returns_fallback_for_empty_messages() -> None:
    assert format_conversation_history([]) == "No previous conversation."


def test_format_conversation_history_formats_user_and_assistant_turns() -> None:
    messages = [
        SimpleNamespace(role="user", content="How was my last run?"),
        SimpleNamespace(role="assistant", content="You kept a steady pace."),
    ]

    result = format_conversation_history(messages)

    assert result == "User: How was my last run?\nAssistant: You kept a steady pace."
