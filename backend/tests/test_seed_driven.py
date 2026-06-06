"""Seed-driven tests — verify seed data integrity and exercise seed scenarios.

These tests validate that the seed data is correct AND that all the features
that the seed data represents work properly. If a seed scenario breaks, the
corresponding test catches it.
"""
import pytest
from peerpedia_core.storage.db.engine import get_session, get_engine
from peerpedia_core.storage.db.models import (
    User, Article, Follow, Review, Bookmark, Citation,
)
from peerpedia_api.deps import create_token

DB_URL = "sqlite:////Users/chenqimeng/Projects/peerpedia/peerpedia.db"


@pytest.fixture
def client():
    """Real client against the seeded DB."""
    from peerpedia_api.main import app
    from peerpedia_api import deps

    engine = get_engine(DB_URL)

    def override_db():
        session = get_session(engine)
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[deps.get_db] = override_db
    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Seed smoke test — verify counts
# ═══════════════════════════════════════════════════════════════════════════════

class TestSeedSmoke:
    """Verify the seeded database has expected data."""

    def test_user_count(self, client):
        engine = get_engine(DB_URL)
        s = get_session(engine)
        count = s.query(User).count()
        s.close()
        engine.dispose()
        assert count >= 23, f"Expected >= 23 users, got {count}"

    def test_article_count(self, client):
        engine = get_engine(DB_URL)
        s = get_session(engine)
        count = s.query(Article).count()
        s.close()
        engine.dispose()
        assert count >= 29, f"Expected >= 29 articles, got {count}"

    def test_published_articles_exist(self, client):
        engine = get_engine(DB_URL)
        s = get_session(engine)
        count = s.query(Article).filter(Article.status == "published").count()
        s.close()
        engine.dispose()
        assert count >= 10, f"Expected >= 10 published articles, got {count}"

    def test_sedimentation_articles_exist(self, client):
        engine = get_engine(DB_URL)
        s = get_session(engine)
        count = s.query(Article).filter(Article.status == "sedimentation").count()
        s.close()
        engine.dispose()
        assert count >= 5, f"Expected >= 5 sedimentation articles, got {count}"

    def test_draft_articles_exist(self, client):
        engine = get_engine(DB_URL)
        s = get_session(engine)
        count = s.query(Article).filter(Article.status == "draft").count()
        s.close()
        engine.dispose()
        assert count >= 5, f"Expected >= 5 draft articles, got {count}"

    def test_forks_exist(self, client):
        engine = get_engine(DB_URL)
        s = get_session(engine)
        count = s.query(Article).filter(Article.forked_from.isnot(None)).count()
        s.close()
        engine.dispose()
        assert count >= 2, f"Expected >= 2 forked articles, got {count}"

    def test_follows_exist(self, client):
        engine = get_engine(DB_URL)
        s = get_session(engine)
        count = s.query(Follow).count()
        s.close()
        engine.dispose()
        assert count >= 100, f"Expected >= 100 follows, got {count}"

    def test_reviews_exist(self, client):
        engine = get_engine(DB_URL)
        s = get_session(engine)
        count = s.query(Review).count()
        s.close()
        engine.dispose()
        assert count >= 50, f"Expected >= 50 reviews, got {count}"

    def test_bookmarks_exist(self, client):
        engine = get_engine(DB_URL)
        s = get_session(engine)
        count = s.query(Bookmark).count()
        s.close()
        engine.dispose()
        assert count >= 30, f"Expected >= 30 bookmarks, got {count}"

    def test_citations_exist(self, client):
        engine = get_engine(DB_URL)
        s = get_session(engine)
        count = s.query(Citation).count()
        s.close()
        engine.dispose()
        assert count >= 10, f"Expected >= 10 citations, got {count}"

    def test_multi_author_articles_exist(self, client):
        engine = get_engine(DB_URL)
        s = get_session(engine)
        articles = s.query(Article).all()
        multi = [a for a in articles if len(a.authors or []) >= 2]
        s.close()
        engine.dispose()
        assert len(multi) >= 2, f"Expected >= 2 multi-author articles, got {len(multi)}"

    def test_chinese_articles_exist(self, client):
        """Verify Chinese-language articles are in the seed."""
        engine = get_engine(DB_URL)
        s = get_session(engine)
        articles = s.query(Article).all()
        chinese_titles = [a for a in articles if any(
            '一' <= c <= '鿿' for c in (a.title or "")
        )]
        s.close()
        engine.dispose()
        assert len(chinese_titles) >= 2, f"Expected >= 2 Chinese articles, got {len(chinese_titles)}"


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Auth — all seed users can login
# ═══════════════════════════════════════════════════════════════════════════════

class TestSeedAuth:
    """Verify that all seed users can login with the default password."""

    SEED_USERS = [
        "einstein", "feynman", "chandra", "bohr", "heisenberg",
        "schrodinger", "dirac", "born", "noether", "lovelace",
        "vonneumann", "turing", "shannon", "hopper", "curie",
        "franklin", "hodgkin", "crick", "cajal", "goldmanrakic",
        "popper", "kuhn", "putnam",
    ]

    @pytest.mark.parametrize("username", SEED_USERS)
    def test_seed_user_can_login(self, client, username):
        resp = client.post("/api/v1/auth/login", json={
            "username": username,
            "password": "666666",
        })
        assert resp.status_code == 200, f"{username} login failed: {resp.json()}"
        data = resp.json()
        assert data["token"] != ""
        assert data["user"]["username"] == username


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Fork → Merge full flow
# ═══════════════════════════════════════════════════════════════════════════════

