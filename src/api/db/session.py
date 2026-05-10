import os
from functools import lru_cache

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()


def get_database_url() -> str:
    """Read the database URL from the environment when it is actually needed.

    Returns:
        The configured SQLAlchemy database URL.

    Raises:
        ValueError: If ``DATABASE_URL`` is not set.
    """
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL is not set")
    return database_url


@lru_cache(maxsize=1)
def get_engine():
    """Create and cache the SQLAlchemy engine for the application process."""
    return create_engine(get_database_url())


@lru_cache(maxsize=1)
def get_session_local():
    """Create and cache the SQLAlchemy session factory."""
    return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)


def get_db():
    """Provide one SQLAlchemy session per request and close it afterwards.

    Yields:
        A request-scoped SQLAlchemy session connected to PostgreSQL.
    """
    session_local = get_session_local()
    db = session_local()
    try:
        yield db
    finally:
        db.close()
