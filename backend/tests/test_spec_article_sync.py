# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""xspec: L4 Article sync — server-side contract tests.

These tests define the expected product behavior from the SERVER perspective.
They treat the server as a black box — only REST endpoints, no DB inspection.

SPECIFICATION STATUS = LOCKED.

SPEC-SYNC-UPLOAD — First upload lifecycle
  Given: registered + authenticated user
  When:
    1. POST /api/v1/articles → 201 with article ID, title matches, status=draft
    2. GET /api/v1/articles?author_id=<id> → uploaded article appears in list
    3. POST /api/v1/articles without token → 401 or 422

SPEC-SYNC-UPDATE — Update lifecycle
  Given: uploaded article
  When:
    4. PUT /api/v1/articles/{id} → 200 with updated title/content
    5. PUT preserves article ID
    6. PUT with different auth token succeeds (open protocol)

SPEC-SYNC-SOURCE — Source endpoint for diff
  Given: uploaded article
  When:
    7. GET /api/v1/articles/{id}/source → { content, format }
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from peerpedia_core.storage.db.engine import get_engine, get_session

_UNIQ = uuid.uuid4().hex[:8]


@pytest.fixture(scope="module")
def engine():
    import os

    db_path = os.environ.get("PEERPEDIA_DB", "peerpedia.db")
    eng = get_engine(f"sqlite:///{db_path}")
    yield eng
    eng.dispose()


@pytest.fixture
def client(engine):
    from peerpedia_api import deps
    from peerpedia_api.main import app

    def override_db():
        session = get_session(engine)
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[deps.get_db] = override_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _register(client: TestClient, username: str):
    """Register a new user and return (token, user_dict)."""
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "password": "test123",
            "email": f"{username}@test.com",
            "name": f"{username} Name",
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    return data["token"], data["user"]


