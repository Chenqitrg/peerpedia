"""Integration tests for pool and bookmark routes."""
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


class TestPool:
    def test_empty_pool(self, client, db_engine):
        # Create a user so we can pass user_id
        s = get_session(db_engine)
        u = User(name="pool_user", anonymous_name="anon_pool")
        s.add(u)
        s.commit()
        uid = u.id
        s.close()
        resp = client.get(f"/api/v1/pool?user_id={uid}")
        assert resp.status_code == 200
        assert resp.json()["articles"] == []

    def test_pool_with_articles(self, client, db_engine):
        s = get_session(db_engine)
        u = User(name="测试", anonymous_name="anon")
        s.add(u)
        s.commit()
        from datetime import datetime, timezone
        a = Article(status="sedimentation", authors=[u.id],
                    sink_start=datetime.now(timezone.utc),
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
    def test_bookmark_lifecycle(self, client, db_engine):
        s = get_session(db_engine)
        u = User(name="读者", anonymous_name="anon")
        author = User(name="作者", anonymous_name="anon_a")
        s.add_all([u, author])
        s.commit()
        a = Article(status="published", authors=[author.id])
        s.add(a)
        s.commit()
        uid, aid = u.id, a.id
        s.close()

        # bookmark
        resp = client.post(f"/api/v1/bookmarks?user_id={uid}&article_id={aid}")
        assert resp.status_code == 201
        assert resp.json()["bookmarked"] is True

        # list
        resp = client.get(f"/api/v1/bookmarks?user_id={uid}")
        assert resp.status_code == 200
        assert len(resp.json()["bookmarks"]) == 1

        # delete
        resp = client.delete(f"/api/v1/bookmarks/{aid}?user_id={uid}")
        assert resp.status_code == 200
        assert resp.json()["bookmarked"] is False

        # list empty
        resp = client.get(f"/api/v1/bookmarks?user_id={uid}")
        assert len(resp.json()["bookmarks"]) == 0
