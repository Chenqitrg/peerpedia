"""Tests for user, identity, and reputation API endpoints."""

import tempfile
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from peerpedia.web.app import app
from peerpedia_core.storage.db import get_engine, get_session, init_db


def _setup_test_db(tmp_path):
    """Create a test database and return the database URL."""
    db_path = tmp_path / "test.db"
    engine = get_engine(f"sqlite:///{db_path}")
    init_db(engine)
    # Pre-create a session to ensure tables exist, then close
    session = get_session(engine)
    session.close()
    return f"sqlite:///{db_path}"


class TestUserAPI:

    def test_create_user(self):
        """POST /api/v1/users should create a user."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url = _setup_test_db(Path(tmp))

            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                client = TestClient(app)

                resp = client.post("/api/v1/users", json={
                    "id": "testuser",
                    "name": "Test User",
                    "email": "test@example.com",
                    "affiliation": "MIT",
                    "expertise": ["physics", "math"],
                })
                assert resp.status_code == 200
                data = resp.json()
                assert data["id"] == "testuser"
                assert data["name"] == "Test User"

    def test_get_user(self):
        """GET /api/v1/users/{user_id} should return user info."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url = _setup_test_db(Path(tmp))

            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                client = TestClient(app)

                # Create user first
                client.post("/api/v1/users", json={
                    "id": "alice", "name": "Alice", "email": "alice@test.com",
                })

                resp = client.get("/api/v1/users/alice")
                assert resp.status_code == 200
                data = resp.json()
                assert data["id"] == "alice"
                assert data["name"] == "Alice"

    def test_get_user_not_found(self):
        """GET /api/v1/users/{user_id} should 404 for unknown user."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url = _setup_test_db(Path(tmp))

            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                client = TestClient(app)
                resp = client.get("/api/v1/users/nobody")
                assert resp.status_code == 404

    def test_create_identity(self):
        """POST /api/v1/users/{user_id}/identities should bind identity."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url = _setup_test_db(Path(tmp))

            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                client = TestClient(app)

                client.post("/api/v1/users", json={
                    "id": "bob", "name": "Bob", "email": "bob@test.com",
                })

                resp = client.post("/api/v1/users/bob/identities", json={
                    "type": "orcid",
                    "value": "0000-0001-2345-6789",
                    "verified": True,
                })
                assert resp.status_code == 200
                data = resp.json()
                assert data["type"] == "orcid"
                assert data["verified"] is True

    def test_create_identity_user_not_found(self):
        """POST /api/v1/users/{user_id}/identities should 404 if user missing."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url = _setup_test_db(Path(tmp))

            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                client = TestClient(app)
                resp = client.post("/api/v1/users/ghost/identities", json={
                    "type": "orcid",
                    "value": "0000-0002-3456-7890",
                })
                assert resp.status_code == 404

    def test_get_reputation(self):
        """GET /api/v1/users/{user_id}/reputation should return ReputationVector."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url = _setup_test_db(Path(tmp))

            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                client = TestClient(app)

                client.post("/api/v1/users", json={
                    "id": "charlie", "name": "Charlie", "email": "c@test.com",
                })

                resp = client.get("/api/v1/users/charlie/reputation")
                assert resp.status_code == 200
                data = resp.json()
                assert data["user_id"] == "charlie"
                assert "academic_contribution" in data
                assert "review_quality" in data
                assert "collaboration_spirit" in data
                assert "education_outreach" in data
                assert "total_points" in data

    def test_get_reputation_nonexistent_user(self):
        """GET /api/v1/users/{user_id}/reputation should return zeros for unknown user."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url = _setup_test_db(Path(tmp))

            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                client = TestClient(app)

                resp = client.get("/api/v1/users/nobody/reputation")
                assert resp.status_code == 200
                data = resp.json()
                assert data["user_id"] == "nobody"
                assert data["academic_contribution"] == 0.0
