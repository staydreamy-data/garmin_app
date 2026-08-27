import requests
import logging
from src.api.services.training_context import training_context_service
from src.api.services.prompting import (
    build_session_title,
    build_summary_prompt,
    format_conversation_history,
    build_chat_prompt
)
from src.api.schemas.chat import ChatResponse, ChatRequest
from sqlalchemy.orm import Session
from src.api.db.crud import (
    get_messages_by_session,
    create_chat_message,
    create_chat_session,
    get_chat_session,
    update_chat_session_title,
    create_llm_run,
    update_llm_run_success,
    update_llm_run_failure,
    update_chat_session_summary,
)
from src.api.clients.ollama import OllamaClient
import time
from src.api.core.settings import get_settings


ollama_client = OllamaClient()
settings = get_settings()





class SessionNotFoundError(Exception):
    pass


class LLMProviderError(Exception):
    pass


class ChatService:
    def __init__(self, db: Session) -> None:
        self._db_session = db
        self._chat_session = None

    def generate_session_summary(self, existing_summary: str | None, messages_to_compact) -> str:
        """Generate an updated compacted summary for older session history."""
        prompt = build_summary_prompt(existing_summary, messages_to_compact)
        data = ollama_client.generate(
            prompt=prompt,
            num_predict=settings.summary_num_predict,
            temperature=settings.summary_temperature,
        )
        return data["response"].strip()

    def maybe_compact_session_context(self) -> None:
        """Compact older chat turns into a stored session summary.

        This runs after a successful assistant response. It never deletes raw messages.
        """
        all_messages = list(get_messages_by_session(self._db_session, self._chat_session.id))
        total_messages = len(all_messages)

        if total_messages <= settings.compaction_trigger_message_count:
            return

        unsummarized_messages = all_messages[self._chat_session.summarized_message_count :]

        if len(unsummarized_messages) <= settings.recent_raw_message_limit:
            return

        messages_to_compact = unsummarized_messages[: -settings.recent_raw_message_limit]
        if not messages_to_compact:
            return

        updated_summary = self.generate_session_summary(
            self._chat_session.summary, messages_to_compact
        )

        update_chat_session_summary(
            db=self._db_session,
            session=self._chat_session,
            summary=updated_summary,
            summarized_message_count=self._chat_session.summarized_message_count
            + len(messages_to_compact),
        )

    def handle_chat_turn(self, request: ChatRequest) -> ChatResponse:

        if request.session_id is None:
            self._chat_session = create_chat_session(self._db_session)
        else:
            self._chat_session = get_chat_session(self._db_session, request.session_id)
            if self._chat_session is None:
                raise SessionNotFoundError

        all_session_messages = list(get_messages_by_session(self._db_session, self._chat_session.id))
        unsummarized_messages = all_session_messages[
            self._chat_session.summarized_message_count :
        ]
        recent_messages = unsummarized_messages[-settings.recent_raw_message_limit :]

        conversation_history = format_conversation_history(recent_messages)
        session_summary = self._chat_session.summary or "No previous summary."

        user_message = create_chat_message(
            db=self._db_session,
            session_id=self._chat_session.id,
            role="user",
            content=request.message,
        )

        if not self._chat_session.title:
            title = build_session_title(request.message)
            self._chat_session = update_chat_session_title(self._db_session, self._chat_session, title)

        llm_run = create_llm_run(
            db=self._db_session,
            session_id=self._chat_session.id,
            user_message_id=user_message.id,
            model_name=ollama_client.model,
        )

        started_at = time.perf_counter()

        training_context = training_context_service.get_latest_training_context()

        prompt = build_chat_prompt(
            training_context=training_context,
            session_summary=session_summary,
            conversation_history=conversation_history,
            user_message=request.message,
        )

        try:
            data = ollama_client.generate(
                prompt=prompt,
                num_predict=settings.chat_num_predict,
                temperature=settings.chat_temperature,
            )
        except requests.RequestException as exc:
            duration_ms = int((time.perf_counter() - started_at) * 1000)

            update_llm_run_failure(
                db=self._db_session,
                llm_run=llm_run,
                error_message=str(exc),
                duration_ms=duration_ms,
            )

            raise LLMProviderError(f"Ollama request failed: {exc}") from exc

        answer = data["response"]

        assistant_message = create_chat_message(
            db=self._db_session,
            session_id=self._chat_session.id,
            role="assistant",
            content=answer,
        )

        duration_ms = int((time.perf_counter() - started_at) * 1000)

        update_llm_run_success(
            db=self._db_session,
            llm_run=llm_run,
            assistant_message_id=assistant_message.id,
            prompt_tokens=data.get("prompt_eval_count"),
            completion_tokens=data.get("eval_count"),
            total_tokens=(
                (data.get("prompt_eval_count") or 0) + (data.get("eval_count") or 0)
                if data.get("prompt_eval_count") is not None
                or data.get("eval_count") is not None
                else None
            ),
            duration_ms=duration_ms,
        )

        try:
            self.maybe_compact_session_context()
        except requests.RequestException:
            logging.exception(
                "Session compaction failed because the summarization call to Ollama failed."
            )
        except Exception:
            logging.exception("Session compaction failed unexpectedly.")

        return ChatResponse(session_id=self._chat_session.id, answer=answer)
