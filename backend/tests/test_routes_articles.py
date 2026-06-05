"""Integration tests for article API routes."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from peerpedia_core.storage.db.engine import get_session
from peerpedia_core.storage.db.models import User, Article


@pytest.fixture
def client(db_engine):
    from peerpedia_api.main import app
    from peerpedia_api import deps

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


@pytest.fixture
def seed_user(db_engine):
    s = get_session(db_engine)
    u = User(username="user21", password_hash="", name="测试用户", anonymous_name="anon_test", affiliation="测试大学")
    s.add(u)
    s.commit()
    uid = u.id
    s.close()
    return uid


@pytest.fixture
def seed_article(db_engine, seed_user):
    s = get_session(db_engine)
    a = Article(status="published", authors=[seed_user], fork_count=0)
    s.add(a)
    s.commit()
    aid = a.id
    s.close()
    return aid


class TestListArticles:
    def test_empty_list(self, client):
        resp = client.get("/api/v1/articles")
        assert resp.status_code == 200
        assert resp.json()["articles"] == []

    def test_list_with_articles(self, client, seed_article):
        resp = client.get("/api/v1/articles")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["articles"]) >= 1
        assert data["articles"][0]["id"] == seed_article

    def test_filter_by_status(self, client, seed_article):
        resp = client.get("/api/v1/articles?status=published")
        assert resp.status_code == 200
        for a in resp.json()["articles"]:
            assert a["status"] == "published"

    def test_filter_nonexistent_status(self, client):
        resp = client.get("/api/v1/articles?status=draft")
        assert resp.status_code == 200
        assert resp.json()["articles"] == []


class TestGetArticle:
    def test_get_existing(self, client, seed_article):
        resp = client.get(f"/api/v1/articles/{seed_article}")
        assert resp.status_code == 200
        assert resp.json()["id"] == seed_article

    def test_get_nonexistent(self, client):
        resp = client.get("/api/v1/articles/nonexistent")
        assert resp.status_code == 404


class TestCreateArticle:
    def test_create_minimal(self, client, seed_user):
        body = {
            "authors": [seed_user],
            "self_review": {"originality": 4, "rigor": 3, "completeness": 4,
                            "pedagogy": 3, "impact": 3},
        }
        resp = client.post("/api/v1/articles", json=body)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "sedimentation"
        assert data["authors"][0]["id"] == seed_user
        assert data["sink_eta"] is not None

    def test_create_missing_self_review(self, client, seed_user):
        resp = client.post("/api/v1/articles", json={"authors": [seed_user]})
        assert resp.status_code == 422


class TestUpdateArticle:
    def test_update_content_flow(self, client, seed_user):
        """Full flow: create article, then edit it."""
        create_body = {
            "authors": [seed_user],
            "content": "# Original\n\nHello world.",
            "format": "markdown",
            "self_review": {"originality": 4, "rigor": 3, "completeness": 4,
                            "pedagogy": 3, "impact": 3},
        }
        resp = client.post("/api/v1/articles", json=create_body)
        assert resp.status_code == 201
        article_id = resp.json()["id"]

        # Now edit it
        edit_body = {
            "content": "# Edited\n\nUpdated content.",
            "self_review": {"originality": 5, "rigor": 4, "completeness": 5,
                            "pedagogy": 4, "impact": 4},
        }
        resp2 = client.put(f"/api/v1/articles/{article_id}", json=edit_body)
        assert resp2.status_code == 200
        data = resp2.json()
        assert data["id"] == article_id
        assert data["status"] == "sedimentation"

    def test_update_no_content_change(self, client, seed_user):
        """Edit without content change: still commits and re-enters pool."""
        create_body = {
            "authors": [seed_user],
            "content": "# Test",
            "format": "markdown",
            "self_review": {"originality": 3, "rigor": 3, "completeness": 3,
                            "pedagogy": 3, "impact": 3},
        }
        resp = client.post("/api/v1/articles", json=create_body)
        assert resp.status_code == 201
        article_id = resp.json()["id"]

        # Edit without changing content
        edit_body = {
            "self_review": {"originality": 4, "rigor": 4, "completeness": 4,
                            "pedagogy": 4, "impact": 4},
        }
        resp2 = client.put(f"/api/v1/articles/{article_id}", json=edit_body)
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "sedimentation"

    def test_update_nonexistent(self, client):
        resp = client.put("/api/v1/articles/nonexistent", json={"content": "x"})
        assert resp.status_code == 404

    def test_update_no_repo(self, client, seed_user, db_engine):
        """Update article that has no git repo (edge case)."""
        from peerpedia_core.storage.db.engine import get_session
        from peerpedia_core.storage.db.models import Article

        s = get_session(db_engine)
        a = Article(status="draft", authors=[seed_user])
        s.add(a)
        s.commit()
        aid = a.id
        s.close()

        resp = client.put(f"/api/v1/articles/{aid}", json={"content": "x"})
        assert resp.status_code == 400


class TestHistoryWithScores:
    def test_history_includes_per_commit_scores(self, client, seed_user):
        """GET /articles/{id}/history should include score for each commit."""
        create_body = {
            "authors": [seed_user],
            "content": "# V1\n\nFirst version.",
            "format": "markdown",
            "self_review": {"originality": 4, "rigor": 3, "completeness": 4,
                            "pedagogy": 3, "impact": 3},
        }
        resp = client.post("/api/v1/articles", json=create_body)
        article_id = resp.json()["id"]

        history = client.get(f"/api/v1/articles/{article_id}/history")
        assert history.status_code == 200
        data = history.json()
        assert len(data["commits"]) >= 1
        # Each commit should have a score field
        for commit in data["commits"]:
            assert "score" in commit
            # The latest commit should have a score (from self-review)
            if commit == data["commits"][0]:
                assert commit["score"] is not None

    def test_history_multiple_commits_independent_scores(self, client, seed_user):
        """After editing, each commit gets its own score."""
        create_body = {
            "authors": [seed_user],
            "content": "# V1",
            "format": "markdown",
            "self_review": {"originality": 3, "rigor": 3, "completeness": 3,
                            "pedagogy": 3, "impact": 3},
        }
        resp = client.post("/api/v1/articles", json=create_body)
        article_id = resp.json()["id"]

        # Edit to create second commit
        edit_body = {
            "content": "# V2\n\nEdited.",
            "self_review": {"originality": 5, "rigor": 4, "completeness": 5,
                            "pedagogy": 4, "impact": 4},
        }
        client.put(f"/api/v1/articles/{article_id}", json=edit_body)

        history = client.get(f"/api/v1/articles/{article_id}/history")
        data = history.json()
        assert len(data["commits"]) >= 2

        # Latest commit should have score from the edit self-review
        latest = data["commits"][0]
        assert latest["score"] is not None
        assert latest["score"]["originality"] == 5.0

        # Older commit should have its own score
        older = data["commits"][1]
        assert older["score"] is not None
        assert older["score"]["originality"] == 3.0


class TestScoreBackfill:
    def test_article_without_score_gets_backfilled(self, client, seed_user, db_engine):
        """Article with null score gets backfilled on fetch."""
        from peerpedia_core.storage.db.engine import get_session
        from peerpedia_core.storage.db.models import Article

        # Create article via API (now creates score automatically)
        create_body = {
            "authors": [seed_user],
            "content": "# Backfill test",
            "format": "markdown",
            "self_review": {"originality": 4, "rigor": 3, "completeness": 4,
                            "pedagogy": 3, "impact": 3},
        }
        resp = client.post("/api/v1/articles", json=create_body)
        article_id = resp.json()["id"]
        # Score should already be populated from creation
        assert resp.json()["score"] is not None

        # Manually null out the score to simulate old article
        s = get_session(db_engine)
        a = s.get(Article, article_id)
        a.score = None
        s.commit()
        s.close()

        # Fetch should backfill
        article = client.get(f"/api/v1/articles/{article_id}").json()
        assert article["score"] is not None
        assert "originality" in article["score"]


class TestScoreNotCleared:
    """Regression tests: article.score must not be cleared when latest commit has no reviews."""

    def test_edit_without_self_review_preserves_score(self, client, seed_user):
        """Editing content without self_review should not set score to None."""
        create_body = {
            "authors": [seed_user],
            "content": "# V1",
            "format": "markdown",
            "self_review": {"originality": 4, "rigor": 3, "completeness": 4,
                            "pedagogy": 3, "impact": 3},
        }
        resp = client.post("/api/v1/articles", json=create_body)
        article_id = resp.json()["id"]
        original_score = resp.json()["score"]
        assert original_score is not None

        # Edit WITHOUT self_review
        edit_body = {"content": "# V2\n\nNew content."}
        resp2 = client.put(f"/api/v1/articles/{article_id}", json=edit_body)
        assert resp2.status_code == 200
        # Score should NOT be None — should fall back to latest commit with reviews
        assert resp2.json()["score"] is not None

    def test_backfill_walks_commits_for_score(self, client, seed_user, db_engine):
        """Backfill should find a score from older commit if latest has none."""
        from peerpedia_core.storage.db.engine import get_session
        from peerpedia_core.storage.db.models import Article

        # Create article with self-review (commit A, has score)
        create_body = {
            "authors": [seed_user],
            "content": "# V1",
            "format": "markdown",
            "self_review": {"originality": 4, "rigor": 3, "completeness": 4,
                            "pedagogy": 3, "impact": 3},
        }
        resp = client.post("/api/v1/articles", json=create_body)
        article_id = resp.json()["id"]

        # Edit without self-review (commit B, no reviews)
        edit_body = {"content": "# V2\n\nEdited."}
        client.put(f"/api/v1/articles/{article_id}", json=edit_body)

        # Manually null out the score to simulate backfill scenario
        s = get_session(db_engine)
        a = s.get(Article, article_id)
        a.score = None
        s.commit()
        s.close()

        # Fetch should backfill from commit A (older commit with reviews)
        article = client.get(f"/api/v1/articles/{article_id}").json()
        assert article["score"] is not None
        # Should find commit A's score (originality=4), not return None
        assert article["score"]["originality"] == 4.0


class TestPagination:
    def test_list_articles_paginated(self, client, db_engine):
        """GET /articles returns paginated response with page and size."""
        from peerpedia_core.storage.db.engine import get_session
        from peerpedia_core.storage.db.models import User, Article
        s = get_session(db_engine)
        u = User(username="user22", password_hash="", name="pagination_user", anonymous_name="anon_pag")
        s.add(u)
        s.commit()
        for i in range(5):
            s.add(Article(status="published", authors=[u.id]))
        s.commit()
        s.close()

        resp = client.get("/api/v1/articles?page=1&size=2")
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 1
        assert data["size"] == 2
        assert data["total"] >= 5
        assert len(data["articles"]) == 2

    def test_list_articles_default_pagination(self, client):
        """Default pagination when no params provided."""
        resp = client.get("/api/v1/articles")
        assert resp.status_code == 200
        data = resp.json()
        assert "page" in data
        assert "size" in data
        assert "total" in data


class TestDownloadEndpoints:
    """Tests for download endpoints (source and PDF)."""

    def _create_article_with_content(self, client, seed_user, content, fmt="markdown"):
        create_body = {
            "authors": [seed_user],
            "content": content,
            "format": fmt,
            "self_review": {"originality": 4, "rigor": 3, "completeness": 4,
                            "pedagogy": 3, "impact": 3},
        }
        resp = client.post("/api/v1/articles", json=create_body)
        assert resp.status_code == 201
        return resp.json()["id"]

    def test_download_source_markdown(self, client, seed_user):
        """Download source file for a markdown article."""
        aid = self._create_article_with_content(client, seed_user, "# Test\n\nContent.")
        resp = client.get(f"/api/v1/articles/{aid}/download/source")
        assert resp.status_code == 200
        assert "# Test" in resp.text
        assert "Content-Type" in resp.headers

    def test_download_source_typst(self, client, seed_user):
        """Download source file for a Typst article."""
        aid = self._create_article_with_content(
            client, seed_user, "= Introduction\nSome text.", fmt="typst",
        )
        resp = client.get(f"/api/v1/articles/{aid}/download/source")
        assert resp.status_code == 200
        assert "Introduction" in resp.text

    def test_download_source_not_found(self, client):
        """Download source for non-existent article returns 404."""
        resp = client.get("/api/v1/articles/nonexistent/download/source")
        assert resp.status_code == 404

    def test_download_pdf_markdown_returns_html(self, client, seed_user):
        """PDF download for markdown article returns compiled HTML."""
        aid = self._create_article_with_content(client, seed_user, "# Test\n\nContent.")
        resp = client.get(f"/api/v1/articles/{aid}/download/pdf")
        assert resp.status_code == 200
        # Markdown compiler produces HTML
        assert "<h1>" in resp.text or "Test" in resp.text

    def test_download_pdf_not_found(self, client):
        """PDF download for non-existent article returns 404."""
        resp = client.get("/api/v1/articles/nonexistent/download/pdf")
        assert resp.status_code == 404
