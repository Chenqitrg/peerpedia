# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Integration tests for feed, search, compile, citations, merge routes."""

import pytest
from fastapi.testclient import TestClient
from peerpedia_core.storage.db.engine import get_session
from peerpedia_core.storage.db.models import Article, ArticleAuthor, User


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


class TestFeed:
    def test_empty_feed(self, client):
        resp = client.get("/api/v1/feed?user_id=nonexistent")
        assert resp.status_code == 200
        assert resp.json()["articles"] == []

    def test_feed_unauthenticated_returns_all(self, client, db_engine):
        """Without auth header, the feed returns all visible articles."""
        s = get_session(db_engine)
        u = User(username="feed_unauth_au", password_hash="", name="A", anonymous_name="a")
        s.add(u)
        a = Article(status="published", title="Public Article")
        s.add(a)
        s.commit()
        s.close()
        resp = client.get("/api/v1/feed")
        assert resp.status_code == 200
        assert len(resp.json()["articles"]) >= 1

    def test_feed_cache_requires_auth(self, client):
        """GET /feed/cache requires authentication."""
        resp = client.get("/api/v1/feed/cache")
        assert resp.status_code in (401, 403)

    def test_feed_cache_empty_following(self, client, db_engine):
        """Feed cache for user with no following returns empty."""
        from peerpedia_api.deps import create_token

        s = get_session(db_engine)
        u = User(username="fc_empty", password_hash="", name="FC", anonymous_name="a")
        s.add(u)
        s.commit()
        s.close()
        token = create_token(u.id)
        resp = client.get("/api/v1/feed/cache", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["following_ids"] == []
        assert data["articles"] == []

    def test_feed_cache_with_following(self, client, db_engine):
        """Feed cache for user with following returns article metadata."""
        from peerpedia_api.deps import create_token
        from peerpedia_core.storage.db.models import ArticleAuthor, Follow

        s = get_session(db_engine)
        reader = User(username="fc_reader", password_hash="", name="R", anonymous_name="a1")
        writer = User(username="fc_writer", password_hash="", name="W", anonymous_name="a2")
        s.add_all([reader, writer])
        s.commit()
        s.add(Follow(follower_id=reader.id, followed_id=writer.id))
        a = Article(status="published", title="Cached Article")
        s.add(a)
        s.flush()
        s.add(ArticleAuthor(article_id=a.id, author_id=writer.id, position=0))
        s.commit()
        s.close()
        token = create_token(reader.id)
        resp = client.get("/api/v1/feed/cache", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert writer.id in data["following_ids"]
        assert len(data["articles"]) >= 1

    def test_feed_from_followed(self, client, db_engine):
        s = get_session(db_engine)
        reader = User(username="user12", password_hash="", name="读者", anonymous_name="a1")
        writer = User(username="user13", password_hash="", name="作者", anonymous_name="a2")
        s.add_all([reader, writer])
        s.commit()

        from peerpedia_core.storage.db.models import Follow

        s.add(Follow(follower_id=reader.id, followed_id=writer.id))

        a = Article(status="published")
        s.add(a)
        s.commit()
        s.close()

        resp = client.get(f"/api/v1/feed?user_id={reader.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["articles"]) == 1
        assert data["articles"][0]["id"] == a.id

    def test_feed_shows_followed_author_article(self, client, db_engine, auth_header):
        """REGRESSION: Bug 3 — authenticated follower sees followed author's articles.

        If the viewer follows an author who has articles, the feed must include
        those articles.  Verifies the list_articles(follower_id=...) join works
        correctly through Follow + ArticleAuthor.
        """
        from peerpedia_core.storage.db.engine import get_session
        from peerpedia_core.storage.db.models import Article, ArticleAuthor, Follow, User

        s = get_session(db_engine)
        # Author who writes
        author = User(username="feed_regr_auth", password_hash="", name="AuthorX", anonymous_name="ax")
        # Viewer who follows
        viewer = User(username="feed_regr_view", password_hash="", name="ViewerX", anonymous_name="vx")
        s.add_all([author, viewer])
        s.commit()

        # Viewer follows author
        s.add(Follow(follower_id=viewer.id, followed_id=author.id))

        # Author has an article (with ArticleAuthor row)
        a = Article(title="Feed Article", status="published")
        s.add(a)
        s.flush()
        s.add(ArticleAuthor(article_id=a.id, author_id=author.id, position=0))
        s.commit()
        article_id = a.id
        s.close()

        # Authenticate as viewer and fetch feed
        resp = client.get("/api/v1/feed", headers=auth_header(viewer.id))
        assert resp.status_code == 200
        data = resp.json()
        feed_ids = [art["id"] for art in data["articles"]]
        assert article_id in feed_ids, f"Feed should include article {article_id} from followed author {author.id}"


class TestSearch:
    def test_search_by_keyword(self, client, db_engine):
        s = get_session(db_engine)
        u = User(username="user14", password_hash="", name="作者", anonymous_name="a")
        s.add(u)
        s.commit()
        # search currently searches on title/abstract — placeholder until full-text index
        a = Article(status="published")
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
        a1 = Article(status="published", title="Quantum Physics", categories=["physics", "quantum"])
        a2 = Article(status="published", title="Cell Biology", categories=["biology"])
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
        a1 = Article(status="published", title="Older Article")
        a2 = Article(status="published", title="Newer Article")
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
        resp = client.post(
            "/api/v1/compile-preview",
            json={
                "content": "# Hello\n\nThis is a test.",
                "format": "markdown",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["format"] == "html"
        assert "<h1>" in data["output"]

    def test_compile_unsupported_format(self, client):
        resp = client.post(
            "/api/v1/compile-preview",
            json={
                "content": "test",
                "format": "unknown",
            },
        )
        assert resp.status_code == 400

    def test_compile_typst_preview(self, client):
        """Typst compilation returns SVG on success, or graceful error if
        typst CLI is not installed."""
        import shutil

        if shutil.which("typst") is None:
            # typst not installed — expect a 500 with install message
            resp = client.post(
                "/api/v1/compile-preview",
                json={
                    "content": "= Hello\nThis is a test.",
                    "format": "typst",
                },
            )
            assert resp.status_code == 500
            assert "typst CLI not found" in resp.json()["detail"].lower() or "not found" in resp.json()["detail"].lower()
        else:
            resp = client.post(
                "/api/v1/compile-preview",
                json={
                    "content": "= Hello\nThis is a *Typst* test.",
                    "format": "typst",
                },
            )
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
        a = Article(status="published")
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
        a1 = Article(status="published")
        a2 = Article(status="published")
        s.add_all([a1, a2])
        s.commit()
        s.close()

        resp = client.post(
            "/api/v1/citations/click",
            json={
                "from_article_id": a1.id,
                "to_article_id": a2.id,
            },
        )
        assert resp.status_code == 201

    def test_citations_nonexistent_article_returns_404(self, client):
        """Requesting citations for non-existent article returns 404."""
        resp = client.get("/api/v1/articles/no-such-article/citations")
        assert resp.status_code == 404

    def test_citations_with_actual_edges(self, client, db_engine):
        """GET citations for an article that has citation edges."""
        from peerpedia_core.storage.db.crud_citation import create_or_update_citation

        s = get_session(db_engine)
        u = User(username="cit_edge_au", password_hash="", name="A", anonymous_name="a")
        s.add(u)
        s.commit()
        a1 = Article(status="published", title="Article One")
        a2 = Article(status="published", title="Article Two")
        a3 = Article(status="published", title="Article Three")
        s.add_all([a1, a2, a3])
        s.commit()
        # Create citation edges
        create_or_update_citation(s, a1.id, a2.id, forward=0.5, backward=0.2)
        create_or_update_citation(s, a3.id, a1.id, forward=0.3, backward=0.1)
        s.close()

        resp = client.get(f"/api/v1/articles/{a1.id}/citations")
        assert resp.status_code == 200
        data = resp.json()
        # a1 cites a2 (forward edge)
        assert len(data["cites"]) >= 1
        # a1 is cited by a3 (incoming edge)
        assert len(data["cited_by"]) >= 1
        # Check edge structure
        edge = data["cites"][0]
        assert "article_id" in edge
        assert "title" in edge
        assert "forward_prob" in edge
        assert "backward_prob" in edge


class TestMerge:
    @staticmethod
    def _auth(user):
        """Create an auth header for the given user."""
        from peerpedia_api.deps import create_token

        return {"Authorization": f"Bearer {create_token(user.id)}"}

    def test_create_merge_proposal(self, client, db_engine):
        s = get_session(db_engine)
        author = User(username="user17", password_hash="", name="原文作者", anonymous_name="a1")
        forker = User(username="user18", password_hash="", name="派生者", anonymous_name="a2")
        s.add_all([author, forker])
        s.commit()
        original = Article(status="published")
        fork = Article(status="draft", forked_from=original.id)
        s.add_all([original, fork])
        s.commit()
        s.close()

        resp = client.post(
            f"/api/v1/articles/{original.id}/merge-proposals", json={"fork_article_id": fork.id}, headers=self._auth(forker)
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "open"
        # proposer_id should come from JWT, not request body
        assert data["proposer_id"] == forker.id

    def test_merge_create_requires_auth(self, client, db_engine):
        """Unauthenticated merge creation returns 401."""
        s = get_session(db_engine)
        u = User(username="merge_noauth", password_hash="", name="X", anonymous_name="a")
        a = Article(status="published")
        s.add_all([u, a])
        s.commit()
        s.close()
        resp = client.post(f"/api/v1/articles/{a.id}/merge-proposals", json={"fork_article_id": "irrelevant"})
        assert resp.status_code == 401

    def test_merge_create_uses_jwt_identity(self, client, db_engine):
        """proposer_id is derived from JWT, not request body."""
        s = get_session(db_engine)
        author = User(username="user17b", password_hash="", name="A", anonymous_name="a1")
        forker = User(username="user18b", password_hash="", name="F", anonymous_name="a2")
        victim = User(username="user19b", password_hash="", name="V", anonymous_name="a3")
        s.add_all([author, forker, victim])
        s.commit()
        original = Article(status="published")
        fork = Article(status="draft", forked_from=original.id)
        s.add_all([original, fork])
        s.commit()
        s.close()

        # Authenticate as forker, but try to set proposer_id to victim
        resp = client.post(
            f"/api/v1/articles/{original.id}/merge-proposals",
            json={"fork_article_id": fork.id, "proposer_id": victim.id},
            headers=self._auth(forker),
        )
        assert resp.status_code == 201
        # Should use forker's ID from JWT, ignore body's proposer_id
        assert resp.json()["proposer_id"] == forker.id

    def test_list_merge_proposals(self, client, db_engine):
        s = get_session(db_engine)
        author = User(username="user19", password_hash="", name="原文作者", anonymous_name="a1")
        forker = User(username="user20", password_hash="", name="派生者", anonymous_name="a2")
        s.add_all([author, forker])
        s.commit()
        original = Article(status="published")
        fork = Article(status="draft", forked_from=original.id)
        s.add_all([original, fork])
        s.commit()
        s.close()

        client.post(
            f"/api/v1/articles/{original.id}/merge-proposals", json={"fork_article_id": fork.id}, headers=self._auth(forker)
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
        original = Article(status="published")
        fork = Article(status="draft", forked_from=original.id)
        s.add_all([original, fork])
        s.flush()
        s.add(ArticleAuthor(article_id=original.id, author_id=author.id, position=0))
        s.commit()
        s.close()

        r = client.post(
            f"/api/v1/articles/{original.id}/merge-proposals", json={"fork_article_id": fork.id}, headers=self._auth(forker)
        )
        pid = r.json()["id"]

        resp = client.post(f"/api/v1/articles/{original.id}/merge-proposals/{pid}/accept", headers=self._auth(author))
        assert resp.status_code == 200
        assert resp.json()["status"] == "accepted"

    def test_merge_accept_requires_auth(self, client, db_engine):
        """Unauthenticated merge accept returns 401."""
        s = get_session(db_engine)
        author = User(username="user21x", password_hash="", name="A", anonymous_name="a1")
        forker = User(username="user22x", password_hash="", name="F", anonymous_name="a2")
        s.add_all([author, forker])
        s.commit()
        original = Article(status="published")
        fork = Article(status="draft", forked_from=original.id)
        s.add_all([original, fork])
        s.commit()
        s.close()
        r = client.post(
            f"/api/v1/articles/{original.id}/merge-proposals", json={"fork_article_id": fork.id}, headers=self._auth(forker)
        )
        pid = r.json()["id"]
        resp = client.post(f"/api/v1/articles/{original.id}/merge-proposals/{pid}/accept")
        assert resp.status_code == 401

    def test_reject_merge_proposal(self, client, db_engine):
        s = get_session(db_engine)
        author = User(username="user23", password_hash="", name="作者", anonymous_name="a1")
        forker = User(username="user24", password_hash="", name="派生", anonymous_name="a2")
        s.add_all([author, forker])
        s.commit()
        original = Article(status="published")
        fork = Article(status="draft", forked_from=original.id)
        s.add_all([original, fork])
        s.flush()
        s.add(ArticleAuthor(article_id=original.id, author_id=author.id, position=0))
        s.commit()
        s.close()

        r = client.post(
            f"/api/v1/articles/{original.id}/merge-proposals", json={"fork_article_id": fork.id}, headers=self._auth(forker)
        )
        pid = r.json()["id"]

        resp = client.post(f"/api/v1/articles/{original.id}/merge-proposals/{pid}/reject", headers=self._auth(author))
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

    def test_merge_reject_requires_auth(self, client, db_engine):
        """Unauthenticated merge reject returns 401."""
        s = get_session(db_engine)
        author = User(username="user23x", password_hash="", name="A", anonymous_name="a1")
        forker = User(username="user24x", password_hash="", name="F", anonymous_name="a2")
        s.add_all([author, forker])
        s.commit()
        original = Article(status="published")
        fork = Article(status="draft", forked_from=original.id)
        s.add_all([original, fork])
        s.commit()
        s.close()
        r = client.post(
            f"/api/v1/articles/{original.id}/merge-proposals", json={"fork_article_id": fork.id}, headers=self._auth(forker)
        )
        pid = r.json()["id"]
        resp = client.post(f"/api/v1/articles/{original.id}/merge-proposals/{pid}/reject")
        assert resp.status_code == 401

    def test_merge_nonexistent_article_returns_404(self, client, db_engine):
        s = get_session(db_engine)
        u = User(username="user25", password_hash="", name="测试", anonymous_name="a1")
        s.add(u)
        s.commit()
        s.close()

        resp = client.post(
            "/api/v1/articles/nonexistent-id/merge-proposals", json={"fork_article_id": "irrelevant"}, headers=self._auth(u)
        )
        assert resp.status_code == 404

    def test_accept_nonexistent_proposal_returns_404(self, client, db_engine):
        s = get_session(db_engine)
        u = User(username="user26", password_hash="", name="测试", anonymous_name="a1")
        s.add(u)
        a = Article(status="published")
        s.add(a)
        s.commit()
        s.close()

        resp = client.post(f"/api/v1/articles/{a.id}/merge-proposals/nonexistent/accept", headers=self._auth(u))
        assert resp.status_code == 404

    def test_accept_wrong_article_returns_400(self, client, db_engine):
        """Accepting a merge proposal targeting a different article returns 400."""
        s = get_session(db_engine)
        author = User(username="mp_wrong_au", password_hash="", name="A", anonymous_name="a1")
        forker = User(username="mp_wrong_fk", password_hash="", name="F", anonymous_name="a2")
        s.add_all([author, forker])
        s.commit()
        target = Article(status="published")
        fork = Article(status="draft", forked_from=target.id)
        other = Article(status="published")
        s.add_all([target, fork, other])
        s.commit()
        s.close()

        r = client.post(
            f"/api/v1/articles/{target.id}/merge-proposals", json={"fork_article_id": fork.id}, headers=self._auth(forker)
        )
        pid = r.json()["id"]
        resp = client.post(f"/api/v1/articles/{other.id}/merge-proposals/{pid}/accept", headers=self._auth(author))
        assert resp.status_code == 400

    def test_reject_wrong_article_returns_400(self, client, db_engine):
        """Rejecting a merge proposal for a different article returns 400."""
        s = get_session(db_engine)
        author = User(username="mp_rej_wr_au", password_hash="", name="A", anonymous_name="a1")
        forker = User(username="mp_rej_wr_fk", password_hash="", name="F", anonymous_name="a2")
        s.add_all([author, forker])
        s.commit()
        target = Article(status="published")
        fork = Article(status="draft", forked_from=target.id)
        other = Article(status="published")
        s.add_all([target, fork, other])
        s.commit()
        s.close()

        r = client.post(
            f"/api/v1/articles/{target.id}/merge-proposals", json={"fork_article_id": fork.id}, headers=self._auth(forker)
        )
        pid = r.json()["id"]
        resp = client.post(f"/api/v1/articles/{other.id}/merge-proposals/{pid}/reject", headers=self._auth(author))
        assert resp.status_code == 400

    def test_accept_already_resolved_proposal_returns_400(self, client, db_engine):
        """Accepting an already-accepted merge proposal returns 400."""
        s = get_session(db_engine)
        author = User(username="mp_res_au", password_hash="", name="A", anonymous_name="a1")
        forker = User(username="mp_res_fk", password_hash="", name="F", anonymous_name="a2")
        s.add_all([author, forker])
        s.commit()
        target = Article(status="published")
        fork = Article(status="draft", forked_from=target.id)
        s.add_all([target, fork])
        s.flush()
        s.add(ArticleAuthor(article_id=target.id, author_id=author.id, position=0))
        s.commit()
        s.close()

        r = client.post(
            f"/api/v1/articles/{target.id}/merge-proposals", json={"fork_article_id": fork.id}, headers=self._auth(forker)
        )
        pid = r.json()["id"]
        client.post(f"/api/v1/articles/{target.id}/merge-proposals/{pid}/accept", headers=self._auth(author))
        # Accept again — should return 400
        resp = client.post(f"/api/v1/articles/{target.id}/merge-proposals/{pid}/accept", headers=self._auth(author))
        assert resp.status_code == 400

    def test_reject_already_resolved_proposal_returns_400(self, client, db_engine):
        """Rejecting an already-accepted merge proposal returns 400."""
        s = get_session(db_engine)
        author = User(username="mp_rej2_au", password_hash="", name="A", anonymous_name="a1")
        forker = User(username="mp_rej2_fk", password_hash="", name="F", anonymous_name="a2")
        s.add_all([author, forker])
        s.commit()
        target = Article(status="published")
        fork = Article(status="draft", forked_from=target.id)
        s.add_all([target, fork])
        s.flush()
        s.add(ArticleAuthor(article_id=target.id, author_id=author.id, position=0))
        s.commit()
        s.close()

        r = client.post(
            f"/api/v1/articles/{target.id}/merge-proposals", json={"fork_article_id": fork.id}, headers=self._auth(forker)
        )
        pid = r.json()["id"]
        client.post(f"/api/v1/articles/{target.id}/merge-proposals/{pid}/accept", headers=self._auth(author))
        resp = client.post(f"/api/v1/articles/{target.id}/merge-proposals/{pid}/reject", headers=self._auth(author))
        assert resp.status_code == 400

    def test_merge_accept_non_author_forbidden(self, client, db_engine):
        """Non-authors cannot accept merge proposals; others get 403."""
        s = get_session(db_engine)
        author = User(username="mp_na_au", password_hash="", name="A", anonymous_name="a1")
        forker = User(username="mp_na_fk", password_hash="", name="F", anonymous_name="a2")
        outsider = User(username="mp_na_out", password_hash="", name="O", anonymous_name="a3")
        s.add_all([author, forker, outsider])
        s.commit()
        target = Article(status="published")
        fork = Article(status="draft", forked_from=target.id)
        s.add_all([target, fork])
        s.flush()
        s.add(ArticleAuthor(article_id=target.id, author_id=author.id, position=0))
        s.commit()
        s.close()

        r = client.post(
            f"/api/v1/articles/{target.id}/merge-proposals", json={"fork_article_id": fork.id}, headers=self._auth(forker)
        )
        pid = r.json()["id"]
        resp = client.post(f"/api/v1/articles/{target.id}/merge-proposals/{pid}/accept", headers=self._auth(outsider))
        assert resp.status_code == 403

    def test_merge_reject_non_author_forbidden(self, client, db_engine):
        """Non-authors cannot reject merge proposals; others get 403."""
        s = get_session(db_engine)
        author = User(username="mp_na2_au", password_hash="", name="A", anonymous_name="a1")
        forker = User(username="mp_na2_fk", password_hash="", name="F", anonymous_name="a2")
        outsider = User(username="mp_na2_out", password_hash="", name="O", anonymous_name="a3")
        s.add_all([author, forker, outsider])
        s.commit()
        target = Article(status="published")
        fork = Article(status="draft", forked_from=target.id)
        s.add_all([target, fork])
        s.flush()
        s.add(ArticleAuthor(article_id=target.id, author_id=author.id, position=0))
        s.commit()
        s.close()

        r = client.post(
            f"/api/v1/articles/{target.id}/merge-proposals", json={"fork_article_id": fork.id}, headers=self._auth(forker)
        )
        pid = r.json()["id"]
        resp = client.post(f"/api/v1/articles/{target.id}/merge-proposals/{pid}/reject", headers=self._auth(outsider))
        assert resp.status_code == 403

    def test_search_empty_q_with_category(self, client, db_engine):
        """Search with only category filter, no query text."""
        s = get_session(db_engine)
        u = User(username="user27", password_hash="", name="测试", anonymous_name="a")
        s.add(u)
        s.commit()
        a1 = Article(status="published", title="Article A", categories=["math"])
        a2 = Article(status="published", title="Article B", categories=["physics"])
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
        low = Article(
            status="published",
            title="Low Score",
            score={"originality": 1, "rigor": 1, "completeness": 1, "pedagogy": 1, "impact": 1},
        )
        high = Article(
            status="published",
            title="High Score",
            score={"originality": 5, "rigor": 5, "completeness": 5, "pedagogy": 5, "impact": 5},
        )
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
            a = Article(status="published", title=f"Page Article {i + 1}")
            articles.append(a)
        s.add_all(articles)
        s.commit()
        # Collect IDs in creation order (oldest first since no created_at override)
        [a.id for a in articles]
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


# ═══════════════════════════════════════════════════════════════════════════════
# Compilation edge cases
# ═══════════════════════════════════════════════════════════════════════════════


class TestCompileEdgeCases:
    """Compile endpoint behavior with various input types."""

    def test_compile_markdown_with_math(self, client):
        """Markdown with KaTeX math delimiters should compile correctly."""
        resp = client.post(
            "/api/v1/compile-preview",
            json={
                "content": "# Math Test\n\n$$E = mc^2$$\n\nInline $x^2$ math.",
                "format": "markdown",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["format"] == "html"
        # Math should be preserved (not corrupted by markdown parser)
        output = data["output"]
        assert "E = mc^2" in output or "katex" in output.lower() or "math" in output.lower()

    def test_compile_markdown_with_chinese(self, client):
        """Markdown with Chinese characters should compile without corruption."""
        resp = client.post(
            "/api/v1/compile-preview",
            json={
                "content": "# 中文测试\n\n这是**一段**中文内容。\n\n- 列表项一\n- 列表项二",
                "format": "markdown",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["format"] == "html"
        assert "中文测试" in data["output"]
        assert "列表项一" in data["output"]

    def test_compile_empty_content(self, client):
        """Empty content should return empty/simple HTML, not crash."""
        resp = client.post(
            "/api/v1/compile-preview",
            json={
                "content": "",
                "format": "markdown",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["format"] == "html"
        assert isinstance(data["output"], str)

    def test_compile_download_returns_html_for_markdown(self, client):
        """Compile download returns HTML Content-Type for markdown."""
        resp = client.post(
            "/api/v1/compile-download",
            json={
                "content": "# Download Test\n\nContent.",
                "format": "markdown",
            },
        )
        assert resp.status_code == 200
        content_type = resp.headers.get("content-type", "")
        assert "html" in content_type or "Download Test" in resp.text

    def test_compile_preview_typst_graceful(self, client):
        """Typst preview returns SVG if CLI available, else 500 with message."""
        import shutil

        resp = client.post(
            "/api/v1/compile-preview",
            json={
                "content": "= Hello\nThis is a test.",
                "format": "typst",
            },
        )
        if shutil.which("typst") is None:
            assert resp.status_code == 500
        else:
            assert resp.status_code == 200
            assert "svg" in resp.json()["format"]


# ═══════════════════════════════════════════════════════════════════════════════
# Compile download regression tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestCompileDownload:
    """Regression: compile-download endpoint returns downloadable files."""

    def test_download_markdown_returns_html(self, client):
        """Markdown compile-download returns HTML with correct Content-Type."""
        resp = client.post(
            "/api/v1/compile-download",
            json={
                "content": "# Test\n\nHello world.",
                "format": "markdown",
            },
        )
        assert resp.status_code == 200
        content_type = resp.headers.get("content-type", "")
        assert "html" in content_type

    def test_download_typst_returns_pdf(self, client):
        """Typst compile-download returns PDF (or 500 if CLI missing)."""
        import shutil

        resp = client.post(
            "/api/v1/compile-download",
            json={
                "content": "= Hello\nThis is a test.",
                "format": "typst",
            },
        )
        if shutil.which("typst") is None:
            assert resp.status_code == 500
        else:
            assert resp.status_code == 200
            content_type = resp.headers.get("content-type", "")
            assert "pdf" in content_type

    def test_download_unsupported_format_returns_400(self, client):
        """Unsupported format should return 400."""
        resp = client.post(
            "/api/v1/compile-download",
            json={
                "content": "test",
                "format": "unknown",
            },
        )
        assert resp.status_code == 400


class TestCompileHelpersDirect:
    """Direct tests for compile helper functions."""

    def test_compile_typst_svg_error_path(self):
        """_compile_typst_svg raises 500 when backend fails."""
        from unittest.mock import patch

        from fastapi import HTTPException
        from peerpedia_core.storage.compiler import CompileResult

        with patch("peerpedia_core.storage.compiler.TypstBackend.compile") as mock_compile:
            mock_compile.return_value = CompileResult(
                success=False,
                format="typst",
                error="Simulated compilation failure",
            )
            import pytest
            from peerpedia_api.routes.compile import _compile_typst_svg

            with pytest.raises(HTTPException) as exc:
                _compile_typst_svg("= test content")
            assert exc.value.status_code == 500

    def test_compile_typst_pdf_error_path(self):
        """_compile_typst_pdf raises 500 when backend fails."""
        from unittest.mock import patch

        from fastapi import HTTPException
        from peerpedia_core.storage.compiler import CompileResult

        with patch("peerpedia_core.storage.compiler.TypstBackend.compile") as mock_compile:
            mock_compile.return_value = CompileResult(
                success=False,
                format="typst",
                error="Simulated PDF failure",
            )
            import pytest
            from peerpedia_api.routes.compile import _compile_typst_pdf

            with pytest.raises(HTTPException) as exc:
                _compile_typst_pdf("= test")
            assert exc.value.status_code == 500

    def test_compile_markdown_error_path(self):
        """_compile_markdown raises 500 when backend fails."""
        from unittest.mock import patch

        from fastapi import HTTPException
        from peerpedia_core.storage.compiler import CompileResult

        with patch("peerpedia_core.storage.compiler.MarkdownBackend.compile") as mock_compile:
            mock_compile.return_value = CompileResult(
                success=False,
                format="markdown",
                error="Simulated markdown failure",
            )
            import pytest
            from peerpedia_api.routes.compile import _compile_markdown

            with pytest.raises(HTTPException) as exc:
                _compile_markdown("# test")
            assert exc.value.status_code == 500

    def test_compile_typst_svg_output_path_fallback(self):
        """Read SVG from output path when html_content is empty."""
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        from peerpedia_core.storage.compiler import CompileResult

        with tempfile.TemporaryDirectory() as tmp:
            svg_file = Path(tmp) / "out" / "article.svg"
            svg_file.parent.mkdir()
            svg_file.write_text("<svg>Mock SVG</svg>")

            result = CompileResult(
                success=True,
                format="typst-svg",
                output_path=str(svg_file),
                html_content=None,  # Force file read path
            )

            with patch(
                "peerpedia_core.storage.compiler.TypstBackend.compile",
                return_value=result,
            ):
                from peerpedia_api.routes.compile import _compile_typst_svg

                output = _compile_typst_svg("= test")
                assert output == "<svg>Mock SVG</svg>"

    def test_compile_typst_pdf_output_not_found(self):
        """_compile_typst_pdf raises 500 when PDF output file not found."""
        from unittest.mock import patch

        from fastapi import HTTPException
        from peerpedia_core.storage.compiler import CompileResult

        result = CompileResult(
            success=True,
            format="typst-pdf",
            output_path="/nonexistent/path/file.pdf",
            html_content=None,
        )

        with patch(
            "peerpedia_core.storage.compiler.TypstBackend.compile",
            return_value=result,
        ):
            import pytest
            from peerpedia_api.routes.compile import _compile_typst_pdf

            with pytest.raises(HTTPException) as exc:
                _compile_typst_pdf("= test")
            assert "PDF output not found" in str(exc.value.detail)


class TestCompileRouteErrorHandlers:
    """Exception handler catch-all paths in compile routes."""

    def test_compile_preview_catches_unexpected_error(self, client):
        """When _compile_markdown throws a non-HTTPException, it becomes 500."""
        from unittest.mock import patch

        with patch(
            "peerpedia_api.routes.compile._compile_markdown",
            side_effect=RuntimeError("Unexpected runtime error"),
        ):
            resp = client.post(
                "/api/v1/compile-preview",
                json={
                    "content": "# Test",
                    "format": "markdown",
                },
            )
            assert resp.status_code == 500
            assert "Unexpected runtime error" in resp.json()["detail"]

    def test_compile_download_catches_unexpected_error(self, client):
        """When _compile_markdown throws a non-HTTPException, it becomes 500."""
        from unittest.mock import patch

        with patch(
            "peerpedia_api.routes.compile._compile_markdown",
            side_effect=RuntimeError("Download runtime error"),
        ):
            resp = client.post(
                "/api/v1/compile-download",
                json={
                    "content": "# Test",
                    "format": "markdown",
                },
            )
            assert resp.status_code == 500
            assert "Download runtime error" in resp.json()["detail"]
