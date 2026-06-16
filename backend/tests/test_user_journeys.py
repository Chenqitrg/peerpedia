# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""End-to-end user journey tests — black-box, multi-step, cross-API.

These tests verify complete user stories from the user's perspective:
what they do and what they see, not how the code works internally.
Each test simulates a real user session across multiple API calls.

Philosophy per docs/test_requirement.md:
- Tests user behavior, not implementation
- Stable across code refactoring
- Large-scale closed-loop, connecting frontend↔backend concepts
- Almost uniquely determines current functionality
"""
import pytest
from fastapi.testclient import TestClient
from peerpedia_core.storage.db.engine import get_session


@pytest.fixture
def client(db_engine):
    """TestClient with DB override (no auth override — tests manage their own auth)."""
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


def _login(client, username: str, password: str) -> dict:
    """Login helper — returns (token, user_dict)."""
    resp = client.post("/api/v1/auth/login", json={
        "username": username,
        "password": password,
    })
    assert resp.status_code == 200, f"Login failed: {resp.json()}"
    data = resp.json()
    return {"token": data["token"], "user": data["user"]}


def _register(client, username: str, password: str, email: str, name: str) -> dict:
    """Register helper — returns (token, user_dict)."""
    resp = client.post("/api/v1/auth/register", json={
        "username": username,
        "password": password,
        "email": email,
        "name": name,
    })
    assert resp.status_code == 201, f"Register failed: {resp.json()}"
    data = resp.json()
    return {"token": data["token"], "user": data["user"]}


# ═══════════════════════════════════════════════════════════════════════════════
# Journey 1: Register → Write → Review → Pool → Publish
# ═══════════════════════════════════════════════════════════════════════════════

class TestJourneyWriteReviewPublish:
    """A complete user journey: two users register, one writes an article,
    the other reviews it, and the article flows through the pool."""

    def test_full_write_review_publish_flow(self, client):
        # 1. Register author and reviewer
        author = _register(client, "journey_author", "pass123!", "author@test.com", "孙悟空")
        reviewer = _register(client, "journey_reviewer", "pass123!", "rv@test.com", "唐僧")
        author_headers = {"Authorization": f"Bearer {author['token']}"}
        reviewer_headers = {"Authorization": f"Bearer {reviewer['token']}"}

        # 2. Author creates an article → starts as draft
        create_body = {
            "authors": [author["user"]["id"]],
            "content": "# 西游记新解\n\n大闹天宫是一场革命。",
            "format": "markdown",
            "title": "西游记新解",
            "self_review": {
                "originality": 5, "rigor": 4, "completeness": 4,
                "pedagogy": 5, "impact": 4,
            },
        }
        resp = client.post("/api/v1/articles", json=create_body, headers=author_headers)
        assert resp.status_code == 201, f"Create article failed: {resp.json()}"
        article = resp.json()
        article_id = article["id"]
        assert article["status"] == "draft"
        assert article["authors"][0]["name"] == "孙悟空"

        # 3. Author publishes the article → enters sedimentation pool
        pub_resp = client.post(f"/api/v1/articles/{article_id}/publish", headers=author_headers)
        assert pub_resp.status_code == 200
        assert pub_resp.json()["status"] == "sedimentation"

        # 4. Article appears in the pool (author can see their own article)
        pool_resp = client.get("/api/v1/pool", headers=author_headers)
        assert pool_resp.status_code == 200
        pool_articles = pool_resp.json()["articles"]
        assert any(a["id"] == article_id for a in pool_articles), \
            "New article should appear in pool"

        # 4. Reviewer submits a pool review
        # First get the commit hash from history
        hist_resp = client.get(f"/api/v1/articles/{article_id}/history")
        assert hist_resp.status_code == 200
        commits = hist_resp.json()["commits"]
        assert len(commits) >= 1
        commit_hash = commits[0]["hash"]

        review_body = {
            "article_id": article_id,
            "commit_hash": commit_hash,
            "scope": "pool",
            "scores": {
                "originality": 5, "rigor": 4, "completeness": 3,
                "pedagogy": 5, "impact": 5,
            },
        }
        rev_resp = client.post(
            f"/api/v1/articles/{article_id}/reviews",
            json=review_body,
            headers=reviewer_headers,
        )
        assert rev_resp.status_code == 201, f"Review submit failed: {rev_resp.json()}"
        review_data = rev_resp.json()
        assert review_data["reviewer_id"] == reviewer["user"]["id"]
        assert review_data["scope"] == "pool"

        # 5. Review appears in article's review list with anonymous name (pool scope)
        list_resp = client.get(f"/api/v1/articles/{article_id}/reviews")
        assert list_resp.status_code == 200
        reviews = list_resp.json()
        community_reviews = [r for r in reviews if not r["is_self_review"]]
        assert len(community_reviews) >= 1
        # Pool reviews should show anonymous name, not real name
        community_review = community_reviews[0]
        assert community_review["reviewer_name"] != "唐僧", \
            "Pool review should use anonymous name, not real name"

        # 6. Article score is updated after review
        article_resp = client.get(f"/api/v1/articles/{article_id}")
        assert article_resp.status_code == 200
        updated_article = article_resp.json()
        assert updated_article["score"] is not None
        assert "originality" in updated_article["score"]


# ═══════════════════════════════════════════════════════════════════════════════
# Journey 2: Fork → Edit → Propose Merge → Accept
# ═══════════════════════════════════════════════════════════════════════════════

class TestJourneyForkEditMerge:
    """A user forks an article, edits it, and proposes a merge back."""

    def test_full_fork_edit_merge_flow(self, client):
        # 1. Register original author and forker
        orig = _register(client, "merge_orig", "pass123!", "orig@test.com", "老子")
        forker = _register(client, "merge_forker", "pass123!", "fork@test.com", "庄子")
        orig_headers = {"Authorization": f"Bearer {orig['token']}"}
        forker_headers = {"Authorization": f"Bearer {forker['token']}"}

        # 2. Original author creates and publishes an article
        create_body = {
            "authors": [orig["user"]["id"]],
            "content": "# 道德经\n\n道可道，非常道。",
            "format": "markdown",
            "title": "道德经",
            "self_review": {
                "originality": 5, "rigor": 4, "completeness": 5,
                "pedagogy": 4, "impact": 5,
            },
        }
        resp = client.post("/api/v1/articles", json=create_body, headers=orig_headers)
        assert resp.status_code == 201
        original_id = resp.json()["id"]

        # Publish and set status to published so it can be forked
        pub_resp = client.post(
            f"/api/v1/articles/{original_id}/publish",
            headers=orig_headers,
        )
        assert pub_resp.status_code == 200

        # Transition to published (pool articles are not forkable per spec)
        from peerpedia_api import deps
        s = next(client.app.dependency_overrides[deps.get_db]())
        from peerpedia_core.storage.db.models import Article
        a = s.get(Article, original_id)
        a.status = "published"
        s.commit()
        s.close()

        # 3. Forker forks the published article
        fork_resp = client.post(
            f"/api/v1/articles/{original_id}/fork",
            headers=forker_headers,
        )
        assert fork_resp.status_code == 201, f"Fork failed: {fork_resp.json()}"
        fork_id = fork_resp.json()["id"]
        assert fork_id != original_id

        # 4. Forker edits the fork
        edit_body = {
            "authors": [forker["user"]["id"]],
            "content": "# 道德经注\n\n道可道，非常道。\n\n庄子注：此道无形无相。",
            "format": "markdown",
            "commit_message": "Add Zhuangzi commentary",
            "self_review": {
                "originality": 4, "rigor": 3, "completeness": 4,
                "pedagogy": 4, "impact": 3,
            },
        }
        edit_resp = client.put(
            f"/api/v1/articles/{fork_id}",
            json=edit_body,
            headers=forker_headers,
        )
        assert edit_resp.status_code == 200, f"Edit fork failed: {edit_resp.json()}"

        # 5. Forker proposes merge back to original
        merge_body = {
            "fork_article_id": fork_id,
        }
        merge_resp = client.post(
            f"/api/v1/articles/{original_id}/merge-proposals",
            json=merge_body,
            headers=forker_headers,
        )
        assert merge_resp.status_code == 201, f"Merge proposal failed: {merge_resp.json()}"
        proposal = merge_resp.json()
        assert proposal["status"] == "open"
        proposal_id = proposal["id"]

        # 6. Merge proposal appears in the list
        list_resp = client.get(f"/api/v1/articles/{original_id}/merge-proposals")
        assert list_resp.status_code == 200
        proposals = list_resp.json()["proposals"]
        assert any(p["id"] == proposal_id for p in proposals)

        # 7. Original author accepts the merge
        accept_resp = client.post(
            f"/api/v1/articles/{original_id}/merge-proposals/{proposal_id}/accept",
            headers=orig_headers,
        )
        assert accept_resp.status_code == 200, f"Accept merge failed: {accept_resp.json()}"
        assert accept_resp.json()["status"] == "accepted"


# ═══════════════════════════════════════════════════════════════════════════════
# Journey 3: Bookmark → List → Unbookmark
# ═══════════════════════════════════════════════════════════════════════════════

class TestJourneyBookmarkLifecycle:
    """A user bookmarks articles, views their collection, and removes bookmarks."""

    def test_full_bookmark_lifecycle(self, client):
        # 1. Register reader and author
        reader = _register(client, "bm_reader", "pass123!", "reader@test.com", "孔子")
        author = _register(client, "bm_author", "pass123!", "auth@test.com", "孟子")
        reader_headers = {"Authorization": f"Bearer {reader['token']}"}
        author_headers = {"Authorization": f"Bearer {author['token']}"}

        # 2. Author creates two articles
        articles = []
        for i, title in enumerate(["论语", "大学"]):
            body = {
                "authors": [author["user"]["id"]],
                "content": f"# {title}\n\n内容。",
                "format": "markdown",
                "title": title,
                "self_review": {
                    "originality": 4, "rigor": 3, "completeness": 4,
                    "pedagogy": 3, "impact": 4,
                },
            }
            resp = client.post("/api/v1/articles", json=body, headers=author_headers)
            assert resp.status_code == 201
            articles.append(resp.json()["id"])

        # 3. Reader bookmarks both articles
        for aid in articles:
            bm_resp = client.post(
                f"/api/v1/bookmarks?article_id={aid}",
                headers=reader_headers,
            )
            assert bm_resp.status_code == 201
            assert bm_resp.json()["bookmarked"] is True

        # 4. Bookmarks appear in reader's list
        list_resp = client.get("/api/v1/bookmarks", headers=reader_headers)
        assert list_resp.status_code == 200
        bookmarks = list_resp.json()["bookmarks"]
        assert len(bookmarks) == 2
        bm_ids = {b["article_id"] for b in bookmarks}
        assert set(articles) == bm_ids

        # 5. Reader removes first bookmark
        del_resp = client.delete(
            f"/api/v1/bookmarks/{articles[0]}",
            headers=reader_headers,
        )
        assert del_resp.status_code == 200
        assert del_resp.json()["bookmarked"] is False

        # 6. Only second bookmark remains
        list2 = client.get("/api/v1/bookmarks", headers=reader_headers)
        remaining = list2.json()["bookmarks"]
        assert len(remaining) == 1
        assert remaining[0]["article_id"] == articles[1]


# ═══════════════════════════════════════════════════════════════════════════════
# Journey 4: Multi-author collaboration
# ═══════════════════════════════════════════════════════════════════════════════

class TestJourneyMultiAuthor:
    """Two users co-author an article and both can see it."""

    def test_multi_author_article_visible_to_both(self, client):
        # 1. Register two co-authors
        co1 = _register(client, "coauthor_a", "pass123!", "ca@test.com", "张衡")
        co2 = _register(client, "coauthor_b", "pass123!", "cb@test.com", "祖冲之")
        co1_headers = {"Authorization": f"Bearer {co1['token']}"}
        co2_headers = {"Authorization": f"Bearer {co2['token']}"}

        # 2. Co-author 1 creates article with both as authors
        body = {
            "authors": [co1["user"]["id"], co2["user"]["id"]],
            "content": "# 天文历法\n\n浑天说与日月星辰。",
            "format": "markdown",
            "title": "天文历法",
            "self_review": {
                "originality": 5, "rigor": 5, "completeness": 4,
                "pedagogy": 3, "impact": 4,
            },
            "contributions": {
                co1["user"]["id"]: {
                    "originality": 5, "rigor": 5, "completeness": 3,
                    "pedagogy": 2, "impact": 3,
                },
                co2["user"]["id"]: {
                    "originality": 3, "rigor": 4, "completeness": 4,
                    "pedagogy": 4, "impact": 4,
                },
            },
        }
        resp = client.post("/api/v1/articles", json=body, headers=co1_headers)
        assert resp.status_code == 201
        article = resp.json()
        article_id = article["id"]

        # 3. Both authors listed
        author_names = {a["name"] for a in article["authors"]}
        assert author_names == {"张衡", "祖冲之"}

        # 4. Both users can see the article and it's marked as their own
        for headers in (co1_headers, co2_headers):
            get_resp = client.get(f"/api/v1/articles/{article_id}", headers=headers)
            assert get_resp.status_code == 200
            assert get_resp.json()["is_own_article"] is True

        # 5. Publish the article → enters pool
        pub_resp = client.post(f"/api/v1/articles/{article_id}/publish", headers=co1_headers)
        assert pub_resp.status_code == 200

        # 6. Article appears in pool
        pool_resp = client.get("/api/v1/pool", headers=co1_headers)
        assert pool_resp.status_code == 200
        assert any(a["id"] == article_id for a in pool_resp.json()["articles"])


# ═══════════════════════════════════════════════════════════════════════════════
# Journey 5: Create → Delete → Verify Gone
# ═══════════════════════════════════════════════════════════════════════════════

class TestJourneyDeleteArticle:
    """A user creates an article, then deletes it — verify complete removal."""

    def test_create_then_delete_article(self, client):
        # 1. Register a user
        user = _register(client, "delete_user", "pass123!", "del@test.com", "韩非")
        headers = {"Authorization": f"Bearer {user['token']}"}

        # 2. Create an article
        body = {
            "authors": [user["user"]["id"]],
            "content": "# 韩非子\n\n法、术、势，三者皆帝王之具也。",
            "format": "markdown",
            "title": "韩非子",
            "self_review": {
                "originality": 5, "rigor": 4, "completeness": 5,
                "pedagogy": 4, "impact": 5,
            },
        }
        resp = client.post("/api/v1/articles", json=body, headers=headers)
        assert resp.status_code == 201
        article_id = resp.json()["id"]

        # 3. Verify article exists
        get_resp = client.get(f"/api/v1/articles/{article_id}", headers=headers)
        assert get_resp.status_code == 200
        assert get_resp.json()["title"] == "韩非子"

        # 4. Delete the article (only the author can delete)
        del_resp = client.delete(f"/api/v1/articles/{article_id}", headers=headers)
        assert del_resp.status_code == 204, \
            f"Delete should return 204, got {del_resp.status_code}: {del_resp.text}"

        # 5. Verify article is gone — GET returns 404
        get_resp2 = client.get(f"/api/v1/articles/{article_id}")
        assert get_resp2.status_code == 404, \
            "Article should return 404 after deletion"

    def test_delete_non_author_rejected(self, client):
        """Only the article author can delete — others get 403."""
        # 1. Register author and another user
        author = _register(client, "del_author", "pass123!", "da@test.com", "商鞅")
        other = _register(client, "del_other", "pass123!", "do@test.com", "李斯")
        author_headers = {"Authorization": f"Bearer {author['token']}"}
        other_headers = {"Authorization": f"Bearer {other['token']}"}

        # 2. Author creates an article
        body = {
            "authors": [author["user"]["id"]],
            "content": "# 商君书\n\n治世不一道，便国不必法古。",
            "format": "markdown",
            "title": "商君书",
            "self_review": {
                "originality": 4, "rigor": 4, "completeness": 4,
                "pedagogy": 3, "impact": 4,
            },
        }
        resp = client.post("/api/v1/articles", json=body, headers=author_headers)
        assert resp.status_code == 201
        article_id = resp.json()["id"]

        # 3. Other user tries to delete → 403
        del_resp = client.delete(f"/api/v1/articles/{article_id}", headers=other_headers)
        assert del_resp.status_code == 403, \
            f"Non-author should get 403, got {del_resp.status_code}"

        # 4. Verify article still exists (must authenticate as author for draft)
        get_resp = client.get(f"/api/v1/articles/{article_id}", headers=author_headers)
        assert get_resp.status_code == 200
