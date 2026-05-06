# Personal AI Trainer

A local-first AI running coach built on top of Garmin training data. Garmin raw data ingestion is semi-automated and the deliverables contain summarised training data prepared for AI consumption. 

## What It Does
- ingest Garmin data
- transform it with Airflow/dbt/DuckDB
- expose a Streamlit chat UI
- call a local Ollama model through FastAPI
- persist chat sessions/messages/LLM runs in Postgres

## Architecture
- `Streamlit` for the chat UI
- `FastAPI` for orchestration
- `Ollama` for local LLM inference
- `PostgreSQL` for persistent chat memory and LLM run tracking
- `DuckDB`/`dbt` for Garmin training context and analytics
- `Airflow` for ingesting data from Garmin account and orchestrating the raw data transformation and dbt runs.

## Current State

Implemented:
- `Airflow` pipeline for ingesting Garmin data and orchestrating downstream transformations
- local Airflow development using `Astronomer Astro`
ata into parquet format, within Pydantic validations
- medallion architecture in `duckdb-dbt`, where the last layer contains the aggregated context for AI
- `Streamlit` chat UI for interacting with the trainer
- `FastAPI` backend that orchestrates prompt construction and local LLM calls
- `Ollama` integration for local model inference
- PostgreSQL-backed chat memory with persisted:
  - chat sessions
  - chat messages
  - LLM run metadata such as status, latency, and token usage
- Session-aware chat flow where the same conversation can continue across messages
- Training-context injection from DuckDB into the prompt
- Alembic-based database migrations for application state

Current limitations:
- data layer is not yet completed. While the trainings text summary is ready, it requires to add more technical models for storing weekly and monthly volume.
- saved AI sessions cannot yet be browsed and resumed from the UI
- memory is based on recent message history, without summarization yet
- RAG over training articles/books is not implemented yet
- MCP server is not implemented yet

## Local Setup

This project is developed locally with `uv` for Python dependencies, `docker compose` for the application Postgres instance, `Ollama` for local LLM inference, and `Astronomer Astro` for the Airflow-based ingestion pipeline.

### Prerequisites

Make sure the following tools are installed locally:

- `uv`
- `Docker` and `docker compose`
- `Ollama`
- `Astronomer Astro` if you want to run the Airflow ingestion pipeline

### 1. Install Python dependencies

From the repo root:

```bash
uv sync --extra airflow-tests
```

### 2. Configure environment variables
Create a local `.env` file in the repo root.
Follow the structure of `.env.example` file

### 3. Run the Airflow ingestion pipeline with Astro
The data pipeline part of the project is developed locally with Astronomer Astro.

Navigate to astro folder.

To start the Airflow environment:
```bash
astro dev start
```

This runs the local Airflow services and exposes the Airflow UI on http://localhost:8080.

Use this part when you want to:
- ingest Garmin data
- orchestrate raw-to-landing transformations

### 4. DBT setup

```bash
cd dbt
uv run dbt deps
uv run dbt debug
uv run dbt build
```

### 5. Start PostgreSQL
The AI application uses a dedicated Postgres instance for chat memory and LLM run tracking.
```bash
docker compose up -d
docker compose ps
```

### 6. Run database migrations
Apply the Alembic migrations to create the application tables:

```
uv run alembic upgrade head
```
For more details, see alembic_migrations_quickstart.md.

### 7. LLM step 
Start Ollama locally and ensure the configured model is available.

### 8. Start the FastAPI backend
`uv run uvicorn src.api.main:app --reload --port 8000`

### 9. Start the Streamlit UI
In a separate terminal:

`uv run streamlit run src/ui/app.py`

At this point, the chat application should be available locally with:

FastAPI on http://localhost:8000
Streamlit on the default Streamlit local URL
