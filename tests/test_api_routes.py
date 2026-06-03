"""API route integration tests for under-tested endpoints.

Focus: citations (21% before), collab (38%), articles (39%).
All API routes live under /api/v1/ prefix.
"""

import tempfile
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient


# ── Helpers ────────────────────────────────────────────────────────────────────

def _setup_db_with_article(tmp_path: str, author: str = "testuser"):
    """Create a test DB with one submitted article. Returns (db_url, article_id)."""
    from peerpedia.submit import submit_article

    base = Path(tmp_path)
    db_path = base / "test.db"
    articles_dir = base / "articles"
    articles_dir.mkdir()
    db_url = f"sqlite:///{db_path}"

    source = base / "test.md"
    source.write_text(f"""---
title: Test Article by {author}
abstract: An article for API testing.
---

# Test Article

Content paragraph.
""")
    result = submit_article(
        source_path=source,
        database_url=db_url,
        articles_dir=articles_dir,
        author_name=author,
    )
    assert result.success, f"submit_article failed: {result.error}"
    return db_url, result.article_id


def _setup_two_articles(tmp_path: str):
    """Create two articles (A cites B). Returns (db_url, a_id, b_id)."""
    from peerpedia.submit import submit_article

    base = Path(tmp_path)
    db_path = base / "test.db"
    articles_dir = base / "articles"
    articles_dir.mkdir()
    db_url = f"sqlite:///{db_path}"

    source_b = base / "b.md"
    source_b.write_text("""---
title: Article B
abstract: This is the article being cited.
---

# Article B

Key results that others cite.
""")
    result_b = submit_article(
        source_path=source_b, database_url=db_url, articles_dir=articles_dir,
        author_name="author_b",
    )
    assert result_b.success

    source_a = base / "a.md"
    source_a.write_text(f"""---
title: Article A
abstract: This article cites B.
---

# Article A

See also peerpedia:{result_b.article_id} for background.
""")
    result_a = submit_article(
        source_path=source_a, database_url=db_url, articles_dir=articles_dir,
        author_name="author_a",
    )
    assert result_a.success

    return db_url, result_a.article_id, result_b.article_id


def _setup_empty_db(tmp_path: str):
    """Create an empty initialized DB. Returns db_url."""
    from peerpedia_core.storage.db import get_engine, init_db

    base = Path(tmp_path)
    db_path = base / "test.db"
    db_url = f"sqlite:///{db_path}"
    engine = get_engine(db_url)
    init_db(engine)
    return db_url


# ── Article API tests ──────────────────────────────────────────────────────────

