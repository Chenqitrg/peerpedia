"""Locked specification tests — define product behavior.

SPECIFICATION STATUS = LOCKED
Tests define product behavior. Implementation must satisfy these specs.
Only modify if requirements change, spec is contradictory, or user approves.
"""
import pytest
from fastapi.testclient import TestClient
from peerpedia_core.storage.db.engine import get_session
from peerpedia_core.storage.db.models import Article, ArticleAuthor, User
from peerpedia_core.storage.git_backend import (
    DEFAULT_ARTICLES_DIR,
    commit_article,
    init_article_repo,
)


@pytest.fixture
def client(db_engine):
    """TestClient with DB override."""
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


def _create_article_with_user(db_engine, username="spec_user"):
    """Create a user + article, return (article_id, user_id, auth_token)."""
    s = get_session(db_engine)
    u = User(username=username, password_hash="", name="Spec Tester")
    s.add(u)
    s.commit()

    a = Article(status="draft")
    s.add(a)
    s.flush()
    s.add(ArticleAuthor(article_id=a.id, author_id=u.id, position=0))
    s.commit()

    aid, uid = a.id, u.id
    s.close()

    # Create git repo for the article
    rp = init_article_repo(aid, DEFAULT_ARTICLES_DIR)
    (rp / "article.md").write_text("# Spec\n\nContent")
    commit_article(rp, "Initial", username, f"{username}@test.com")

    return aid, uid


def _get_auth_headers(db_engine, user_id):
    """Get auth headers for a user (bypass auth with direct DB user)."""
    from peerpedia_api import deps as api_deps
    s = get_session(db_engine)
    user = s.query(User).filter(User.id == user_id).first()
    s.close()
    assert user is not None, f"User {user_id} not found in DB"

    # Create a simple override that returns this user
    from peerpedia_api.main import app
    return user


# ── Spec 3: Fork validates user identity ──────────────────────────────

class TestSpec3ForkUserValidation:
    """User story: fork gives clear error when user not synced to server."""

    def test_S3_2_fork_works_with_server_user(self, client, db_engine):
        """Given: article exists and user is in server DB
        When: POST /api/v1/articles/{id}/fork
        Then: returns 201 with id and forked_from fields"""
        aid, uid = _create_article_with_user(db_engine, "fork_user_1")
        user = _get_auth_headers(db_engine, uid)

        # Override require_user to return our test user
        from peerpedia_api import deps as api_deps
        from peerpedia_api.main import app

        app.dependency_overrides[api_deps.require_user] = lambda: user

        resp = client.post(f"/api/v1/articles/{aid}/fork")
        assert resp.status_code == 201, f"Fork failed: {resp.text}"
        data = resp.json()
        assert "id" in data
        assert data["forked_from"] == aid
        assert data["status"] == "draft"

    def test_S3_2_fork_returns_404_for_nonexistent_article(self, client, db_engine):
        """Given: article does not exist
        When: POST /api/v1/articles/nonexistent-id/fork
        Then: returns 404"""
        _, uid = _create_article_with_user(db_engine, "fork_user_2")
        user = _get_auth_headers(db_engine, uid)

        from peerpedia_api import deps as api_deps
        from peerpedia_api.main import app

        app.dependency_overrides[api_deps.require_user] = lambda: user

        resp = client.post("/api/v1/articles/nonexistent-id/fork")
        assert resp.status_code == 404
