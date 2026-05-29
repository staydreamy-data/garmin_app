from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
import requests
from fastapi.testclient import TestClient

from src.api import main
from src.api.db.session import get_db
from src.api.routers import chat as chat_router


class FakeOllamaResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {
            "response": "Focus on easy mileage and consistency.",
            "prompt_eval_count": 12,
            "eval_count": 8,
        }


def fake_chat_session(session_id, title=None, summary=None, summarized_message_count=0):
    return SimpleNamespace(
        id=session_id,
        title=title,
        summary=summary,
        summarized_message_count=summarized_message_count,
    )


@pytest.fixture
def client():
    dummy_db = object()
    main.app.dependency_overrides[get_db] = lambda: dummy_db

    with TestClient(main.app) as test_client:
        yield test_client, dummy_db

    main.app.dependency_overrides.clear()


def test_chat_creates_new_session_when_session_id_is_missing(
    monkeypatch, client
) -> None:
    test_client, dummy_db = client
    session_id = uuid4()
    user_message_id = uuid4()
    assistant_message_id = uuid4()
    run_id = uuid4()

    created_session = fake_chat_session(session_id)
    llm_run = SimpleNamespace(id=run_id, status="started")
    created_messages: list[tuple[str, str]] = []
    success_updates: list[dict] = []

    monkeypatch.setattr(
        chat_router,
        "create_chat_session",
        lambda db: created_session,
    )
    monkeypatch.setattr(
        chat_router,
        "get_messages_by_session",
        lambda db, current_session_id, limit=20: [],
    )
    monkeypatch.setattr(
        chat_router.training_context_service,
        "get_latest_training_context",
        lambda: "Latest run on 2026-05-01: steady aerobic run.",
    )

    def fake_create_chat_message(db, session_id, role, content):
        created_messages.append((role, content))
        message_id = user_message_id if role == "user" else assistant_message_id
        return SimpleNamespace(id=message_id, role=role, content=content)

    monkeypatch.setattr(chat_router, "create_chat_message", fake_create_chat_message)
    monkeypatch.setattr(
        chat_router,
        "update_chat_session_title",
        lambda db, session, title: fake_chat_session(
            session.id,
            title=title,
            summary=session.summary,
            summarized_message_count=session.summarized_message_count,
        ),
    )
    monkeypatch.setattr(
        chat_router,
        "create_llm_run",
        lambda db, session_id, user_message_id, model_name: llm_run,
    )

    def fake_update_llm_run_success(
        db,
        llm_run,
        assistant_message_id,
        prompt_tokens=None,
        completion_tokens=None,
        total_tokens=None,
        duration_ms=None,
    ):
        success_updates.append(
            {
                "assistant_message_id": assistant_message_id,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            }
        )
        return llm_run

    monkeypatch.setattr(
        chat_router, "update_llm_run_success", fake_update_llm_run_success
    )
    monkeypatch.setattr(
        chat_router.ollama_client,
        "generate",
        lambda *args, **kwargs: FakeOllamaResponse().json(),
    )

    response = test_client.post("/chat", json={"message": "Help me improve my 10K"})

    assert response.status_code == 200
    assert response.json()["session_id"] == str(session_id)
    assert response.json()["answer"] == "Focus on easy mileage and consistency."
    assert created_messages == [
        ("user", "Help me improve my 10K"),
        ("assistant", "Focus on easy mileage and consistency."),
    ]
    assert len(success_updates) == 1
    assert success_updates[0]["assistant_message_id"] == assistant_message_id
    assert success_updates[0]["prompt_tokens"] == 12
    assert success_updates[0]["completion_tokens"] == 8
    assert success_updates[0]["total_tokens"] == 20


