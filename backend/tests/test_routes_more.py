"""Integration tests for feed, search, compile, citations, merge routes."""
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


class TestFeed:
    def test_empty_feed(self, client):
        resp = client.get("/api/v1/feed?user_id=nonexistent")
        assert resp.status_code == 200
        assert resp.json()["articles"] == []

    def test_feed_from_followed(self, client, db_engine):
        s = get_session(db_engine)
        reader = User(name="读者", anonymous_name="a1")
        writer = User(name="作者", anonymous_name="a2")
        s.add_all([reader, writer])
        s.commit()

        from peerpedia_core.storage.db.models import Follow
        s.add(Follow(follower_id=reader.id, followed_id=writer.id))

        a = Article(status="published", authors=[writer.id])
        s.add(a)
        s.commit()
        s.close()

        resp = client.get(f"/api/v1/feed?user_id={reader.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["articles"]) == 1
        assert data["articles"][0]["id"] == a.id


class TestSearch:
    def test_search_by_keyword(self, client, db_engine):
        s = get_session(db_engine)
        u = User(name="作者", anonymous_name="a")
        s.add(u)
        s.commit()
        # search currently searches on title/abstract — placeholder until full-text index
        a = Article(status="published", authors=[u.id])
        s.add(a)
        s.commit()
        s.close()

        resp = client.get("/api/v1/search?q=test")
        assert resp.status_code == 200
        assert "articles" in resp.json()


class TestCompile:
    def test_compile_preview_markdown(self, client):
        resp = client.post("/api/v1/compile-preview", json={
            "content": "# Hello\n\nThis is a test.",
            "format": "markdown",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["format"] == "html"
        assert "<h1>" in data["output"]

    def test_compile_unsupported_format(self, client):
        resp = client.post("/api/v1/compile-preview", json={
            "content": "test", "format": "unknown",
        })
        assert resp.status_code == 400

    def test_compile_typst_preview(self, client):
        """Typst compilation returns SVG on success, or graceful error if
        typst CLI is not installed."""
        import shutil
        if shutil.which("typst") is None:
            # typst not installed — expect a 500 with install message
            resp = client.post("/api/v1/compile-preview", json={
                "content": "= Hello\nThis is a test.",
                "format": "typst",
            })
            assert resp.status_code == 500
            assert "typst CLI not found" in resp.json()["detail"].lower() or \
                   "not found" in resp.json()["detail"].lower()
        else:
            resp = client.post("/api/v1/compile-preview", json={
                "content": "= Hello\nThis is a *Typst* test.",
                "format": "typst",
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["format"] == "svg"
            assert "<svg" in data["output"]


class TestCitations:
    def test_empty_citations(self, client, db_engine):
        s = get_session(db_engine)
        u = User(name="作者", anonymous_name="a")
        s.add(u)
        s.commit()
        a = Article(status="published", authors=[u.id])
        s.add(a)
        s.commit()
        s.close()

        resp = client.get(f"/api/v1/articles/{a.id}/citations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cites"] == []
        assert data["cited_by"] == []

    def test_record_click(self, client, db_engine):
        s = get_session(db_engine)
        u = User(name="作者", anonymous_name="a")
        s.add(u)
        s.commit()
        a1 = Article(status="published", authors=[u.id])
        a2 = Article(status="published", authors=[u.id])
        s.add_all([a1, a2])
        s.commit()
        s.close()

        resp = client.post("/api/v1/citations/click", json={
            "from_article_id": a1.id, "to_article_id": a2.id,
        })
        assert resp.status_code == 201


class TestMerge:
    def test_create_merge_proposal(self, client, db_engine):
        s = get_session(db_engine)
        author = User(name="原文作者", anonymous_name="a1")
        forker = User(name="派生者", anonymous_name="a2")
        s.add_all([author, forker])
        s.commit()
        original = Article(status="published", authors=[author.id])
        fork = Article(status="draft", authors=[forker.id], forked_from=original.id)
        s.add_all([original, fork])
        s.commit()
        s.close()

        resp = client.post(
            f"/api/v1/articles/{original.id}/merge-proposals",
            json={"fork_article_id": fork.id, "proposer_id": forker.id},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "open"

    def test_list_merge_proposals(self, client, db_engine):
        s = get_session(db_engine)
        author = User(name="原文作者", anonymous_name="a1")
        forker = User(name="派生者", anonymous_name="a2")
        s.add_all([author, forker])
        s.commit()
        original = Article(status="published", authors=[author.id])
        fork = Article(status="draft", authors=[forker.id], forked_from=original.id)
        s.add_all([original, fork])
        s.commit()
        s.close()

        client.post(
            f"/api/v1/articles/{original.id}/merge-proposals",
            json={"fork_article_id": fork.id, "proposer_id": forker.id},
        )
        resp = client.get(f"/api/v1/articles/{original.id}/merge-proposals")
        assert resp.status_code == 200
        assert len(resp.json()["proposals"]) == 1
