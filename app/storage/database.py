from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

Base = declarative_base()

_ENGINE = None
_SESSION_FACTORY = None


def init_database(database_url: str) -> None:
    global _ENGINE, _SESSION_FACTORY
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    _ENGINE = create_engine(database_url, future=True, connect_args=connect_args)
    _SESSION_FACTORY = sessionmaker(bind=_ENGINE, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=_ENGINE)


def get_session() -> Session:
    if _SESSION_FACTORY is None:
        raise RuntimeError("Database not initialized. Call init_database first.")
    return _SESSION_FACTORY()


def session_scope() -> Iterator[Session]:
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