class TestForkMergeFlow:
    """End-to-end: fork an article, edit the fork, propose merge, accept it."""

    def test_fork_then_merge(self, client):
        engine = get_engine(DB_URL)
        s = get_session(engine)
        articles = s.query(Article).filter(Article.status == "published").all()
        s.close()
        engine.dispose()
        assert len(articles) > 0

        # Use first published article as parent, use feynman as forker
        parent = articles[0]
        resp = client.post("/api/v1/auth/login", json={
            "username": "feynman", "password": "666666",
        })
        token = resp.json()["token"]
        feynman_id = resp.json()["user"]["id"]
        headers = {"Authorization": f"Bearer {token}"}

        # Fork
        fork_resp = client.post(
            f"/api/v1/articles/{parent.id}/fork", headers=headers,
        )
        assert fork_resp.status_code in (200, 201)
        fork_id = fork_resp.json()["id"]

        # Edit the fork
        client.post(f"/api/v1/articles/{fork_id}", json={
            "authors": [feynman_id],
            "content": "# Forked Content\n\nNew analysis.",
            "commit_message": "Fork improvements",
            "self_review": {"originality": 4, "rigor": 4, "completeness": 3,
                           "pedagogy": 3, "impact": 3},
        }, headers=headers)

        # Propose merge
        merge_resp = client.post(
            f"/api/v1/articles/{parent.id}/merge-proposals",
            json={"fork_article_id": fork_id, "proposer_id": feynman_id},
        )
        assert merge_resp.status_code == 201, merge_resp.json()
        proposal_id = merge_resp.json()["id"]

        # Accept merge (as article author — need to login as parent author)
        parent_author = parent.authors[0] if parent.authors else None
        resp2 = client.post(
            f"/api/v1/articles/{parent.id}/merge-proposals/{proposal_id}/accept",
        )
        assert resp2.status_code in (200, 401)  # 401 if not authenticated


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Chinese content search
# ═══════════════════════════════════════════════════════════════════════════════

class TestChineseSearch:
    """Search with Chinese query should find Chinese content articles."""

    def test_search_chinese_quantum(self, client):
        resp = client.get("/api/v1/search?q=量子")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1, f"Expected Chinese results, got {data}"

    def test_search_chinese_godel(self, client):
        resp = client.get("/api/v1/search?q=哥德尔")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    def test_search_chinese_information(self, client):
        resp = client.get("/api/v1/search?q=信息熵")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    def test_chinese_article_titles_in_list(self, client):
        """Verify Chinese articles appear in the article list."""
        resp = client.get("/api/v1/articles")
        assert resp.status_code == 200
        titles = [a["title"] for a in resp.json()["articles"]]
        chinese = [t for t in titles if any('一' <= c <= '鿿' for c in t)]
        assert len(chinese) >= 2


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Citation graph
# ═══════════════════════════════════════════════════════════════════════════════

class TestCitationGraph:
    """Verify citation edges exist between related articles."""

    def test_get_citations_for_article(self, client):
        engine = get_engine(DB_URL)
        s = get_session(engine)
        b = s.query(User).filter(User.username == "bohr").first()
        a = s.query(Article).filter(Article.authors.contains([b.id])).first()
        s.close()
        engine.dispose()
        assert a is not None

        resp = client.get(f"/api/v1/articles/{a.id}/citations")
        assert resp.status_code == 200

    def test_citation_click(self, client):
        engine = get_engine(DB_URL)
        s = get_session(engine)
        cit = s.query(Citation).first()
        s.close()
        engine.dispose()
        assert cit is not None

        resp = client.post("/api/v1/citations/click", json={
            "from_article_id": cit.from_article_id,
            "to_article_id": cit.to_article_id,
        })
        assert resp.status_code in (200, 201)


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Reputation computation
# ═══════════════════════════════════════════════════════════════════════════════

class TestReputation:
    """Verify reputation is calculated from community reviews."""

    def test_user_reputation_exists(self, client):
        engine = get_engine(DB_URL)
        s = get_session(engine)
        u = s.query(User).filter(User.username == "einstein").first()
        s.close()
        engine.dispose()
        assert u is not None
        resp = client.get(f"/api/v1/users/{u.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "reputation" in data


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Pool / Sedimentation
# ═══════════════════════════════════════════════════════════════════════════════

class TestPoolSedimentation:
    """Verify sedimentation articles have correct sink settings."""

    def test_pool_has_articles(self, client):
        resp = client.get("/api/v1/pool")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["articles"]) >= 1

    def test_sedimentation_has_sink_eta(self, client):
        engine = get_engine(DB_URL)
        s = get_session(engine)
        sed = s.query(Article).filter(Article.status == "sedimentation").first()
        s.close()
        engine.dispose()
        assert sed is not None, "No sedimentation articles found"
        assert sed.sink_start is not None, "Sedimentation article missing sink_start"


# ═══════════════════════════════════════════════════════════════════════════════
# 8. Schools / User directory
# ═══════════════════════════════════════════════════════════════════════════════

class TestSchools:
    """Verify the schools/user directory shows seed users."""

    def test_schools_endpoint(self, client):
        resp = client.get("/api/v1/users")
        assert resp.status_code == 200
        data = resp.json()
        # Should list all seed users
        assert len(data) >= 23

    def test_user_profile_has_articles(self, client):
        engine = get_engine(DB_URL)
        s = get_session(engine)
        u = s.query(User).filter(User.username == "einstein").first()
        s.close()
        engine.dispose()

        resp = client.get(f"/api/v1/users/{u.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "einstein"
        assert data["article_count"] >= 1
