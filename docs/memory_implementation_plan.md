# Self-Implemented Memory Plan

## Summary

Implement v1 memory as persistent chat sessions backed by PostgreSQL, without LlamaIndex or vector memory. The goal is to let a user start a conversation, close the app, resume the same session later, and have the LLM answer using prior conversation context plus the existing Garmin training context from DuckDB.

This version should stay intentionally simple:

- store sessions and messages in PostgreSQL
- load recent conversation history on every `/chat` request
- inject that history into the Ollama prompt
- keep Streamlit thin and FastAPI responsible for orchestration
- defer semantic recall, embeddings, and RAG-specific retrieval to later phases

## Implementation Changes

### Persistence and schema

- Add PostgreSQL as the application-state database, separate from DuckDB analytics storage.
- Add `SQLAlchemy`, `Alembic`, and a Postgres driver to the app dependencies.
- Introduce two tables only for v1:
  - `chat_sessions`
  - `chat_messages`
- `chat_sessions` fields:
  - `id` as UUID primary key
  - `title` as nullable text
  - `created_at`
  - `updated_at`
- `chat_messages` fields:
  - `id` as UUID primary key
  - `session_id` as foreign key to `chat_sessions.id`
  - `role` constrained to `user` or `assistant`
  - `content` as text
  - `created_at`
- Create an index on `chat_messages.session_id, created_at` for ordered history reads.
- Do not add summary fields, embeddings, metadata blobs, or feedback tables in v1.

### Backend API and prompt flow

- Keep the existing FastAPI app in [src/api/main.py](/Users/evgeni/Documents/GitHub/garmin_app/src/api/main.py) as the orchestration entrypoint.
- Add a database session factory and repository-style helper functions for session and message CRUD.
- Change the chat contract so the client sends:
  - `session_id` as optional on first message, required for resumed conversations
  - `message` as the new user prompt
- `/chat` behavior:
  - if `session_id` is missing, create a new session
  - persist the user message before model invocation
  - load the last N messages for that session ordered ascending
  - load existing Garmin training context from DuckDB
  - build one prompt from:
    - fixed system instructions
    - training context
    - recent conversation transcript
    - current user message
  - call Ollama
  - persist the assistant reply
  - return `session_id` and `answer`
- Add a `GET /sessions` endpoint that lists sessions ordered by `updated_at DESC`.
- Add a `GET /sessions/{session_id}/messages` endpoint that returns the full message history for UI resume.
- Keep `/health` unchanged except for optionally reporting DB connectivity later if desired.
- Use a fixed recent-history window in v1:
  - default to the last 12 messages
  - if fewer exist, use all available messages
- Do not implement summarization or token-based truncation in v1; use count-based truncation only.

### UI behavior

- Update [src/ui/app.py](/Users/evgeni/Documents/GitHub/garmin_app/src/ui/app.py) so Streamlit no longer treats `st.session_state.messages` as the source of truth.
- Persist only UI state needed for the active session selection and currently rendered messages.
- On initial page load:
  - fetch available sessions from FastAPI
  - show a "new chat" action and a list of resumable sessions
- On selecting a session:
  - fetch historical messages from FastAPI
  - render them in order
  - store the selected `session_id` in Streamlit session state
- On sending a new user message:
  - call `/chat` with `session_id` and `message`
  - append returned assistant response to the rendered chat
  - if the session was newly created, store the returned `session_id`
- Session titles in v1:
  - default to the first user message truncated to a short display length
  - compute this in FastAPI when the first user message is saved
  - do not add rename/delete UI in v1

### Configuration and boundaries

- Add environment variables for PostgreSQL connection settings, preferably one full `DATABASE_URL`.
- Keep DuckDB as the source for training context only.
- Keep PostgreSQL as the source for chat state only.
- Keep prompt assembly inside FastAPI, not in Streamlit.
- Keep Ollama invocation logic centralized in the backend.

## Public Interfaces

- `POST /chat`
  - request:
    - `session_id: str | null`
    - `message: str`
  - response:
    - `session_id: str`
    - `answer: str`
- `GET /sessions`
  - response: ordered list of session summaries with `id`, `title`, `created_at`, `updated_at`
- `GET /sessions/{session_id}/messages`
  - response: ordered list of messages with `role`, `content`, `created_at`

## Test Plan

- Add backend tests for session creation:
  - first `/chat` call without `session_id` creates a session and returns its ID
  - first user message is stored
  - assistant reply is stored
- Add backend tests for session resume:
  - later `/chat` call with an existing `session_id` reuses that session
  - prior messages are included in prompt construction
  - `updated_at` changes on new activity
- Add backend tests for list/history endpoints:
  - `/sessions` returns newest active session first
  - `/sessions/{session_id}/messages` returns ordered transcript
- Add prompt assembly tests:
  - prompt includes Garmin training context
  - prompt includes only the last N messages
  - empty history path still works for a brand-new session
- Add error-path tests:
  - unknown `session_id` returns 404
  - Ollama failure returns 502 and does not create an assistant message
  - DB connection failure surfaces as 500-level API error
- Add a simple UI smoke test plan if no Streamlit automation is added yet:
  - create new chat
  - reload app
  - reopen prior session
  - send follow-up question
  - confirm reply reflects prior conversation

## Assumptions and Defaults

- PostgreSQL is the only persistence layer for memory.
- v1 memory means resumable chat threads, not semantic memory.
- No LlamaIndex, Mem0, pgvector, or embeddings are included in v1.
- Recent history is capped by message count, not token count.
- One local user is assumed; no auth or multi-user tenancy is included.
- Session titles are auto-generated from the first user message.
- The plan assumes the repo will add database dependencies and migrations before implementation starts.
- Future extensions should layer on top of this design:
  - session summaries as a new nullable field or related table
  - semantic recall via `pgvector`
  - RAG and MCP as separate additions, not part of v1 memory
