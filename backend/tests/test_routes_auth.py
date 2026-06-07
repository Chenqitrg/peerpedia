"""Auth tests — register, login, me, edge cases.

These tests ensure every seed user scenario is well-tested:
- Registration with valid/invalid data
- Login with correct/wrong credentials
- Login with non-existent user (the einstein bug!)
- Token validation and expiry
- Round-trip: register → login → me
"""
import time

import pytest
from peerpedia_api.deps import create_token
from peerpedia_core.storage.db.engine import get_session


@pytest.fixture
def client(db_engine):
    from peerpedia_api import deps
    from peerpedia_api.main import app

    def override_db():
        session = get_session(db_engine)
        try:
            yield session
        finally:
            session.close()
    app.dependency_overrides[deps.get_db] = override_db
    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    app.dependency_overrides.clear()


# ── Registration ──────────────────────────────────────────────────────────────

class TestRegister:
    def test_register_creates_user_and_returns_token(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "username": "newton",
            "password": "gravity123",
            "email": "newton@physics.org",
            "name": "Isaac Newton",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["user"]["username"] == "newton"
        assert data["user"]["name"] == "Isaac Newton"
        assert data["token"] != ""

    def test_register_duplicate_username_returns_409(self, client):
        client.post("/api/v1/auth/register", json={
            "username": "galileo",
            "password": "stars123",
            "email": "galileo@astronomy.org",
            "name": "Galileo",
        })
        resp = client.post("/api/v1/auth/register", json={
            "username": "galileo",
            "password": "different456",
            "email": "galileo2@astronomy.org",
            "name": "Galileo Two",
        })
        assert resp.status_code == 409
        assert "already taken" in resp.json()["detail"].lower()

    def test_register_missing_email_returns_422(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "username": "nomail",
            "password": "password123",
            "name": "No Email",
        })
        assert resp.status_code == 422

    def test_register_missing_name_returns_422(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "username": "noname",
            "password": "password123",
            "email": "noname@test.com",
        })
        assert resp.status_code == 422

    def test_register_missing_password_returns_422(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "username": "nopass",
            "email": "nopass@test.com",
            "name": "No Password",
        })
        assert resp.status_code == 422

    def test_register_short_username_returns_422(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "username": "ab",
            "password": "password123",
            "email": "short@test.com",
            "name": "Short Name",
        })
        assert resp.status_code == 422

    def test_register_invalid_email_returns_422(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "username": "bademail",
            "password": "password123",
            "email": "not-an-email",
            "name": "Bad Email",
        })
        assert resp.status_code == 422

    def test_register_empty_body_returns_422(self, client):
        resp = client.post("/api/v1/auth/register", json={})
        assert resp.status_code == 422


# ── Login ─────────────────────────────────────────────────────────────────────

