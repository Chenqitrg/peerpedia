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
        reader = User(username="user12", password_hash="", name="读者", anonymous_name="a1")
        writer = User(username="user13", password_hash="", name="作者", anonymous_name="a2")
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
        u = User(username="user14", password_hash="", name="作者", anonymous_name="a")
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

    def test_search_with_category_filter(self, client, db_engine):
        s = get_session(db_engine)
        u = User(username="user15", password_hash="", name="测试", anonymous_name="a")
        s.add(u)
        s.commit()
        a1 = Article(status="published", authors=[u.id], title="Quantum Physics",
                      categories=["physics", "quantum"])
        a2 = Article(status="published", authors=[u.id], title="Cell Biology",
                      categories=["biology"])
        s.add_all([a1, a2])
        s.commit()
        s.close()

        resp = client.get("/api/v1/search?category=physics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["articles"][0]["id"] == a1.id

    def test_search_with_sort_newest(self, client, db_engine):
        s = get_session(db_engine)
        u = User(username="user16", password_hash="", name="排序", anonymous_name="a")
        s.add(u)
        s.commit()
        a1 = Article(status="published", authors=[u.id], title="Older Article")
        a2 = Article(status="published", authors=[u.id], title="Newer Article")
        s.add_all([a1, a2])
        s.commit()
        s.close()

        resp = client.get("/api/v1/search?sort=newest")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["articles"]) >= 2
        assert data["articles"][0]["id"] == a2.id


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
        u = User(username="user15", password_hash="", name="作者", anonymous_name="a")
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
        u = User(username="user16", password_hash="", name="作者", anonymous_name="a")
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
        author = User(username="user17", password_hash="", name="原文作者", anonymous_name="a1")
        forker = User(username="user18", password_hash="", name="派生者", anonymous_name="a2")
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
        author = User(username="user19", password_hash="", name="原文作者", anonymous_name="a1")
        forker = User(username="user20", password_hash="", name="派生者", anonymous_name="a2")
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

    def test_accept_merge_proposal(self, client, db_engine):
        s = get_session(db_engine)
        author = User(username="user21", password_hash="", name="作者", anonymous_name="a1")
        forker = User(username="user22", password_hash="", name="派生", anonymous_name="a2")
        s.add_all([author, forker])
        s.commit()
        original = Article(status="published", authors=[author.id])
        fork = Article(status="draft", authors=[forker.id], forked_from=original.id)
        s.add_all([original, fork])
        s.commit()
        s.close()

        r = client.post(
            f"/api/v1/articles/{original.id}/merge-proposals",
            json={"fork_article_id": fork.id, "proposer_id": forker.id},
        )
        pid = r.json()["id"]

        resp = client.post(f"/api/v1/articles/{original.id}/merge-proposals/{pid}/accept")
        assert resp.status_code == 200
        assert resp.json()["status"] == "accepted"

    def test_reject_merge_proposal(self, client, db_engine):
        s = get_session(db_engine)
        author = User(username="user23", password_hash="", name="作者", anonymous_name="a1")
        forker = User(username="user24", password_hash="", name="派生", anonymous_name="a2")
        s.add_all([author, forker])
        s.commit()
        original = Article(status="published", authors=[author.id])
        fork = Article(status="draft", authors=[forker.id], forked_from=original.id)
        s.add_all([original, fork])
        s.commit()
        s.close()

        r = client.post(
            f"/api/v1/articles/{original.id}/merge-proposals",
            json={"fork_article_id": fork.id, "proposer_id": forker.id},
        )
        pid = r.json()["id"]

        resp = client.post(f"/api/v1/articles/{original.id}/merge-proposals/{pid}/reject")
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

    def test_merge_nonexistent_article_returns_404(self, client, db_engine):
        s = get_session(db_engine)
        u = User(username="user25", password_hash="", name="测试", anonymous_name="a1")
        s.add(u)
        s.commit()
        s.close()

        resp = client.post(
            "/api/v1/articles/nonexistent-id/merge-proposals",
            json={"fork_article_id": "irrelevant", "proposer_id": u.id},
        )
        assert resp.status_code == 404

    def test_accept_nonexistent_proposal_returns_404(self, client, db_engine):
        s = get_session(db_engine)
        u = User(username="user26", password_hash="", name="测试", anonymous_name="a1")
        s.add(u)
        a = Article(status="published", authors=[u.id])
        s.add(a)
        s.commit()
        s.close()

        resp = client.post(f"/api/v1/articles/{a.id}/merge-proposals/nonexistent/accept")
        assert resp.status_code == 404

    def test_search_empty_q_with_category(self, client, db_engine):
        """Search with only category filter, no query text."""
        s = get_session(db_engine)
        u = User(username="user27", password_hash="", name="测试", anonymous_name="a")
        s.add(u)
        s.commit()
        a1 = Article(status="published", authors=[u.id], title="Article A",
                      categories=["math"])
        a2 = Article(status="published", authors=[u.id], title="Article B",
                      categories=["physics"])
        s.add_all([a1, a2])
        s.commit()
        s.close()

        resp = client.get("/api/v1/search?category=math")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["articles"][0]["id"] == a1.id

    def test_search_sort_by_score(self, client, db_engine):
        s = get_session(db_engine)
        u = User(username="user28", password_hash="", name="排序测试", anonymous_name="a")
        s.add(u)
        s.commit()
        low = Article(status="published", authors=[u.id], title="Low Score",
                       score={"originality": 1, "rigor": 1, "completeness": 1,
                              "pedagogy": 1, "impact": 1})
        high = Article(status="published", authors=[u.id], title="High Score",
                        score={"originality": 5, "rigor": 5, "completeness": 5,
                               "pedagogy": 5, "impact": 5})
        s.add_all([low, high])
        s.commit()
        s.close()

        resp = client.get("/api/v1/search?sort=score")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["articles"]) >= 2
        # Highest score first
        assert data["articles"][0]["id"] == high.id

    def test_search_pagination_page_and_size(self, client, db_engine):
        """Pagination: page and size params control which results are returned."""
        s = get_session(db_engine)
        u = User(username="user29", password_hash="", name="分页测试", anonymous_name="a")
        s.add(u)
        s.commit()
        # Create 5 articles with distinct titles for pagination testing
        articles = []
        for i in range(5):
            a = Article(status="published", authors=[u.id],
                         title=f"Page Article {i+1}")
            articles.append(a)
        s.add_all(articles)
        s.commit()
        # Collect IDs in creation order (oldest first since no created_at override)
        ids = [a.id for a in articles]
        s.close()

        # Page 1, size 2 → returns first 2 articles, total=5
        resp = client.get("/api/v1/search?page=1&size=2")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        assert len(data["articles"]) == 2
        assert data["page"] == 1
        assert data["size"] == 2

        # Page 2, size 2 → returns next 2, different from page 1
        resp = client.get("/api/v1/search?page=2&size=2")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["articles"]) == 2
        page1_ids = {a["id"] for a in client.get("/api/v1/search?page=1&size=2").json()["articles"]}
        page2_ids = {a["id"] for a in data["articles"]}
        assert page1_ids != page2_ids, "Page 1 and Page 2 should return different results"

        # Page 3, size 2 → returns last article (total=5, so page 3 has 1 item)
        resp = client.get("/api/v1/search?page=3&size=2")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["articles"]) == 1

        # Default size (no size param → defaults to 20)
        resp = client.get("/api/v1/search")
        assert resp.status_code == 200
        data = resp.json()
        assert data["size"] == 20
