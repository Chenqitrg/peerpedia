"""Shared fixtures for backend tests."""
import tempfile

import pytest
from peerpedia_api.deps import create_token
from peerpedia_core.storage.db.engine import Base, get_engine, init_db
from peerpedia_core.storage.db.models import *  # noqa: F401,F403 — register all models


@pytest.fixture
def db_engine():
    """Temporary SQLite database for backend integration tests."""
    with tempfile.TemporaryDirectory() as tmp:
        db_url = f"sqlite:///{tmp}/test.db"
        eng = get_engine(db_url)
        Base.metadata.drop_all(eng)
        init_db(eng)
        yield eng
        eng.dispose()


@pytest.fixture
def auth_header():
    """Return a helper that creates an Authorization header for a user ID."""
    def _make(user_id: str) -> dict:
        token = create_token(user_id)
        return {"Authorization": f"Bearer {token}"}
    return _make