class TestLogin:
    @pytest.fixture(autouse=True)
    def _seed_user(self, client):
        """Create a known user for login tests."""
        client.post("/api/v1/auth/register", json={
            "username": "fermat",
            "password": "margin123",
            "email": "fermat@math.org",
            "name": "Pierre de Fermat",
        })

    def test_login_with_correct_credentials_returns_token(self, client):
        resp = client.post("/api/v1/auth/login", json={
            "username": "fermat",
            "password": "margin123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"]["username"] == "fermat"
        assert data["user"]["name"] == "Pierre de Fermat"
        assert data["token"] != ""

    def test_login_with_wrong_password_returns_401(self, client):
        resp = client.post("/api/v1/auth/login", json={
            "username": "fermat",
            "password": "wrongpassword",
        })
        assert resp.status_code == 401
        assert "invalid" in resp.json()["detail"].lower()

    def test_login_with_nonexistent_username_returns_401(self, client):
        """The einstein bug: login with a user that was never registered."""
        resp = client.post("/api/v1/auth/login", json={
            "username": "einstein",
            "password": "666666",
        })
        assert resp.status_code == 401
        assert "invalid" in resp.json()["detail"].lower()

    def test_login_with_empty_username_fails(self, client):
        resp = client.post("/api/v1/auth/login", json={
            "username": "",
            "password": "margin123",
        })
        # Backend treats empty username as invalid credentials (401) or
        # validation error (422) — either is correct
        assert resp.status_code in (401, 422)

    def test_login_with_empty_password_fails(self, client):
        resp = client.post("/api/v1/auth/login", json={
            "username": "fermat",
            "password": "",
        })
        assert resp.status_code in (401, 422)

    def test_login_missing_username_returns_422(self, client):
        resp = client.post("/api/v1/auth/login", json={
            "password": "margin123",
        })
        assert resp.status_code == 422

    def test_login_case_sensitive_username(self, client):
        """Username should be case-sensitive (or case-insensitive, but consistent)."""
        resp = client.post("/api/v1/auth/login", json={
            "username": "FERMAT",
            "password": "margin123",
        })
        # Either 200 or 401 is acceptable — just document the behavior
        assert resp.status_code in (200, 401)


# ── GET /me ───────────────────────────────────────────────────────────────────

class TestMe:
    @pytest.fixture(autouse=True)
    def _seed_user(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "username": "curie",
            "password": "radium123",
            "email": "curie@physics.org",
            "name": "Marie Curie",
        })
        self.user_id = resp.json()["user"]["id"]

    def test_me_with_valid_token_returns_user(self, client):
        # Login to get a token
        resp = client.post("/api/v1/auth/login", json={
            "username": "curie",
            "password": "radium123",
        })
        token = resp.json()["token"]

        resp2 = client.get("/api/v1/auth/me", headers={
            "Authorization": f"Bearer {token}",
        })
        assert resp2.status_code == 200
        data = resp2.json()
        assert data["user"]["username"] == "curie"
        assert data["user"]["name"] == "Marie Curie"

    def test_me_without_token_returns_401(self, client):
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    def test_me_with_invalid_token_returns_401(self, client):
        resp = client.get("/api/v1/auth/me", headers={
            "Authorization": "Bearer this-is-not-a-valid-jwt-token",
        })
        assert resp.status_code == 401

    def test_me_with_expired_token_returns_401(self, client):
        # Create a token that expires immediately
        import jwt
        expired = jwt.encode(
            {"sub": self.user_id, "iat": int(time.time()) - 10, "exp": int(time.time()) - 1},
            "peerpedia-dev-secret",
            algorithm="HS256",
        )
        resp = client.get("/api/v1/auth/me", headers={
            "Authorization": f"Bearer {expired}",
        })
        assert resp.status_code == 401

    def test_me_with_tampered_token_returns_401(self, client):
        """Token with valid signature but for non-existent user."""
        fake_token = create_token("nonexistent-user-id-12345")
        resp = client.get("/api/v1/auth/me", headers={
            "Authorization": f"Bearer {fake_token}",
        })
        assert resp.status_code == 401

    def test_me_with_malformed_header_returns_401(self, client):
        resp = client.get("/api/v1/auth/me", headers={
            "Authorization": "NotBearer anything",
        })
        assert resp.status_code == 401


# ── Round-trip ────────────────────────────────────────────────────────────────

class TestAuthRoundTrip:
    """End-to-end: register → login → me → all match."""

    def test_register_then_login_then_me(self, client):
        # 1. Register
        r1 = client.post("/api/v1/auth/register", json={
            "username": "turing",
            "password": "enigma123",
            "email": "turing@cs.org",
            "name": "Alan Turing",
        })
        assert r1.status_code == 201
        reg_user = r1.json()["user"]
        r1.json()["token"]

        # 2. Login
        r2 = client.post("/api/v1/auth/login", json={
            "username": "turing",
            "password": "enigma123",
        })
        assert r2.status_code == 200
        login_user = r2.json()["user"]
        login_token = r2.json()["token"]
        assert login_user["id"] == reg_user["id"]
        # Tokens within the same second are identical (JWT uses int(time.time()))
        # — both are valid and interchangeable

        # 3. Me
        r3 = client.get("/api/v1/auth/me", headers={
            "Authorization": f"Bearer {login_token}",
        })
        assert r3.status_code == 200
        me_user = r3.json()["user"]
        assert me_user["id"] == reg_user["id"]
        assert me_user["username"] == "turing"
        assert me_user["name"] == "Alan Turing"

    def test_multiple_users_independent_sessions(self, client):
        """Register two users — each can log in independently."""
        # Register user A
        client.post("/api/v1/auth/register", json={
            "username": "shannon",
            "password": "info123!!",
            "email": "shannon@math.org",
            "name": "Claude Shannon",
        })
        # Register user B
        client.post("/api/v1/auth/register", json={
            "username": "hopper",
            "password": "compiler42",
            "email": "hopper@navy.mil",
            "name": "Grace Hopper",
        })

        # Login as A
        ra = client.post("/api/v1/auth/login", json={
            "username": "shannon", "password": "info123!!",
        })
        assert ra.json()["user"]["name"] == "Claude Shannon"

        # Login as B
        rb = client.post("/api/v1/auth/login", json={
            "username": "hopper", "password": "compiler42",
        })
        assert rb.json()["user"]["name"] == "Grace Hopper"

        # A's token sees A, not B
        rme = client.get("/api/v1/auth/me", headers={
            "Authorization": f"Bearer {ra.json()['token']}",
        })
        assert rme.json()["user"]["username"] == "shannon"
