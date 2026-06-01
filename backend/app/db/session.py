"""
SQLAlchemy engine + session factory.
Sync session — the rest of the code is straightforward request/response,
async adds complexity without speed-up here (Postgres calls are fast).
"""
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)
SessionLocal = sessionmaker(engine, expire_on_commit=False, autoflush=False)


@contextmanager
def db_session() -> Session:
    s = SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def get_db():
    """FastAPI dependency."""
    with db_session() as s:
        yield s
