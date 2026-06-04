"""Shared fixtures for core tests."""
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import Engine

from peerpedia_core.storage.db.engine import get_engine, init_db, get_session, Base


@pytest.fixture
def db_url():
    """Create a temporary SQLite database and return its URL."""
    with tempfile.TemporaryDirectory() as tmp:
        url = f"sqlite:///{tmp}/test.db"
        yield url


@pytest.fixture
def engine(db_url):
    """Create a fresh SQLAlchemy engine with a temporary database."""
    eng = get_engine(db_url)
    Base.metadata.drop_all(eng)  # ensure clean slate
    init_db(eng)
    yield eng
    eng.dispose()
