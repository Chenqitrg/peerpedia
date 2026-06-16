# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""xspec: Server connectivity specification tests.

SPEC S1 — Health endpoint responds when server is running.
  Given  server is running
  When   client sends GET /health
  Then   response is 200 with {"status":"ok"}
  And    CORS header allows tauri://localhost

SPEC S4 — Full API chain with seed data works.
  Given  server is running with seed data (23 users, 25 articles)
  When   user logs in as einstein / 666666
  Then   pool returns articles, feed returns activity

SPECIFICATION STATUS = LOCKED.
These tests define product behavior. If implementation makes them fail,
assume the implementation is wrong — not the spec.
"""
import pytest
from fastapi.testclient import TestClient
from peerpedia_core.storage.db.engine import get_engine, get_session

pytestmark = pytest.mark.seed
# ── S1 fixtures (empty test DB — health doesn't need data) ──────────────


@pytest.fixture
def client(db_engine):
    """TestClient with DB override — fresh empty DB per test."""
    from peerpedia_api import deps
    from peerpedia_api.main import app

    def override_db():
        session = get_session(db_engine)
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[deps.get_db] = override_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ── S1: Health endpoint ─────────────────────────────────────────────────


class TestSpecS1HealthEndpoint:  # noqa: N801
    """SPEC S1: Server liveness probe responds on GET /health."""

    def test_health_returns_200_ok(self, client):
        """Given a running server, /health returns 200 with status ok."""
        resp = client.get("/health")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        assert resp.json() == {"status": "ok"}

    def test_health_cors_allows_tauri_origin(self, client):
        """Tauri webview origin must be allowed by CORS for health checks."""
        resp = client.get("/health", headers={"Origin": "tauri://localhost"})
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == "tauri://localhost"


# ── S4 fixtures (real seed DB) ──────────────────────────────────────────


@pytest.fixture(scope="module")
def seed_engine():
    """Connect to the seed database (peerpedia.db in project root)."""
    import os
    db_path = os.environ.get("PEERPEDIA_DB", "peerpedia.db")
    db_url = f"sqlite:///{db_path}"
    eng = get_engine(db_url)
    yield eng
    eng.dispose()


@pytest.fixture
def seed_client(seed_engine):
    """TestClient wired to the real seed database."""
    from peerpedia_api import deps
    from peerpedia_api.main import app

    def override_db():
        session = get_session(seed_engine)
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[deps.get_db] = override_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ── S4: Seed data full-chain smoke test ─────────────────────────────────


class TestSpecS4SeedDataAccessible:  # noqa: N801
    """SPEC S4: Seed users and articles are accessible through the API."""

    def test_seed_user_einstein_can_login(self, seed_client):
        """Given seed data, einstein/666666 logs in and gets a JWT token."""
        resp = seed_client.post("/api/v1/auth/login", json={
            "username": "einstein",
            "password": "666666",
        })
        assert resp.status_code == 200, f"Login failed: {resp.json()}"
        data = resp.json()
        assert "token" in data, "Response must include a JWT token"
        assert data["user"]["username"] == "einstein"

    def test_pool_returns_non_empty_list(self, seed_client):
        """Given einstein is logged in, GET /pool returns articles."""
        r = seed_client.post("/api/v1/auth/login", json={
            "username": "einstein",
            "password": "666666",
        })
        token = r.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        resp = seed_client.get("/api/v1/pool", headers=headers)
        assert resp.status_code == 200, f"Pool failed: {resp.json()}"
        data = resp.json()
        articles = data.get("articles", [])
        assert len(articles) > 0, f"Pool returned 0 articles — seed data may be stale. Got: {data}"

    def test_feed_returns_list(self, seed_client):
        """Given einstein is logged in, GET /feed returns activity."""
        r = seed_client.post("/api/v1/auth/login", json={
            "username": "einstein",
            "password": "666666",
        })
        token = r.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        resp = seed_client.get("/api/v1/feed", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        articles = data.get("articles", [])
        assert len(articles) > 0, f"Feed returned 0 articles — seed data may be stale. Got: {data}"
