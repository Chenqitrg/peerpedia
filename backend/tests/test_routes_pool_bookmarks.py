"""Integration tests for pool and bookmark routes."""
import pytest
from fastapi.testclient import TestClient
from peerpedia_core.storage.db.engine import get_session
from peerpedia_core.storage.db.models import Article, User, ArticleAuthor


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
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


class TestPool:
    def test_empty_pool(self, client, db_engine):
        # Create a user so we can pass user_id
        s = get_session(db_engine)
        u = User(username="user8", password_hash="", name="pool_user", anonymous_name="anon_pool")
        s.add(u)
        s.commit()
        uid = u.id
        s.close()
        resp = client.get(f"/api/v1/pool?user_id={uid}")
        assert resp.status_code == 200
        assert resp.json()["articles"] == []

    def test_pool_with_articles(self, client, db_engine):
        s = get_session(db_engine)
        u = User(username="user9", password_hash="", name="测试", anonymous_name="anon")
        s.add(u)
        s.commit()
        from datetime import datetime, timezone
        a = Article(status="sedimentation", sink_start=datetime.now(timezone.utc),
                    sink_duration_days=7)
        s.add(a)
        s.commit()
        uid = u.id
        s.close()

        resp = client.get(f"/api/v1/pool?user_id={uid}")
        assert resp.status_code == 200
        data = resp.json()
        # Author is in their own follow circle (self)
        assert len(data["articles"]) == 1
        assert data["articles"][0]["days_remaining"] >= 0


class TestBookmarks:
    def test_bookmark_lifecycle(self, client, db_engine, auth_header):
        s = get_session(db_engine)
        u = User(username="user10", password_hash="", name="读者", anonymous_name="anon")
        author = User(username="user11", password_hash="", name="作者", anonymous_name="anon_a")
        s.add_all([u, author])
        s.commit()
        a = Article(status="published")
        s.add(a)
        s.commit()
        uid, aid = u.id, a.id
        s.close()

        headers = auth_header(uid)

        # bookmark
        resp = client.post(f"/api/v1/bookmarks?article_id={aid}", headers=headers)
        assert resp.status_code == 201
        assert resp.json()["bookmarked"] is True

        # list
        resp = client.get("/api/v1/bookmarks", headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()["bookmarks"]) == 1

        # delete
        resp = client.delete(f"/api/v1/bookmarks/{aid}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["bookmarked"] is False

    def test_bookmark_nonexistent_article_returns_404(self, client, db_engine, auth_header):
        s = get_session(db_engine)
        u = User(username="bm_user", password_hash="", name="收藏者", anonymous_name="a")
        s.add(u)
        s.commit()
        s.close()

        headers = auth_header(u.id)
        resp = client.post("/api/v1/bookmarks?article_id=nonexistent-id", headers=headers)
        assert resp.status_code == 404

        # list empty
        resp = client.get("/api/v1/bookmarks", headers=headers)
        assert len(resp.json()["bookmarks"]) == 0
