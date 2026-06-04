"""FastAPI dependency injection."""
from sqlalchemy.orm import Session

from peerpedia_core.storage.db.engine import get_engine, get_session

_engine = None


def get_db():
    """Yield a database session. Engine is cached across requests."""
    global _engine
    if _engine is None:
        _engine = get_engine("sqlite:///peerpedia.db")
    session = get_session(_engine)
    try:
        yield session
    finally:
        session.close()
