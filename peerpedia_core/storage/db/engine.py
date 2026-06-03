"""Database engine, session factory, and utility types.

Provides:
- JSONList / JSONDict type decorators for SQLite
- Engine creation with WAL mode + foreign keys
- Session factory
- Declarative Base
"""

from __future__ import annotations

import json

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.types import Text, TypeDecorator

# ── JSON column types for list/dict fields ───────────────────────────────────

class JSONList(TypeDecorator):
    """Store Python list as JSON string in SQLite."""
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return json.dumps(value, ensure_ascii=False)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return json.loads(value)


class JSONDict(TypeDecorator):
    """Store Python dict as JSON string in SQLite."""
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return json.dumps(value, ensure_ascii=False)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return json.loads(value)


# ── Base + Engine ────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


def get_engine(database_url: str) -> Engine:
    """Create a SQLAlchemy engine. Uses SQLite with WAL mode for concurrency."""
    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False} if "sqlite" in database_url else {},
        echo=False,
    )
    if "sqlite" in database_url:
        from sqlalchemy import event

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def init_db(engine: Engine) -> None:
    """Create all tables if they don't exist."""
    Base.metadata.create_all(engine)


def get_session(engine: Engine) -> Session:
    """Create a new session bound to the given engine."""
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()
