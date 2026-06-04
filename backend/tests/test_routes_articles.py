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
    u = User(name="测试用户", anonymous_name="anon_test", affiliation="测试大学")
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
        assert data["authors"] == [seed_user]
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
