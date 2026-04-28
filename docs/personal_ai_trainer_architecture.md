# Personal AI Trainer Architecture

## Purpose

This document defines the initial infrastructure and system architecture for a local-first personalized AI running trainer built on top of Garmin training data.

The goal is to start with a small, practical MVP while keeping the design extensible enough for future additions such as RAG, MCP tools, evaluation, and richer coaching workflows.

## High-Level Goals

- Keep the stack simple enough for local development.
- Reuse the existing data engineering foundation in this repository.
- Separate analytics, application logic, model serving, and UI concerns.
- Build something that is also strong as a data engineering portfolio project.

## Suggested Infrastructure

### Core stack

- `Streamlit` for the chat UI
- `FastAPI` for backend orchestration and inference endpoints
- `Ollama` for serving a local Llama-family model
- `PostgreSQL` for sessions, chat history, prompt runs, and application metadata
- `dbt + DuckDB` for Garmin data transformation and coach-ready feature generation

### Supporting libraries

- `SQLAlchemy` for database access from FastAPI
- `Alembic` for schema migrations
- `Pydantic` for request and response validation
- `httpx` for calling the local model server if needed from FastAPI

## Architecture Layers

### 1. Data layer

This layer is responsible for ingesting and transforming Garmin data into coach-ready features.

Responsibilities:

- ingest raw Garmin data
- model and clean data through `dbt`
- produce AI-friendly training summaries
- expose consistent analytical outputs for the application layer

Examples of useful outputs:

- recent runs and workouts
- split summaries
- workout adherence
- volume and intensity trends
- recovery and fatigue indicators
- training block summaries

Primary technologies:

- `dbt`
- `DuckDB`

### 2. Application layer

This layer coordinates the user request, data retrieval, prompt construction, and model call.

Responsibilities:

- receive chat requests from the UI
- load athlete context from transformed data
- load conversation context from PostgreSQL
- construct prompts for the local model
- call the LLM runtime
- store messages and model outputs
- expose future endpoints for RAG and MCP integrations

Primary technology:

- `FastAPI`

### 3. Model serving layer

This layer isolates model execution from application logic.

Responsibilities:

- host the selected local LLM
- expose an HTTP API for inference
- allow model swaps without changing the UI or orchestration logic

Primary technology:

- `Ollama`

### 4. Presentation layer

This layer provides the user-facing chat experience.

Responsibilities:

- show chat history
- send prompts to FastAPI
- stream or render responses
- show session controls
- optionally display the context used to generate answers

Primary technology:

- `Streamlit`

### 5. Persistence layer

This layer stores operational application state.

Responsibilities:

- chat sessions
- messages
- model runs
- prompt versions
- user feedback
- future retrieval traces and evaluation metadata

Primary technology:

- `PostgreSQL`

## Separation of Responsibilities

The design should keep these concerns clearly separated:

- `DuckDB/dbt` stores analytical outputs and training features
- `PostgreSQL` stores application and conversation state
- `FastAPI` orchestrates requests and prompt assembly
- `Ollama` handles model inference
- `Streamlit` handles presentation only

This separation is important both for maintainability and for portfolio value, because it shows a clear distinction between analytics infrastructure and application infrastructure.

## End-to-End Request Flow

1. Garmin data is ingested and transformed through the existing pipeline.
2. `dbt` produces training summary tables and coach-ready features.
3. The user sends a message from `Streamlit`.
4. `Streamlit` calls a `FastAPI` endpoint.
5. `FastAPI` loads recent athlete context from transformed data.
6. `FastAPI` loads session and message history from `PostgreSQL`.
7. `FastAPI` builds a prompt for the local LLM.
8. `FastAPI` sends the prompt to `Ollama`.
9. The model response is returned to `Streamlit`.
10. The interaction is stored in `PostgreSQL`.

## Suggested MVP Scope

The first version should stay intentionally small:

- one local user
- one Streamlit chat interface
- one FastAPI backend
- one local LLM served through Ollama
- PostgreSQL-backed sessions and message history
- prompt context sourced from curated `dbt` outputs

This is enough to validate the product idea without introducing early complexity.

## Suggested Future Extensions

### Retrieval and RAG

When the MVP is stable, add retrieval over:

- training methodology notes
- curated excerpts from fundamental books
- coaching rules and heuristics
- your own summarized training history

Recommended progression:

1. start with PostgreSQL full-text search
2. add `pgvector` when semantic retrieval becomes useful

### MCP server

Later, expose structured tools such as:

- get recent long runs
- compare this week vs prior weeks
- summarize workout compliance
- explain recent fatigue trend

### Evaluation and observability

Add storage for:

- prompt templates
- model settings
- answer quality feedback
- evaluation cases
- retrieval traces

These will make the project stronger as a portfolio piece and easier to improve over time.

## Why This Is a Good Starting Design

- It is simple enough to build locally.
- It fits the Python-heavy stack already present in this repository.
- It supports clean growth into RAG and MCP later.
- It highlights both data engineering and applied AI skills.
- It demonstrates good system boundaries, which is valuable in a portfolio project.

## Recommended File Name

This document is intentionally named:

`docs/personal_ai_trainer_architecture.md`

Why this name works:

- it is explicit and easy to discover
- it reads well in a portfolio context
- it leaves room for future docs such as `rag_design.md` or `mcp_server_design.md`