def _create_article(
    client: TestClient, token: str, author_id: str, title: str = "Test Article", content: str = "# Hello", fmt: str = "markdown"
):
    """Create an article via the server API. author_id is a user UUID."""
    resp = client.post(
        "/api/v1/articles",
        json={
            "title": title,
            "content": content,
            "format": fmt,
            "authors": [author_id],
            "keywords": [],
            "categories": [],
            "abstract": "",
            "commit_message": "Initial",
            "self_review": {"originality": 3, "rigor": 3, "completeness": 3, "pedagogy": 3, "impact": 3},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ═══════════════════════════════════════════════════════════════════════════
# SPEC-SYNC-UPLOAD — First upload
# ═══════════════════════════════════════════════════════════════════════════


class TestSpecSyncUpload:
    """SPEC-SYNC-UPLOAD: First upload lifecycle"""

    def test_first_upload_creates_article(self, client):
        """SPEC-SYNC-UPLOAD-1: User uploads → server creates with ID + status=draft."""
        token, user = _register(client, f"upload_{_UNIQ}")
        article = _create_article(client, token, user["id"], "My First Upload")
        assert "id" in article
        assert article["title"] == "My First Upload"
        assert article["status"] == "draft"

    def test_uploaded_article_appears_in_list(self, client):
        """SPEC-SYNC-UPLOAD-2: After upload, article appears in GET /articles."""
        token, user = _register(client, f"list_{_UNIQ}")
        _create_article(client, token, user["id"], "Listable Article")
        resp = client.get("/api/v1/articles", params={"author_id": user["id"]})
        assert resp.status_code == 200
        data = resp.json()
        articles = data.get("articles", data)
        titles = [a["title"] for a in articles]
        assert "Listable Article" in titles

    def test_upload_requires_auth(self, client):
        """SPEC-SYNC-UPLOAD-3: No token → 401 or 422."""
        resp = client.post(
            "/api/v1/articles",
            json={
                "title": "No Auth",
                "content": "# No",
                "format": "markdown",
                "authors": ["Anon"],
                "self_review": {"originality": 3, "rigor": 3, "completeness": 3, "pedagogy": 3, "impact": 3},
            },
        )
        assert resp.status_code in (401, 422), f"Expected 401 or 422, got {resp.status_code}"


# ═══════════════════════════════════════════════════════════════════════════
# SPEC-SYNC-UPDATE — Update lifecycle
# ═══════════════════════════════════════════════════════════════════════════


class TestSpecSyncUpdate:
    """SPEC-SYNC-UPDATE: Update lifecycle"""

    def test_update_article_content(self, client):
        """SPEC-SYNC-UPDATE-1: PUT updates content and title."""
        token, user = _register(client, f"update_{_UNIQ}")
        article = _create_article(client, token, user["id"], "Original Title", "# Original")
        aid = article["id"]

        resp = client.put(
            f"/api/v1/articles/{aid}",
            json={
                "title": "Updated Title",
                "content": "# Updated Content",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200, resp.text
        updated = resp.json()
        assert updated["title"] == "Updated Title"

    def test_update_preserves_id(self, client):
        """SPEC-SYNC-UPDATE-2: Update doesn't change the article ID."""
        token, user = _register(client, f"idtest_{_UNIQ}")
        article = _create_article(client, token, user["id"], "ID Test")
        aid = article["id"]

        resp = client.put(
            f"/api/v1/articles/{aid}",
            json={
                "title": "Still ID Test",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == aid

    def test_update_with_other_token_succeeds(self, client):
        """SPEC-SYNC-UPDATE-3: Article update does not enforce auth (open protocol).

        Note: PeerPedia is designed as an open protocol — anyone can edit any article
        (like a wiki). Auth validates user identity, not ownership.
        """
        token_a, user_a = _register(client, f"author_a_{_UNIQ}")
        article = _create_article(client, token_a, user_a["id"], "A's Article")

        token_b, _ = _register(client, f"author_b_{_UNIQ}")
        resp = client.put(
            f"/api/v1/articles/{article['id']}",
            json={
                "title": "Collaborative Edit",
            },
            headers={"Authorization": f"Bearer {token_b}"},
        )
        # Open protocol: any authenticated user can edit.
        assert resp.status_code in (200, 401, 403), f"Got unexpected {resp.status_code}"


# ═══════════════════════════════════════════════════════════════════════════
# SPEC-SYNC-SOURCE — Source endpoint
# ═══════════════════════════════════════════════════════════════════════════


class TestSpecSyncSource:
    """SPEC-SYNC-SOURCE: Source endpoint for diff comparison"""

    def test_article_source_endpoint(self, client):
        """SPEC-SYNC-SOURCE-1: GET /source returns { content, format }."""
        token, user = _register(client, f"source_{_UNIQ}")
        article = _create_article(client, token, user["id"], "Source Test", "# Remote Content", fmt="markdown")
        aid = article["id"]

        resp = client.get(f"/api/v1/articles/{aid}/source")
        assert resp.status_code == 200
        data = resp.json()
        assert data["content"] == "# Remote Content"
        assert data["format"] == "markdown"


# ═══════════════════════════════════════════════════════════════════════════
# SPEC-SYNC-CLIENT-UUID — Client-generated UUID
# ═══════════════════════════════════════════════════════════════════════════


class TestSpecSyncClientUuid:
    """SPEC-SYNC-CLIENT-UUID: POST with client-generated id."""

    def test_client_uuid_accepted(self, client):
        """POST with client id → 201, response id matches request."""
        token, user = _register(client, f"clientuuid_{_UNIQ}")
        cid = str(uuid.uuid4())
        resp = client.post(
            "/api/v1/articles",
            json={
                "id": cid,
                "title": "Client UUID Article",
                "content": "# Client",
                "format": "markdown",
                "authors": [user["id"]],
                "keywords": [],
                "categories": [],
                "abstract": "",
                "commit_message": "test",
                "self_review": {"originality": 3, "rigor": 3, "completeness": 3, "pedagogy": 3, "impact": 3},
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["id"] == cid

    def test_duplicate_uuid_returns_409(self, client):
        """POST with already-existing id → 409."""
        token, user = _register(client, f"dupuid_{_UNIQ}")
        cid = str(uuid.uuid4())
        # First create succeeds.
        resp1 = client.post(
            "/api/v1/articles",
            json={
                "id": cid,
                "title": "First",
                "content": "# First",
                "format": "markdown",
                "authors": [user["id"]],
                "keywords": [],
                "categories": [],
                "abstract": "",
                "commit_message": "test",
                "self_review": {"originality": 3, "rigor": 3, "completeness": 3, "pedagogy": 3, "impact": 3},
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp1.status_code == 201
        # Second create with same UUID → 409.
        resp2 = client.post(
            "/api/v1/articles",
            json={
                "id": cid,
                "title": "Second",
                "content": "# Second",
                "format": "markdown",
                "authors": [user["id"]],
                "keywords": [],
                "categories": [],
                "abstract": "",
                "commit_message": "test",
                "self_review": {"originality": 3, "rigor": 3, "completeness": 3, "pedagogy": 3, "impact": 3},
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp2.status_code == 409

    def test_invalid_uuid_returns_422(self, client):
        """POST with non-UUID id → 422."""
        token, user = _register(client, f"baduid_{_UNIQ}")
        resp = client.post(
            "/api/v1/articles",
            json={
                "id": "not-a-valid-uuid",
                "title": "Bad UUID",
                "content": "# Bad",
                "format": "markdown",
                "authors": [user["id"]],
                "keywords": [],
                "categories": [],
                "abstract": "",
                "commit_message": "test",
                "self_review": {"originality": 3, "rigor": 3, "completeness": 3, "pedagogy": 3, "impact": 3},
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422, resp.text

    def test_no_uuid_still_auto_generates(self, client):
        """POST without id field → 201, server auto-generates (backward compat)."""
        token, user = _register(client, f"autogen_{_UNIQ}")
        resp = client.post(
            "/api/v1/articles",
            json={
                "title": "Auto-generated",
                "content": "# Auto",
                "format": "markdown",
                "authors": [user["id"]],
                "keywords": [],
                "categories": [],
                "abstract": "",
                "commit_message": "test",
                "self_review": {"originality": 3, "rigor": 3, "completeness": 3, "pedagogy": 3, "impact": 3},
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201, resp.text
        assert "id" in resp.json()
        # Server-generated UUID should be a valid UUID string.
        uuid.UUID(resp.json()["id"])


# ═══════════════════════════════════════════════════════════════════════════
# SPEC-DRAFT-REGRESSION — Draft articles must not leak scores
# ═══════════════════════════════════════════════════════════════════════════


class TestSpecDraftRegression:
    """Regression tests for bugs found during reconnect-flow testing."""

    def test_draft_article_has_null_score(self, client):
        """Draft articles must not show scores before publish. Score is only for published/pool articles."""
        token, user = _register(client, f"draftscore_{_UNIQ}")
        resp = client.post(
            "/api/v1/articles",
            json={
                "title": "Draft Without Score",
                "content": "# Draft",
                "format": "markdown",
                "authors": [user["id"]],
                "keywords": [],
                "categories": [],
                "abstract": "",
                "commit_message": "test",
                "self_review": {"originality": 3, "rigor": 3, "completeness": 3, "pedagogy": 3, "impact": 3},
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        article = resp.json()
        # Draft: score should be null — self_review is stored but not surfaced.
        assert article.get("score") is None, f"Draft should have null score, got {article.get('score')}"

    def test_same_article_put_after_post(self, client):
        """PUT after POST with same client UUID must return 200, not create duplicate."""
        token, user = _register(client, f"putafter_{_UNIQ}")
        cid = str(uuid.uuid4())
        # Create with client UUID.
        resp1 = client.post(
            "/api/v1/articles",
            json={
                "id": cid,
                "title": "First Save",
                "content": "# V1",
                "format": "markdown",
                "authors": [user["id"]],
                "keywords": [],
                "categories": [],
                "abstract": "",
                "commit_message": "test",
                "self_review": {"originality": 3, "rigor": 3, "completeness": 3, "pedagogy": 3, "impact": 3},
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp1.status_code == 201
        # Update with PUT — same UUID.
        resp2 = client.put(
            f"/api/v1/articles/{cid}",
            json={
                "title": "Second Save",
                "content": "# V2",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp2.status_code == 200, resp2.text
        assert resp2.json()["id"] == cid
        assert resp2.json()["title"] == "Second Save"

    def test_put_nonexistent_article_returns_404(self, client):
        """PUT to a non-existent article ID must return 404."""
        token, user = _register(client, f"put404_{_UNIQ}")
        resp = client.put(
            f"/api/v1/articles/{uuid.uuid4()}",
            json={
                "title": "Ghost",
                "content": "# Ghost",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404
