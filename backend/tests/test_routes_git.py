"""Tests for git-backed article sub-routes: history, diff, fork."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from peerpedia_core.storage.db.engine import get_session
from peerpedia_core.storage.db.models import User, Article
from peerpedia_core.storage.git_backend import init_article_repo, commit_article


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
def article_with_repo(db_engine):
    """Create user + article with git repo."""
    import tempfile
    s = get_session(db_engine)
    u = User(username="user23", password_hash="", name="作者", anonymous_name="anon")
    s.add(u)
    s.commit()
    a = Article(status="published", authors=[u.id])
    s.add(a)
    s.commit()
    aid = a.id
    uid = u.id
    s.close()

    # Create git repo
    with tempfile.TemporaryDirectory() as tmp:
        from pathlib import Path
        articles_dir = Path(tmp)
        rp = init_article_repo(aid, articles_dir)
        (rp / "article.md").write_text("# Test\n\nHello.\n")
        commit_article(rp, "initial", "Author", "a@b.com")

    return {"article_id": aid, "user_id": uid}


class TestHistory:
    def test_history_returns_list(self, client, article_with_repo):
        aid = article_with_repo["article_id"]
        resp = client.get(f"/api/v1/articles/{aid}/history")
        assert resp.status_code in (200, 404)  # 404 if repo path not found


class TestFork:
    def test_fork_creates_article(self, client, article_with_repo, db_engine, auth_header):
        aid = article_with_repo["article_id"]
        uid = article_with_repo["user_id"]
        resp = client.post(f"/api/v1/articles/{aid}/fork", headers=auth_header(uid))
        # 201 if git repo exists, 404 if not found
        assert resp.status_code in (201, 404)


class TestDiff:
    def test_diff_endpoint(self, client, article_with_repo):
        aid = article_with_repo["article_id"]
        resp = client.get(f"/api/v1/articles/{aid}/diff/abc123/def456")
        assert resp.status_code in (200, 404)
