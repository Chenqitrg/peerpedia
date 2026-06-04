"""Integration tests for review API routes."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from peerpedia_core.storage.db.engine import get_session
from peerpedia_core.storage.db.models import User, Article, Review


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
def seeded(db_engine):
    """Create a user, article with an existing review."""
    s = get_session(db_engine)
    author = User(name="作者", anonymous_name="anon_author", affiliation="PKU")
    reviewer = User(name="评审人", anonymous_name="星云观察者", affiliation="THU")
    s.add_all([author, reviewer])
    s.commit()

    article = Article(status="sedimentation", authors=[author.id])
    s.add(article)
    s.commit()

    s.close()
    return {"author_id": author.id, "reviewer_id": reviewer.id, "article_id": article.id}


class TestReviewSubmit:
    def test_create_review(self, client, seeded):
        body = {
            "article_id": seeded["article_id"],
            "commit_hash": "abc123",
            "reviewer_id": seeded["reviewer_id"],
            "scope": "pool",
            "scores": {"originality": 4, "rigor": 3, "completeness": 4, "pedagogy": 3, "impact": 3},
        }
        resp = client.post(f"/api/v1/articles/{seeded['article_id']}/reviews", json=body)
        assert resp.status_code == 201
        data = resp.json()
        assert data["reviewer_id"] == seeded["reviewer_id"]
        assert data["scope"] == "pool"

    def test_update_existing_review(self, client, seeded):
        body = {
            "article_id": seeded["article_id"],
            "commit_hash": "abc123",
            "reviewer_id": seeded["reviewer_id"],
            "scope": "pool",
            "scores": {"originality": 2, "rigor": 2, "completeness": 2, "pedagogy": 2, "impact": 2},
        }
        # first submit
        client.post(f"/api/v1/articles/{seeded['article_id']}/reviews", json=body)
        # update scores
        body["scores"]["originality"] = 5
        resp = client.post(f"/api/v1/articles/{seeded['article_id']}/reviews", json=body)
        assert resp.status_code == 201
        assert resp.json()["scores"]["originality"] == 5

    def test_review_on_nonexistent_article(self, client):
        body = {
            "article_id": "nonexistent", "commit_hash": "h", "reviewer_id": "u1",
            "scope": "pool",
            "scores": {"originality": 1, "rigor": 1, "completeness": 1, "pedagogy": 1, "impact": 1},
        }
        resp = client.post("/api/v1/articles/nonexistent/reviews", json=body)
        assert resp.status_code == 404


class TestReviewList:
    def test_list_reviews(self, client, seeded):
        # submit a review first
        body = {
            "article_id": seeded["article_id"], "commit_hash": "h", "reviewer_id": seeded["reviewer_id"],
            "scope": "pool",
            "scores": {"originality": 4, "rigor": 3, "completeness": 4, "pedagogy": 3, "impact": 3},
        }
        client.post(f"/api/v1/articles/{seeded['article_id']}/reviews", json=body)

        resp = client.get(f"/api/v1/articles/{seeded['article_id']}/reviews")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["reviewer_name"] == "星云观察者"  # pool → anonymous name


class TestThreadMessage:
    def test_post_message(self, client, seeded):
        # first create a review
        body = {
            "article_id": seeded["article_id"], "commit_hash": "h", "reviewer_id": seeded["reviewer_id"],
            "scope": "pool",
            "scores": {"originality": 3, "rigor": 3, "completeness": 3, "pedagogy": 3, "impact": 3},
        }
        r = client.post(f"/api/v1/articles/{seeded['article_id']}/reviews", json=body).json()

        resp = client.post(
            f"/api/v1/articles/{seeded['article_id']}/reviews/{r['id']}/messages?author_id={seeded['author_id']}",
            json={"content": "谢谢指出，已修改。"},
        )
        assert resp.status_code == 201
        assert resp.json()["status"] == "ok"
