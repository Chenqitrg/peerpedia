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
    author = User(username="user1", password_hash="", name="作者", anonymous_name="anon_author", affiliation="PKU")
    reviewer = User(username="user2", password_hash="", name="评审人", anonymous_name="星云观察者", affiliation="THU")
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

    def test_review_populates_article_score(self, client, db_engine):
        """After submitting a review, the article's score should be computed."""
        # Create a user and article via API (creates git repo + self-review)
        from peerpedia_core.storage.db.engine import get_session
        s = get_session(db_engine)
        from peerpedia_core.storage.db.models import User
        u = User(username="user3", password_hash="", name="score_tester", anonymous_name="anon_score", affiliation="PKU")
        s.add(u)
        s.commit()
        uid = u.id
        s.close()

        create_body = {
            "authors": [uid],
            "content": "# Test\n\nContent for scoring.",
            "format": "markdown",
            "self_review": {"originality": 3, "rigor": 3, "completeness": 3,
                            "pedagogy": 3, "impact": 3},
        }
        resp = client.post("/api/v1/articles", json=create_body)
        assert resp.status_code == 201
        article_id = resp.json()["id"]
        # The article should already have a score from the self-review
        article = client.get(f"/api/v1/articles/{article_id}").json()
        assert article["score"] is not None
        assert "originality" in article["score"]

    def test_different_commits_get_independent_reviews(self, client, db_engine):
        """Same reviewer can submit reviews for different commits."""
        from peerpedia_core.storage.db.engine import get_session
        s = get_session(db_engine)
        from peerpedia_core.storage.db.models import User
        u = User(username="user4", password_hash="", name="multi_commit_rv", anonymous_name="anon_mc", affiliation="PKU")
        s.add(u)
        s.commit()
        uid = u.id
        s.close()

        # Create article
        create_body = {
            "authors": [uid],
            "content": "# V1",
            "format": "markdown",
            "self_review": {"originality": 3, "rigor": 3, "completeness": 3,
                            "pedagogy": 3, "impact": 3},
        }
        resp = client.post("/api/v1/articles", json=create_body)
        article_id = resp.json()["id"]

        # Get the commit hash from history
        history = client.get(f"/api/v1/articles/{article_id}/history").json()
        commit_1 = history["commits"][0]["hash"]

        # Submit a second review for the same commit (different reviewer approach)
        # We need a second user as reviewer
        s2 = get_session(db_engine)
        rv = User(username="user5", password_hash="", name="reviewer_2", anonymous_name="anon_rv2", affiliation="THU")
        s2.add(rv)
        s2.commit()
        rv_id = rv.id
        s2.close()

        # Submit community review for commit_1
        body = {
            "article_id": article_id,
            "commit_hash": commit_1,
            "reviewer_id": rv_id,
            "scope": "pool",
            "scores": {"originality": 5, "rigor": 5, "completeness": 5,
                       "pedagogy": 5, "impact": 5},
        }
        r1 = client.post(f"/api/v1/articles/{article_id}/reviews", json=body)
        assert r1.status_code == 201

        # Now edit the article to create a new commit
        edit_body = {
            "content": "# V2\n\nUpdated.",
            "self_review": {"originality": 4, "rigor": 4, "completeness": 4,
                            "pedagogy": 4, "impact": 4},
        }
        client.put(f"/api/v1/articles/{article_id}", json=edit_body)

        # Get new commit hash
        history2 = client.get(f"/api/v1/articles/{article_id}/history").json()
        commit_2 = history2["commits"][0]["hash"]
        assert commit_2 != commit_1

        # Same reviewer submits review for new commit — should succeed
        body2 = {
            "article_id": article_id,
            "commit_hash": commit_2,
            "reviewer_id": rv_id,
            "scope": "pool",
            "scores": {"originality": 2, "rigor": 2, "completeness": 2,
                       "pedagogy": 2, "impact": 2},
        }
        r2 = client.post(f"/api/v1/articles/{article_id}/reviews", json=body2)
        assert r2.status_code == 201
        assert r2.json()["commit_hash"] == commit_2
        # The two reviews should have different IDs (different reviews)
        assert r1.json()["id"] != r2.json()["id"]

    def test_review_preserves_score_when_latest_commit_has_no_reviews(self, client, db_engine):
        """Submitting review should not clear score when latest commit lacks reviews."""
        from peerpedia_core.storage.db.engine import get_session
        s = get_session(db_engine)
        from peerpedia_core.storage.db.models import User
        u = User(username="user6", password_hash="", name="edge_author", anonymous_name="anon_edge", affiliation="PKU")
        rv = User(username="user7", password_hash="", name="edge_reviewer", anonymous_name="anon_edge_rv", affiliation="THU")
        s.add_all([u, rv])
        s.commit()
        uid = u.id
        rv_id = rv.id
        s.close()

        # Create article (commit A, has self-review → has score)
        create_body = {
            "authors": [uid],
            "content": "# V1",
            "format": "markdown",
            "self_review": {"originality": 4, "rigor": 3, "completeness": 4,
                            "pedagogy": 3, "impact": 3},
        }
        resp = client.post("/api/v1/articles", json=create_body)
        article_id = resp.json()["id"]

        # Edit WITHOUT self-review (commit B, no reviews for latest commit)
        client.put(f"/api/v1/articles/{article_id}", json={"content": "# V2"})

        # Get commit B hash (latest, no reviews)
        history = client.get(f"/api/v1/articles/{article_id}/history").json()
        commit_b = history["commits"][0]["hash"]

        # Submit a review for commit B (latest commit, now gets a review)
        body = {
            "article_id": article_id,
            "commit_hash": commit_b,
            "reviewer_id": rv_id,
            "scope": "pool",
            "scores": {"originality": 5, "rigor": 4, "completeness": 5,
                       "pedagogy": 4, "impact": 4},
        }
        r = client.post(f"/api/v1/articles/{article_id}/reviews", json=body)
        assert r.status_code == 201

        # Article score should now be computed, not None
        article = client.get(f"/api/v1/articles/{article_id}").json()
        assert article["score"] is not None
        # Latest commit now has reviews, so should have a valid score
        assert article["score"]["originality"] > 0


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
