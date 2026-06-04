"""Shared fixtures for backend tests."""
import tempfile
from pathlib import Path

import pytest
from peerpedia_core.storage.db.engine import get_engine, init_db, Base
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
