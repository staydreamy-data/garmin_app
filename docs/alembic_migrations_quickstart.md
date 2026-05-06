# Alembic Migrations Quickstart

This is a short guide for running database migrations in this project.

It is specific to the current setup:

- `uv` for Python environment and commands
- PostgreSQL running in Docker Compose
- connection settings loaded from repo-root `.env`
- SQLAlchemy models under `src/api/db`
- Alembic config in `alembic/` and `alembic.ini`

## 1. Prerequisites

Make sure these are true before running migrations:

- PostgreSQL is started with Docker Compose
- `.env` contains valid Postgres settings, including `DATABASE_URL`
- Alembic is installed in the project environment
- a Postgres driver is installed for SQLAlchemy

Typical `.env` values look like:

```env
POSTGRES_DB=garmin_app
POSTGRES_USER=garmin_app
POSTGRES_PASSWORD=your_real_password
POSTGRES_PORT=5435

DATABASE_URL=postgresql+psycopg://garmin_app:your_real_password@localhost:5435/garmin_app
```

If needed, install missing DB tooling with:

```bash
uv pip install alembic "psycopg[binary]"
```

## 2. Start PostgreSQL

From the repo root:

```bash
docker compose up -d
docker compose ps
```

The `postgres` service should be running or healthy.

If you want an extra check:

```bash
docker compose exec postgres sh -lc 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

## 3. Where Alembic Reads Schema From

Alembic is already configured to:

- load environment variables from `.env`
- read `DATABASE_URL`
- import `Base` from `src/api/db/base.py`
- import models from `src/api/db/models.py`

This means Alembic compares the database against the SQLAlchemy models in:

- [base.py](/Users/evgeni/Documents/GitHub/garmin_app/src/api/db/base.py)
- [models.py](/Users/evgeni/Documents/GitHub/garmin_app/src/api/db/models.py)

## 4. Create a Migration

After changing SQLAlchemy models, generate a migration from the repo root:

```bash
uv run alembic revision --autogenerate -m "create chat memory tables"
```

This creates a new migration file under `alembic/versions/`.

Important:

- always review the generated migration before applying it
- do not assume autogenerate is always correct

## 5. Apply Migrations

Run:

```bash
uv run alembic upgrade head
```

This applies all pending migrations to the Postgres database referenced by `DATABASE_URL`.

## 6. Verify the Tables

You can verify from inside the Postgres container:

```bash
docker compose exec postgres sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "\dt"'
```

To inspect the Alembic version table:

```bash
docker compose exec postgres sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT * FROM alembic_version;"'
```

## 7. Common Commands

Show current migration version:

```bash
uv run alembic current
```

Show migration history:

```bash
uv run alembic history
```

Upgrade to latest:

```bash
uv run alembic upgrade head
```

Rollback one migration:

```bash
uv run alembic downgrade -1
```

## 8. Common Problems

### `alembic: command not found`

Run Alembic through `uv`:

```bash
uv run alembic upgrade head
```

### `DATABASE_URL is not set`

Make sure:

- `.env` exists in the repo root
- `DATABASE_URL` is defined there
- you are running the command from the repo root

### Postgres container is not running

Check:

```bash
docker compose ps -a
docker compose logs postgres
```

### Port conflict on `5432`

Use a different host port in `.env`, for example:

```env
POSTGRES_PORT=5435
DATABASE_URL=postgresql+psycopg://garmin_app:your_real_password@localhost:5435/garmin_app
```

### Postgres 18 volume/layout issue

This project uses `postgres:18`, which expects the volume mounted at:

```yaml
/var/lib/postgresql
```

If you previously initialized the volume with an older Postgres layout, a fresh local reset may be required:

```bash
docker compose down -v
docker compose up -d
```

Warning: `down -v` deletes local database data.

## 9. Recommended Workflow In This Project

When you change DB models:

1. Update `src/api/db/models.py`
2. Generate a migration with `uv run alembic revision --autogenerate -m "..."`
3. Review the migration file
4. Apply it with `uv run alembic upgrade head`
5. Verify tables in Postgres
6. Only then wire the new schema into FastAPI logic

This keeps schema changes explicit and versioned instead of relying on one-off SQL scripts.