def test_chat_reuses_existing_session_when_session_id_is_provided(
    monkeypatch, client
) -> None:
    test_client, dummy_db = client
    session_id = uuid4()
    user_message_id = uuid4()
    assistant_message_id = uuid4()
    existing_session = fake_chat_session(session_id, title="Existing chat")
    llm_run = SimpleNamespace(id=uuid4(), status="started")
    session_lookup_calls: list[UUID] = []

    def fake_get_chat_session(db, requested_session_id):
        session_lookup_calls.append(requested_session_id)
        return existing_session

    monkeypatch.setattr(chat_router, "get_chat_session", fake_get_chat_session)
    monkeypatch.setattr(
        chat_router,
        "get_messages_by_session",
        lambda db, current_session_id, limit=20: [
            SimpleNamespace(role="user", content="How was my last interval session?"),
            SimpleNamespace(role="assistant", content="You handled the pace well."),
        ],
    )
    monkeypatch.setattr(
        chat_router.training_context_service,
        "get_latest_training_context",
        lambda: "Latest run on 2026-05-01: interval session with good pacing.",
    )

    def fake_create_chat_message(db, session_id, role, content):
        message_id = user_message_id if role == "user" else assistant_message_id
        return SimpleNamespace(id=message_id, role=role, content=content)

    monkeypatch.setattr(chat_router, "create_chat_message", fake_create_chat_message)
    monkeypatch.setattr(
        chat_router,
        "create_llm_run",
        lambda db, session_id, user_message_id, model_name: llm_run,
    )
    monkeypatch.setattr(
        chat_router, "update_llm_run_success", lambda *args, **kwargs: llm_run
    )
    monkeypatch.setattr(
        chat_router.ollama_client,
        "generate",
        lambda *args, **kwargs: FakeOllamaResponse().json(),
    )

    response = test_client.post(
        "/chat",
        json={
            "session_id": str(session_id),
            "message": "What should I focus on next week?",
        },
    )

    assert response.status_code == 200
    assert response.json()["session_id"] == str(session_id)
    assert session_lookup_calls == [session_id]


def test_chat_returns_404_for_unknown_session(monkeypatch, client) -> None:
    test_client, dummy_db = client
    session_id = uuid4()

    monkeypatch.setattr(
        chat_router, "get_chat_session", lambda db, requested_session_id: None
    )

    response = test_client.post(
        "/chat",
        json={
            "session_id": str(session_id),
            "message": "Can you continue this session?",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Session not found"


def test_chat_marks_llm_run_failed_when_ollama_request_fails(
    monkeypatch, client
) -> None:
    test_client, dummy_db = client
    session_id = uuid4()
    user_message_id = uuid4()
    llm_run = SimpleNamespace(id=uuid4(), status="started")
    failure_updates: list[dict] = []

    monkeypatch.setattr(
        chat_router,
        "create_chat_session",
        lambda db: fake_chat_session(session_id),
    )
    monkeypatch.setattr(
        chat_router,
        "get_messages_by_session",
        lambda db, current_session_id, limit=20: [],
    )
    monkeypatch.setattr(
        chat_router.training_context_service,
        "get_latest_training_context",
        lambda: "Latest run on 2026-05-01: easy recovery run.",
    )
    monkeypatch.setattr(
        chat_router,
        "create_chat_message",
        lambda db, session_id, role, content: SimpleNamespace(
            id=user_message_id if role == "user" else uuid4(),
            role=role,
            content=content,
        ),
    )
    monkeypatch.setattr(
        chat_router,
        "update_chat_session_title",
        lambda db, session, title: fake_chat_session(
            session.id,
            title=title,
            summary=session.summary,
            summarized_message_count=session.summarized_message_count,
        ),
    )
    monkeypatch.setattr(
        chat_router,
        "create_llm_run",
        lambda db, session_id, user_message_id, model_name: llm_run,
    )

    def fake_update_llm_run_failure(db, llm_run, error_message, duration_ms=None):
        failure_updates.append(
            {
                "llm_run": llm_run,
                "error_message": error_message,
                "duration_ms": duration_ms,
            }
        )
        return llm_run

    monkeypatch.setattr(
        chat_router, "update_llm_run_failure", fake_update_llm_run_failure
    )

    def raise_request_exception(*args, **kwargs):
        raise requests.RequestException("Ollama is unavailable")

    monkeypatch.setattr(chat_router.ollama_client, "generate", raise_request_exception)

    response = test_client.post("/chat", json={"message": "What should I do tomorrow?"})

    assert response.status_code == 502
    assert "Ollama request failed" in response.json()["detail"]
    assert len(failure_updates) == 1
    assert failure_updates[0]["llm_run"] is llm_run
    assert failure_updates[0]["error_message"] == "Ollama is unavailable"
    assert failure_updates[0]["duration_ms"] is not None