class TestArticleListAPI:
    """GET /api/v1/articles — list all articles."""

    def test_list_articles_returns_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_url, _ = _setup_db_with_article(tmp, "testuser")
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                resp = client.get("/api/v1/articles")
                assert resp.status_code == 200
                data = resp.json()
                assert "articles" in data
                assert data["total"] >= 1

    def test_list_articles_empty_db(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_url = _setup_empty_db(tmp)
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                resp = client.get("/api/v1/articles")
                assert resp.status_code == 200
                data = resp.json()
                assert data["total"] == 0
                assert data["articles"] == []


class TestArticleGetAPI:
    """GET /api/v1/articles/{id} — get single article."""

    def test_get_article_returns_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_url, article_id = _setup_db_with_article(tmp, "testuser")
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                resp = client.get(f"/api/v1/articles/{article_id}")
                assert resp.status_code == 200
                data = resp.json()
                assert data["id"] == article_id
                assert "title" in data

    def test_get_article_404(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_url, _ = _setup_db_with_article(tmp, "testuser")
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                resp = client.get("/api/v1/articles/nonexistent")
                assert resp.status_code == 404


class TestArticleHealthAPI:
    """GET /api/v1/health — health check."""

    def test_health_returns_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_url, _ = _setup_db_with_article(tmp, "testuser")
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                resp = client.get("/api/v1/health")
                assert resp.status_code == 200
                data = resp.json()
                assert data["status"] == "ok"


# ── Citation API tests ─────────────────────────────────────────────────────────

class TestCitationClickAPI:
    """POST /api/v1/citations/click — record a citation click."""

    def test_record_click_between_articles(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_url, a_id, b_id = _setup_two_articles(tmp)
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                resp = client.post("/api/v1/citations/click", data={
                    "from_article_id": a_id,
                    "to_article_id": b_id,
                    "node_id": "test-node",
                })
                assert resp.status_code == 200
                data = resp.json()
                assert data["status"] == "recorded"

    def test_record_click_self_referential_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_url, a_id, _ = _setup_two_articles(tmp)
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                resp = client.post("/api/v1/citations/click", data={
                    "from_article_id": a_id,
                    "to_article_id": a_id,
                })
                assert resp.status_code == 400

    def test_record_click_with_user_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_url, a_id, b_id = _setup_two_articles(tmp)
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                resp = client.post("/api/v1/citations/click", data={
                    "from_article_id": a_id,
                    "to_article_id": b_id,
                    "user_id": "test-viewer",
                    "node_id": "node-1",
                })
                assert resp.status_code == 200


class TestCitationTransitionsAPI:
    """GET /api/v1/citations/transitions — transition probabilities."""

    def test_get_transitions_after_click(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_url, a_id, b_id = _setup_two_articles(tmp)
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                client.post("/api/v1/citations/click", data={
                    "from_article_id": a_id, "to_article_id": b_id,
                })
                resp = client.get(
                    f"/api/v1/citations/transitions?article_id={a_id}&source=local"
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["article_id"] == a_id
                assert data["total_clicks"] >= 1

    def test_get_transitions_invalid_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_url, a_id, _ = _setup_two_articles(tmp)
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                resp = client.get(
                    f"/api/v1/citations/transitions?article_id={a_id}&source=invalid"
                )
                assert resp.status_code == 400

    def test_get_transitions_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_url, a_id, _ = _setup_two_articles(tmp)
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                resp = client.get(
                    f"/api/v1/citations/transitions?article_id={a_id}&source=local"
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["total_clicks"] == 0


class TestArticleCitationsAPI:
    """GET /api/v1/articles/{id}/citations — citation graph for article page."""

    def test_get_citations_for_article(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_url, a_id, _ = _setup_two_articles(tmp)
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                resp = client.get(f"/api/v1/articles/{a_id}/citations")
                assert resp.status_code == 200
                data = resp.json()
                assert "cites" in data
                assert "cited_by" in data


# ── Edit proposal API tests ────────────────────────────────────────────────────

class TestProposalListAPI:
    """GET /api/v1/articles/{id}/proposals — list edit proposals."""

    def test_list_proposals_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_url, article_id = _setup_db_with_article(tmp, "testuser")
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                resp = client.get(f"/api/v1/articles/{article_id}/proposals")
                assert resp.status_code == 200
                data = resp.json()
                assert "proposals" in data

    def test_list_proposals_nonexistent_article(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_url, _ = _setup_db_with_article(tmp, "testuser")
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                resp = client.get("/api/v1/articles/nonexistent/proposals")
                assert resp.status_code == 404


class TestProposalReviewAPI:
    """POST /api/v1/proposals/{id}/review — review an edit proposal."""

    def test_review_nonexistent_proposal(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_url, _ = _setup_db_with_article(tmp, "testuser")
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                resp = client.post(
                    "/api/v1/proposals/nonexistent/review",
                    data={"decision": "approved", "reviewer_id": "reviewer1"},
                )
                # Returns 400 (proposal not found → bad request)
                assert resp.status_code in (400, 404)


class TestProposalMergeAPI:
    """POST /api/v1/proposals/{id}/merge — merge an approved proposal."""

    def test_merge_nonexistent_proposal(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_url, _ = _setup_db_with_article(tmp, "testuser")
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                resp = client.post("/api/v1/proposals/nonexistent/merge")
                # Returns 422 (missing article_id param → FastAPI validation)
                assert resp.status_code in (400, 404, 422)


# ── Collaboration API tests ────────────────────────────────────────────────────

class TestCollaborationStatusAPI:
    """GET /api/v1/articles/{id}/collaboration/{reviewer}."""

    def test_collaboration_status_no_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_url, article_id = _setup_db_with_article(tmp, "testuser")
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                resp = client.get(
                    f"/api/v1/articles/{article_id}/collaboration/reviewer-x"
                )
                assert resp.status_code == 200

    def test_collaboration_status_nonexistent_article(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_url, _ = _setup_db_with_article(tmp, "testuser")
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                resp = client.get(
                    "/api/v1/articles/nonexistent/collaboration/some-reviewer"
                )
                # Returns 200 with collaboration_accepted=False for non-existent article
                assert resp.status_code == 200


# ── User API tests ─────────────────────────────────────────────────────────────

class TestUserCreateAPI:
    """POST /api/v1/users — register a new user."""

    def test_create_user(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_url = _setup_empty_db(tmp)
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                resp = client.post("/api/v1/users", json={
                    "id": "newuser",
                    "name": "New User",
                    "email": "new@example.com",
                })
                assert resp.status_code == 200
                data = resp.json()
                assert data["id"] == "newuser"

    def test_create_user_missing_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_url = _setup_empty_db(tmp)
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                resp = client.post("/api/v1/users", json={"id": "partial"})
                assert resp.status_code == 422


class TestUserGetAPI:
    """GET /api/v1/users/{id} — get user profile."""

    def test_get_user_after_create(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_url = _setup_empty_db(tmp)
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                client.post("/api/v1/users", json={
                    "id": "testuser",
                    "name": "Test User",
                    "email": "test@example.com",
                })
                resp = client.get("/api/v1/users/testuser")
                assert resp.status_code == 200
                data = resp.json()
                assert data["id"] == "testuser"

    def test_get_user_404(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_url = _setup_empty_db(tmp)
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                resp = client.get("/api/v1/users/nonexistent")
                assert resp.status_code == 404


# ── Review API tests ───────────────────────────────────────────────────────────

class TestReviewsListAPI:
    """GET /api/v1/articles/{id}/reviews — list reviews."""

    def test_list_reviews_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_url, article_id = _setup_db_with_article(tmp, "testuser")
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                resp = client.get(f"/api/v1/articles/{article_id}/reviews")
                assert resp.status_code == 200

    def test_list_reviews_nonexistent_article(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_url, _ = _setup_db_with_article(tmp, "testuser")
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                resp = client.get("/api/v1/articles/nonexistent/reviews")
                assert resp.status_code == 404


class TestDecideAPI:
    """POST /api/v1/articles/{id}/decide — decide on article."""

    def test_decide_nonexistent_article(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_url, _ = _setup_db_with_article(tmp, "testuser")
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                resp = client.post("/api/v1/articles/nonexistent/decide", data={
                    "decision": "accept",
                })
                # Returns 400 (article not found treated as invalid state)
                assert resp.status_code in (400, 404)
