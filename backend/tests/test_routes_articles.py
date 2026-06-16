# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Integration tests for article API routes."""
import pytest
from fastapi.testclient import TestClient
from peerpedia_core.storage.db.engine import get_session
from peerpedia_core.storage.db.models import Article, ArticleAuthor, User


@pytest.fixture
def client(db_engine):
    from peerpedia_api import deps
    from peerpedia_api.main import app
    from peerpedia_core.storage.db.engine import get_session
    from peerpedia_core.storage.db.models import User

    def override_db():
        session = get_session(db_engine)
        try:
            yield session
        finally:
            session.close()

    # Use the same user as seed_user fixture (user21) so auth user ==
    # default article author.  Policy checks require the authenticated
    # user to be an author for draft access.
    s = get_session(db_engine)
    _u = User(username="user21", password_hash="",
               name="测试用户", anonymous_name="anon_test", affiliation="测试大学")
    s.add(_u)
    s.commit()
    _uid = _u.id
    _user_obj = s.get(User, _uid)
    s.close()

    def override_require_user():
        return _user_obj

    def override_get_current_user():
        return _user_obj

    app.dependency_overrides[deps.get_db] = override_db
    app.dependency_overrides[deps.require_user] = override_require_user
    app.dependency_overrides[deps.get_current_user] = override_get_current_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def seed_user(db_engine):
    s = get_session(db_engine)
    u = s.query(User).filter(User.username == "user21").first()
    if u is None:
        u = User(username="user21", password_hash="", name="测试用户", anonymous_name="anon_test", affiliation="测试大学")
        s.add(u)
        s.commit()
    uid = u.id
    s.close()
    return uid


@pytest.fixture
def auth_user_id(db_engine):
    """Return the ID of the client's implicit auth user (user21)."""
    s = get_session(db_engine)
    u = s.query(User).filter(User.username == "user21").first()
    uid = u.id
    s.close()
    return uid


@pytest.fixture
def second_user(db_engine):
    """Create a second user distinct from the auth user (for multi-author tests)."""
    s = get_session(db_engine)
    u = s.query(User).filter(User.username == "user22").first()
    if u is None:
        u = User(username="user22", password_hash="", name="SecondUser",
                 anonymous_name="anon2", affiliation="U2")
        s.add(u)
        s.commit()
    uid = u.id
    s.close()
    return uid


@pytest.fixture
def seed_article(db_engine, seed_user):
    s = get_session(db_engine)
    a = Article(status="published", fork_count=0)
    s.add(a)
    s.commit()
    aid = a.id
    s.close()
    return aid


class TestListArticles:
    def test_empty_list(self, client):
        resp = client.get("/api/v1/articles")
        assert resp.status_code == 200
        assert resp.json()["articles"] == []

    def test_list_with_articles(self, client, seed_article):
        resp = client.get("/api/v1/articles")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["articles"]) >= 1
        assert data["articles"][0]["id"] == seed_article

    def test_filter_by_status(self, client, seed_article):
        resp = client.get("/api/v1/articles?status=published")
        assert resp.status_code == 200
        for a in resp.json()["articles"]:
            assert a["status"] == "published"

    def test_filter_nonexistent_status(self, client):
        resp = client.get("/api/v1/articles?status=draft")
        assert resp.status_code == 200
        assert resp.json()["articles"] == []


class TestGetArticle:
    def test_get_existing(self, client, seed_article):
        resp = client.get(f"/api/v1/articles/{seed_article}")
        assert resp.status_code == 200
        assert resp.json()["id"] == seed_article

    def test_get_nonexistent(self, client):
        resp = client.get("/api/v1/articles/nonexistent")
        assert resp.status_code == 404


class TestCreateArticle:
    def test_create_minimal(self, client, seed_user):
        body = {
            "authors": [seed_user],
            "self_review": {"originality": 4, "rigor": 3, "completeness": 4,
                            "pedagogy": 3, "impact": 3},
        }
        resp = client.post("/api/v1/articles", json=body)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "draft"
        assert data["authors"][0]["id"] == seed_user

    def test_create_missing_self_review(self, client, seed_user):
        """self_review is optional for draft creation; only required at publish time."""
        resp = client.post("/api/v1/articles", json={
            "authors": [seed_user],
            "title": "Draft without self-review",
            "content": "# Test",
            "format": "markdown",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "draft"
        assert data["score"] is None

    def test_create_publish_without_self_review_rejected(self, client, seed_user):
        """Publishing without self_review must be rejected with 400."""
        resp = client.post("/api/v1/articles", json={
            "authors": [seed_user],
            "title": "Publish without review",
            "content": "# Test",
            "format": "markdown",
            "publish": True,
        })
        assert resp.status_code == 400
        assert "self_review is required" in resp.json()["detail"]

    def test_update_publish_without_self_review_rejected(self, client, auth_user_id):
        """Updating with publish=true but no self_review must be rejected."""
        # Create a draft first (auth_user_id is the implicit require_user override)
        resp = client.post("/api/v1/articles", json={
            "authors": [auth_user_id],
            "title": "Draft to publish",
            "content": "# Test",
            "format": "markdown",
        })
        assert resp.status_code == 201
        article_id = resp.json()["id"]

        # Try to publish via update without self_review
        resp2 = client.put(f"/api/v1/articles/{article_id}", json={
            "content": "# Updated",
            "publish": True,
        })
        assert resp2.status_code == 400
        assert "self_review is required" in resp2.json()["detail"]

    def test_create_with_all_metadata(self, client, seed_user):
        """Create article with categories, keywords, abstract, contributions."""
        body = {
            "authors": [seed_user],
            "self_review": {"originality": 5, "rigor": 4, "completeness": 4,
                            "pedagogy": 3, "impact": 4},
            "title": "Quantum Entanglement in Many-Body Systems",
            "abstract": "A comprehensive review of entanglement measures.",
            "keywords": ["quantum", "entanglement", "many-body"],
            "categories": ["physics", "quantum"],
            "contributions": {seed_user: {"originality": 5, "rigor": 4,
                                           "completeness": 4, "pedagogy": 3,
                                           "impact": 4}},
            "format": "markdown",
            "content": "# Introduction\n\nEntanglement is a fundamental resource...",
            "commit_message": "Initial draft",
        }
        resp = client.post("/api/v1/articles", json=body)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Quantum Entanglement in Many-Body Systems"

    def test_create_with_empty_content_is_accepted(self, client, seed_user):
        """Empty content is valid — article can be saved as draft."""
        body = {
            "authors": [seed_user],
            "self_review": {"originality": 3, "rigor": 3, "completeness": 3,
                            "pedagogy": 3, "impact": 3},
            "content": "",
        }
        resp = client.post("/api/v1/articles", json=body)
        assert resp.status_code == 201

    def test_create_with_repo_bundle(self, client, auth_user_id):
        """Create article via repo_bundle (Phase B — client sends full git repo as tar.gz)."""
        import base64
        import io
        import json
        import shutil
        import tarfile
        import tempfile
        import uuid
        from pathlib import Path

        from peerpedia_core.storage.git_backend import commit_article, init_article_repo

        # Use a client-generated UUID so the tar directory name matches
        article_uuid = str(uuid.uuid4())

        tmp = tempfile.mkdtemp()
        try:
            src_rp = Path(tmp) / article_uuid
            init_article_repo(article_uuid, base_dir=Path(tmp))
            (src_rp / "article.md").write_text("# Bundle Article\n\nContent.")
            (src_rp / "article.json").write_text(json.dumps({
                "title": "Bundle Article",
                "abstract": "Created via tar.gz bundle",
                "keywords": ["bundle", "test"],
                "categories": ["testing"],
                "status": "draft",
            }))
            commit_article(src_rp, "initial", "Author", f"{auth_user_id}@peerpedia")

            # Tar.gz the repo — extractall(path=rp.parent) expects article_uuid/ dir
            tar_buf = io.BytesIO()
            with tarfile.open(fileobj=tar_buf, mode="w:gz") as tar:
                tar.add(str(src_rp), arcname=article_uuid)
            tar_buf.seek(0)
            b64 = base64.b64encode(tar_buf.read()).decode()

            body = {"authors": [auth_user_id], "repo_bundle": b64, "id": article_uuid}
            resp = client.post("/api/v1/articles", json=body)
            assert resp.status_code == 201
            data = resp.json()
            assert data["id"] == article_uuid
            assert data["status"] == "draft"
            assert data["title"] == "Bundle Article"
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_create_repo_bundle_bad_base64(self, client, auth_user_id):
        """repo_bundle with invalid base64 returns 422."""
        body = {
            "authors": [auth_user_id],
            "repo_bundle": "!!! not valid base64 !!!",
        }
        resp = client.post("/api/v1/articles", json=body)
        assert resp.status_code == 422

    def test_create_repo_bundle_not_a_repo(self, client, auth_user_id):
        """repo_bundle tar.gz without a .git directory returns 422."""
        import base64
        import io
        import tarfile

        # Build a tar.gz with just a file, no .git
        tar_buf = io.BytesIO()
        with tarfile.open(fileobj=tar_buf, mode="w:gz") as tar:
            info = tarfile.TarInfo(name="some-dir/not-a-repo.txt")
            info.size = 0
            tar.addfile(info)

        tar_buf.seek(0)
        b64 = base64.b64encode(tar_buf.read()).decode()

        body = {
            "authors": [auth_user_id],
            "repo_bundle": b64,
        }
        resp = client.post("/api/v1/articles", json=body)
        assert resp.status_code == 422

    def test_create_repo_bundle_corrupt_tar(self, client, auth_user_id):
        """repo_bundle with corrupt tar.gz returns 422."""
        import base64

        # Valid base64 but not a valid gzip stream
        b64 = base64.b64encode(b"not a tar gz file").decode()
        body = {
            "authors": [auth_user_id],
            "repo_bundle": b64,
        }
        resp = client.post("/api/v1/articles", json=body)
        assert resp.status_code == 422

    def test_create_with_publish(self, client, auth_user_id):
        """Create article with publish=true enters the sedimentation pool."""
        body = {
            "authors": [auth_user_id],
            "content": "# Publish Test\n\nContent.",
            "format": "markdown",
            "publish": True,
            "self_review": {"originality": 5, "rigor": 4, "completeness": 4,
                            "pedagogy": 3, "impact": 4},
        }
        resp = client.post("/api/v1/articles", json=body)
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"]
        # Article should be in pool or already progressed to sedimentation
        assert data["status"] in ("pool", "sedimentation")


class TestUpdateArticle:
    def test_update_content_flow(self, client, seed_user, second_user, auth_user_id):
        """Full flow: create article, then edit it."""
        create_body = {
            "authors": [seed_user, second_user],
            "content": "# Original\n\nHello world.",
            "format": "markdown",
            "self_review": {"originality": 4, "rigor": 3, "completeness": 4,
                            "pedagogy": 3, "impact": 3},
        }
        resp = client.post("/api/v1/articles", json=create_body)
        assert resp.status_code == 201
        article_id = resp.json()["id"]

        # Now edit it
        edit_body = {
            "content": "# Edited\n\nUpdated content.",
            "self_review": {"originality": 5, "rigor": 4, "completeness": 5,
                            "pedagogy": 4, "impact": 4},
        }
        resp2 = client.put(f"/api/v1/articles/{article_id}", json=edit_body)
        assert resp2.status_code == 200
        data = resp2.json()
        assert data["id"] == article_id
        assert data["status"] == "draft"

    def test_update_no_content_change(self, client, seed_user, second_user, auth_user_id):
        """Edit without content change: commits, stays draft unless publish=true."""
        create_body = {
            "authors": [seed_user, second_user],
            "content": "# Test",
            "format": "markdown",
            "self_review": {"originality": 3, "rigor": 3, "completeness": 3,
                            "pedagogy": 3, "impact": 3},
        }
        resp = client.post("/api/v1/articles", json=create_body)
        assert resp.status_code == 201
        article_id = resp.json()["id"]

        # Edit without changing content
        edit_body = {
            "self_review": {"originality": 4, "rigor": 4, "completeness": 4,
                            "pedagogy": 4, "impact": 4},
        }
        resp2 = client.put(f"/api/v1/articles/{article_id}", json=edit_body)
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "draft"

    def test_update_nonexistent(self, client):
        resp = client.put("/api/v1/articles/nonexistent", json={"content": "x"})
        assert resp.status_code == 404

    def test_update_no_repo(self, client, seed_user, second_user, db_engine, auth_user_id):
        """Update article that has no git repo (edge case)."""
        from peerpedia_core.storage.db.engine import get_session
        from peerpedia_core.storage.db.models import Article, ArticleAuthor

        s = get_session(db_engine)
        a = Article(status="draft")
        s.add(a)
        s.flush()
        s.add(ArticleAuthor(article_id=a.id, author_id=auth_user_id, position=0))
        s.commit()
        aid = a.id
        s.close()

        resp = client.put(f"/api/v1/articles/{aid}", json={"content": "x"})
        assert resp.status_code == 400

    def test_update_non_author_forbidden(self, client, seed_user, second_user, db_engine, auth_user_id):
        """Non-authors cannot edit; others get 403."""
        # Create article owned by seed_user + auth_user
        create_body = {
            "authors": [seed_user],
            "content": "# Test\n\nContent.",
            "format": "markdown",
            "self_review": {"originality": 4, "rigor": 3, "completeness": 4,
                            "pedagogy": 3, "impact": 3},
        }
        resp = client.post("/api/v1/articles", json=create_body)
        article_id = resp.json()["id"]

        # Create a third user who is NOT an author
        from peerpedia_core.storage.db.engine import get_session
        from peerpedia_core.storage.db.models import User
        s = get_session(db_engine)
        other = User(username="other_editor", password_hash="",
                      name="OtherEditor", anonymous_name="anon_other", affiliation="X")
        s.add(other)
        s.commit()
        other_id = other.id
        s.close()

        # Switch auth to the non-author user
        from peerpedia_api import deps
        s2 = get_session(db_engine)
        other_obj = s2.get(User, other_id)
        app = client.app
        old = app.dependency_overrides.get(deps.require_user)
        try:
            app.dependency_overrides[deps.require_user] = lambda: other_obj
            edit_body = {"content": "# Hacked\n\nEvil edit."}
            resp = client.put(f"/api/v1/articles/{article_id}", json=edit_body)
            assert resp.status_code == 403
        finally:
            if old is not None:
                app.dependency_overrides[deps.require_user] = old
            s2.close()


class TestHistoryWithScores:
    def test_history_includes_per_commit_scores(self, client, seed_user):
        """GET /articles/{id}/history should include score for each commit."""
        create_body = {
            "authors": [seed_user],
            "content": "# V1\n\nFirst version.",
            "format": "markdown",
            "self_review": {"originality": 4, "rigor": 3, "completeness": 4,
                            "pedagogy": 3, "impact": 3},
        }
        resp = client.post("/api/v1/articles", json=create_body)
        article_id = resp.json()["id"]

        history = client.get(f"/api/v1/articles/{article_id}/history")
        assert history.status_code == 200
        data = history.json()
        assert len(data["commits"]) >= 1
        # Each commit should have a score field
        for commit in data["commits"]:
            assert "score" in commit
            # The latest commit should have a score (from self-review)
            if commit == data["commits"][0]:
                assert commit["score"] is not None

    def test_history_multiple_commits_independent_scores(self, client, seed_user, second_user, auth_user_id):
        """After editing, each commit gets its own score."""
        create_body = {
            "authors": [seed_user, second_user],
            "content": "# V1",
            "format": "markdown",
            "self_review": {"originality": 3, "rigor": 3, "completeness": 3,
                            "pedagogy": 3, "impact": 3},
        }
        resp = client.post("/api/v1/articles", json=create_body)
        article_id = resp.json()["id"]

        # Edit to create second commit
        edit_body = {
            "content": "# V2\n\nEdited.",
            "self_review": {"originality": 5, "rigor": 4, "completeness": 5,
                            "pedagogy": 4, "impact": 4},
            "publish": True,
        }
        client.put(f"/api/v1/articles/{article_id}", json=edit_body)

        history = client.get(f"/api/v1/articles/{article_id}/history")
        data = history.json()
        assert len(data["commits"]) >= 2

        # Scores are now aggregated across all commits — both commits
        # should reflect the combined review pool (avg of 3 and 5 = 4.0)
        latest = data["commits"][0]
        assert latest["score"] is not None
        assert latest["score"]["originality"] == 4.0

        older = data["commits"][1]
        assert older["score"] is not None
        assert older["score"]["originality"] == 4.0


class TestScoreBackfill:
    def test_article_without_score_gets_backfilled(self, client, seed_user, second_user, auth_user_id, db_engine):
        """Article with null score gets backfilled on fetch."""
        from peerpedia_core.storage.db.engine import get_session
        from peerpedia_core.storage.db.models import Article

        # Create article via API (now creates score automatically)
        create_body = {
            "authors": [seed_user, second_user],
            "content": "# Backfill test",
            "format": "markdown",
            "self_review": {"originality": 4, "rigor": 3, "completeness": 4,
                            "pedagogy": 3, "impact": 3},
        }
        resp = client.post("/api/v1/articles", json=create_body)
        article_id = resp.json()["id"]
        # Draft: score is None until publish.
        assert resp.json()["score"] is None

        # Publish → score computed.
        pub_resp = client.put(f"/api/v1/articles/{article_id}", json={
            "publish": True,
            "self_review": {"originality": 4, "rigor": 3, "completeness": 4, "pedagogy": 3, "impact": 3},
        })
        assert pub_resp.status_code == 200
        assert pub_resp.json()["score"] is not None  # published article has score

        # Manually null out the score to simulate backfill scenario
        s = get_session(db_engine)
        a = s.get(Article, article_id)
        assert a.status == "sedimentation"
        a.score = None
        s.commit()
        s.close()

        # Fetch should backfill from commit history
        article = client.get(f"/api/v1/articles/{article_id}").json()
        assert article["score"] is not None, f"Backfill failed, article: {article}"
        assert "originality" in article["score"]


class TestScoreNotCleared:
    """Regression tests: article.score must not be cleared when latest commit has no reviews."""

    def test_edit_without_self_review_preserves_score(self, client, seed_user, second_user, auth_user_id):
        """Editing content without self_review should not set score to None."""
        create_body = {
            "authors": [seed_user, second_user],
            "content": "# V1",
            "format": "markdown",
            "self_review": {"originality": 4, "rigor": 3, "completeness": 4,
                            "pedagogy": 3, "impact": 3},
        }
        resp = client.post("/api/v1/articles", json=create_body)
        article_id = resp.json()["id"]
        # Draft: score is None until publish.
        assert resp.json()["score"] is None

        # Publish → score computed.
        client.put(f"/api/v1/articles/{article_id}", json={
            "publish": True,
            "self_review": {"originality": 4, "rigor": 3, "completeness": 4, "pedagogy": 3, "impact": 3},
        })
        # Edit WITHOUT self_review — score persists from publish commit.
        edit_body = {"content": "# V2\n\nNew content."}
        resp2 = client.put(f"/api/v1/articles/{article_id}", json=edit_body)
        assert resp2.status_code == 200
        assert resp2.json()["score"] is not None

    def test_backfill_walks_commits_for_score(self, client, seed_user, second_user, db_engine, auth_user_id):
        """Backfill should find a score from older commit if latest has none."""
        from peerpedia_core.storage.db.engine import get_session
        from peerpedia_core.storage.db.models import Article

        # Create article with self-review (commit A, has score)
        create_body = {
            "authors": [seed_user, second_user],
            "content": "# V1",
            "format": "markdown",
            "self_review": {"originality": 4, "rigor": 3, "completeness": 4,
                            "pedagogy": 3, "impact": 3},
        }
        resp = client.post("/api/v1/articles", json=create_body)
        article_id = resp.json()["id"]

        # Publish → score computed from self_review.
        pub_resp = client.put(f"/api/v1/articles/{article_id}", json={
            "publish": True,
            "self_review": {"originality": 4, "rigor": 3, "completeness": 4, "pedagogy": 3, "impact": 3},
        })
        assert pub_resp.status_code == 200
        assert pub_resp.json()["score"] is not None
        # Edit without self-review (commit B, no reviews)
        edit_body = {"content": "# V2\n\nEdited."}
        client.put(f"/api/v1/articles/{article_id}", json=edit_body)

        # Manually null out the score to simulate backfill scenario
        s = get_session(db_engine)
        a = s.get(Article, article_id)
        a.score = None
        s.commit()
        s.close()

        # Fetch should backfill from commit A (older commit with reviews)
        article = client.get(f"/api/v1/articles/{article_id}").json()
        assert article["score"] is not None, f"Backfill failed after manual null, article: {article}"
        # Should find commit A's score (originality=4), not return None
        assert article["score"]["originality"] == 4.0


class TestPagination:
    def test_list_articles_paginated(self, client, db_engine):
        """GET /articles returns paginated response with page and size."""
        from peerpedia_core.storage.db.engine import get_session
        from peerpedia_core.storage.db.models import Article, User
        s = get_session(db_engine)
        u = User(username="user22", password_hash="", name="pagination_user", anonymous_name="anon_pag")
        s.add(u)
        s.commit()
        for i in range(5):
            s.add(Article(status="published"))
        s.commit()
        s.close()

        resp = client.get("/api/v1/articles?page=1&size=2")
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 1
        assert data["size"] == 2
        assert data["total"] >= 5
        assert len(data["articles"]) == 2

    def test_list_articles_default_pagination(self, client):
        """Default pagination when no params provided."""
        resp = client.get("/api/v1/articles")
        assert resp.status_code == 200
        data = resp.json()
        assert "page" in data
        assert "size" in data
        assert "total" in data


class TestDownloadEndpoints:
    """Tests for download endpoints (source and PDF)."""

    def _create_article_with_content(self, client, seed_user, content, fmt="markdown"):
        """Create article. authors defaults to current auth user (omit seed_user)."""
        create_body: dict = {
            "content": content,
            "format": fmt,
            "self_review": {"originality": 4, "rigor": 3, "completeness": 4,
                            "pedagogy": 3, "impact": 3},
        }
        resp = client.post("/api/v1/articles", json=create_body)
        assert resp.status_code == 201, resp.text
        return resp.json()["id"]

    def test_download_source_markdown(self, client, seed_user):
        """Download source file for a markdown article."""
        aid = self._create_article_with_content(client, seed_user, "# Test\n\nContent.")
        resp = client.get(f"/api/v1/articles/{aid}/download/source")
        assert resp.status_code == 200
        assert "# Test" in resp.text
        assert "Content-Type" in resp.headers

    def test_download_source_typst(self, client, seed_user):
        """Download source file for a Typst article."""
        aid = self._create_article_with_content(
            client, seed_user, "= Introduction\nSome text.", fmt="typst")
        resp = client.get(f"/api/v1/articles/{aid}/download/source")
        assert resp.status_code == 200
        assert "Introduction" in resp.text

    def test_download_source_not_found(self, client):
        """Download source for non-existent article returns 404."""
        resp = client.get("/api/v1/articles/nonexistent/download/source")
        assert resp.status_code == 404

    def test_download_pdf_markdown_returns_html(self, client, seed_user):
        """PDF download for markdown article returns compiled HTML."""
        aid = self._create_article_with_content(client, seed_user, "# Test\n\nContent.")
        resp = client.get(f"/api/v1/articles/{aid}/download/pdf")
        assert resp.status_code == 200
        # Markdown compiler produces HTML
        assert "<h1>" in resp.text or "Test" in resp.text

    def test_download_pdf_not_found(self, client):
        """PDF download for non-existent article returns 404."""
        resp = client.get("/api/v1/articles/nonexistent/download/pdf")
        assert resp.status_code == 404

    def test_download_repo_returns_tar_gz(self, client, seed_user):
        """Download repo bundle returns a valid tar.gz with git history."""
        aid = self._create_article_with_content(
            client, seed_user, "# Test\n\nContent.", fmt="markdown")
        resp = client.get(f"/api/v1/articles/{aid}/download/repo")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/gzip"
        # Verify it's a valid gzip that contains the article + .git
        import io
        import tarfile

        data = resp.content
        # gzip magic bytes
        assert data[:2] == b"\x1f\x8b"
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
            names = tar.getnames()
            assert any("article.md" in n for n in names)
            assert any(".git" in n for n in names)

    def test_download_repo_not_found(self, client):
        """Repo download for non-existent article returns 404."""
        resp = client.get("/api/v1/articles/nonexistent/download/repo")
        assert resp.status_code == 404


class TestDeleteArticle:
    """Tests for DELETE /articles/{id} and core delete_article()."""

    @pytest.fixture
    def owned_article(self, db_engine):
        """Create an article owned by the client's auth user (user21)."""
        from peerpedia_core.storage.db.engine import get_session
        from peerpedia_core.storage.db.models import Article, User

        s = get_session(db_engine)
        auth_user = s.query(User).filter(User.username == "user21").first()
        a = Article(status="draft")
        s.add(a)
        s.flush()
        s.add(ArticleAuthor(article_id=a.id, author_id=auth_user.id, position=0))
        s.commit()
        aid = a.id
        s.close()
        return aid

    def test_delete_article_removes_from_db(self, client, seed_user, db_engine):
        """Core: delete_article() removes article row from database."""
        from peerpedia_core.storage.db.crud_article import delete_article, get_article
        from peerpedia_core.storage.db.engine import get_session

        s = get_session(db_engine)
        a = Article(status="draft")
        s.add(a)
        s.commit()
        article_id = a.id
        s.close()

        s2 = get_session(db_engine)
        delete_article(s2, article_id)
        s2.close()

        s3 = get_session(db_engine)
        assert get_article(s3, article_id) is None
        s3.close()

    def test_delete_article_removes_git_repo(self, client, seed_user, db_engine):
        """Core: delete_article() removes the git repository directory."""
        from peerpedia_core.storage.db.engine import get_session
        from peerpedia_core.storage.db.models import User
        from peerpedia_core.storage.git_backend import DEFAULT_ARTICLES_DIR

        # Get the auth user's ID so the article is owned by the authenticated user
        s = get_session(db_engine)
        auth_user = s.query(User).filter(User.username == "user21").first()
        auth_id = auth_user.id
        s.close()

        create_body = {
            "authors": [auth_id],
            "content": "# Test\n\nContent.",
            "format": "markdown",
            "self_review": {"originality": 4, "rigor": 3, "completeness": 4,
                            "pedagogy": 3, "impact": 3},
        }
        resp = client.post("/api/v1/articles", json=create_body)
        assert resp.status_code == 201
        article_id = resp.json()["id"]

        repo_path = DEFAULT_ARTICLES_DIR / article_id
        assert repo_path.exists()
        assert (repo_path / ".git").is_dir()

        del_resp = client.delete(f"/api/v1/articles/{article_id}")
        assert del_resp.status_code == 204

        assert not repo_path.exists()

    def test_delete_endpoint_returns_204(self, client, owned_article):
        """DELETE /articles/{id} returns 204 on success."""
        resp = client.delete(f"/api/v1/articles/{owned_article}")
        assert resp.status_code == 204

    def test_delete_endpoint_requires_auth(self, client, owned_article):
        """DELETE /articles/{id} returns 401 without authentication."""
        from peerpedia_api import deps
        app = client.app
        old_req = app.dependency_overrides.get(deps.require_user)
        old_cur = app.dependency_overrides.get(deps.get_current_user)
        try:
            app.dependency_overrides.pop(deps.require_user, None)
            app.dependency_overrides.pop(deps.get_current_user, None)
            resp = client.delete(f"/api/v1/articles/{owned_article}")
            assert resp.status_code == 401
        finally:
            if old_req is not None:
                app.dependency_overrides[deps.require_user] = old_req
            if old_cur is not None:
                app.dependency_overrides[deps.get_current_user] = old_cur

    def test_delete_nonexistent_article(self, client):
        """DELETE /articles/nonexistent returns 404."""
        resp = client.delete("/api/v1/articles/nonexistent")
        assert resp.status_code == 404

    def test_delete_article_verify_gone(self, client, owned_article):
        """After DELETE, GET returns 404."""
        del_resp = client.delete(f"/api/v1/articles/{owned_article}")
        assert del_resp.status_code == 204

        get_resp = client.get(f"/api/v1/articles/{owned_article}")
        assert get_resp.status_code == 404

    def test_delete_non_author_forbidden(self, client, owned_article, db_engine):
        """Only article authors can delete; others get 403."""
        from peerpedia_core.storage.db.engine import get_session
        from peerpedia_core.storage.db.models import User

        s = get_session(db_engine)
        other = User(username="other_user", password_hash="",
                      name="Other", anonymous_name="anon_other", affiliation="X")
        s.add(other)
        s.commit()
        other_id = other.id
        s.close()

        from peerpedia_api import deps
        s2 = get_session(db_engine)
        other_obj = s2.get(User, other_id)
        app = client.app
        old = app.dependency_overrides.get(deps.require_user)
        try:
            app.dependency_overrides[deps.require_user] = lambda: other_obj
            resp = client.delete(f"/api/v1/articles/{owned_article}")
            assert resp.status_code == 403
        finally:
            if old is not None:
                app.dependency_overrides[deps.require_user] = old
            s2.close()


# ═══════════════════════════════════════════════════════════════════════════════
# Article lifecycle — status transitions (sedimentation → published)
# ═══════════════════════════════════════════════════════════════════════════════

class TestArticleLifecycle:
    """Verify article status transitions through the sedimentation pool."""

    def test_create_article_starts_as_draft(self, client, seed_user):
        """New articles start as draft; publish is explicit via POST /{id}/publish."""
        body = {
            "authors": [seed_user],
            "content": "# Test\n\nContent.",
            "format": "markdown",
            "self_review": {"originality": 4, "rigor": 3, "completeness": 4,
                            "pedagogy": 3, "impact": 3},
        }
        resp = client.post("/api/v1/articles", json=body)
        assert resp.status_code == 201
        assert resp.json()["status"] == "draft"

    def test_edit_re_enters_pool(self, client, seed_user, second_user, auth_user_id):
        """Editing an article should update sink_start and re-enter sedimentation."""
        create_body = {
            "authors": [seed_user, second_user],
            "content": "# V1\n\nFirst.",
            "format": "markdown",
            "self_review": {"originality": 3, "rigor": 3, "completeness": 3,
                            "pedagogy": 3, "impact": 3},
        }
        resp = client.post("/api/v1/articles", json=create_body)
        article_id = resp.json()["id"]

        # Edit with publish flag
        edit_body = {
            "content": "# V2\n\nUpdated.",
            "self_review": {"originality": 4, "rigor": 4, "completeness": 4,
                            "pedagogy": 4, "impact": 4},
            "publish": True,
        }
        resp2 = client.put(f"/api/v1/articles/{article_id}", json=edit_body)
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "sedimentation"

    def test_publish_transitions_to_sedimentation(self, client, seed_user):
        """Publish endpoint transitions article to sedimentation pool."""
        create_body = {
            "authors": [seed_user],
            "content": "# To Publish",
            "format": "markdown",
            "self_review": {"originality": 3, "rigor": 3, "completeness": 3,
                            "pedagogy": 3, "impact": 3},
        }
        resp = client.post("/api/v1/articles", json=create_body)
        article_id = resp.json()["id"]

        pub_resp = client.post(f"/api/v1/articles/{article_id}/publish")
        assert pub_resp.status_code == 200
        assert pub_resp.json()["status"] == "sedimentation"

    def test_publish_nonexistent_article_returns_404(self, client):
        resp = client.post("/api/v1/articles/nonexistent/publish")
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# Sink extension — extra pool time
# ═══════════════════════════════════════════════════════════════════════════════

class TestSinkExtension:
    """Verify sink extension API extends the sedimentation pool duration."""

    def test_extend_sink_increases_duration(self, client, seed_user):
        create_body = {
            "authors": [seed_user],
            "content": "# Sink Test",
            "format": "markdown",
            "self_review": {"originality": 3, "rigor": 3, "completeness": 3,
                            "pedagogy": 3, "impact": 3},
        }
        resp = client.post("/api/v1/articles", json=create_body)
        article_id = resp.json()["id"]
        original_duration = resp.json()["sink_duration_days"]

        # Extend by 10 days
        ext_resp = client.put(
            f"/api/v1/articles/{article_id}/sink-extension",
            json={"extra_days": 10})
        assert ext_resp.status_code == 200
        assert ext_resp.json()["sink_duration_days"] > original_duration

    def test_extend_sink_rejects_zero_or_negative(self, client, seed_user):
        create_body = {
            "authors": [seed_user],
            "content": "# Sink Test 2",
            "format": "markdown",
            "self_review": {"originality": 3, "rigor": 3, "completeness": 3,
                            "pedagogy": 3, "impact": 3},
        }
        resp = client.post("/api/v1/articles", json=create_body)
        article_id = resp.json()["id"]

        for bad_days in [0, -1]:
            ext_resp = client.put(
                f"/api/v1/articles/{article_id}/sink-extension",
                json={"extra_days": bad_days})
            assert ext_resp.status_code == 422, \
                f"extra_days={bad_days} should be rejected, got {ext_resp.status_code}"


# ═══════════════════════════════════════════════════════════════════════════════
# Error path coverage — fork, has-forked, rollback
# ═══════════════════════════════════════════════════════════════════════════════

class TestArticleErrorPaths:
    """Verify error responses for article sub-routes."""

    def test_fork_nonexistent_article_returns_404(self, client):
        """Forking a nonexistent article returns 404. Auth is already overridden."""
        resp = client.post("/api/v1/articles/nonexistent/fork")
        assert resp.status_code == 404

    def test_has_forked_without_auth_returns_401(self, client, seed_user):
        """has-forked endpoint requires authentication."""
        create_body = {
            "authors": [seed_user],
            "content": "# Forkable",
            "format": "markdown",
            "self_review": {"originality": 3, "rigor": 3, "completeness": 3,
                            "pedagogy": 3, "impact": 3},
        }
        resp = client.post("/api/v1/articles", json=create_body)
        article_id = resp.json()["id"]

        # Without auth override, require_user dependency returns 401
        from peerpedia_api import deps
        app = client.app
        old_req = app.dependency_overrides.get(deps.require_user)
        old_cur = app.dependency_overrides.get(deps.get_current_user)
        try:
            app.dependency_overrides.pop(deps.require_user, None)
            app.dependency_overrides.pop(deps.get_current_user, None)
            resp2 = client.get(f"/api/v1/articles/{article_id}/has-forked")
            assert resp2.status_code == 401
        finally:
            if old_req is not None:
                app.dependency_overrides[deps.require_user] = old_req
            if old_cur is not None:
                app.dependency_overrides[deps.get_current_user] = old_cur

    def test_rollback_nonexistent_article_returns_404(self, client):
        resp = client.post("/api/v1/articles/nonexistent/rollback/abc123")
        assert resp.status_code == 404

    def test_rollback_creates_revert_commit(self, client, seed_user, second_user, auth_user_id):
        """Happy path: create article with 2 commits, rollback to first, verify content restored."""
        body = {
            "authors": [seed_user, second_user],
            "self_review": {"originality": 4, "rigor": 3, "completeness": 4,
                            "pedagogy": 3, "impact": 3},
            "title": "Rollback Test",
            "content": "Original content",
            "format": "markdown",
        }
        resp = client.post("/api/v1/articles", json=body)
        assert resp.status_code == 201
        article_id = resp.json()["id"]
        first_hash = resp.json()["commit_hash"]

        # Update article — creates a 2nd commit
        update_body = {
            "content": "Updated content",
            "commit_message": "Second commit",
        }
        resp2 = client.put(f"/api/v1/articles/{article_id}", json=update_body)
        assert resp2.status_code == 200

        # Get history — should have at least 2 commits
        hist = client.get(f"/api/v1/articles/{article_id}/history")
        assert hist.status_code == 200
        commits = hist.json()["commits"]
        assert len(commits) >= 2

        # Rollback to the first commit
        resp3 = client.post(f"/api/v1/articles/{article_id}/rollback/{first_hash}")
        assert resp3.status_code == 200
        data = resp3.json()
        assert "commit_hash" in data
        assert "Rollback" in data["message"]

        # Source should be restored to original
        src = client.get(f"/api/v1/articles/{article_id}/source")
        assert src.status_code == 200
        assert src.json()["content"] == "Original content"

        # History should now have 3 commits
        hist2 = client.get(f"/api/v1/articles/{article_id}/history")
        assert hist2.status_code == 200
        assert len(hist2.json()["commits"]) >= 3


# ═══════════════════════════════════════════════════════════════════════════════
# Additional edge cases for uncovered branches
# ═══════════════════════════════════════════════════════════════════════════════

class TestArticleCreateEdgeCases:
    """Edge cases for article creation."""

    def test_create_with_empty_authors_defaults_to_current_user(self, client, seed_user):
        """Creating an article with empty authors defaults to the current user (SPEC-11)."""
        body = {
            "authors": [],
            "title": "Solo Article",
            "content": "Content",
            "format": "markdown",
            "self_review": {"originality": 3, "rigor": 3, "completeness": 3,
                           "pedagogy": 3, "impact": 3},
        }
        resp = client.post("/api/v1/articles", json=body)
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["authors"]) >= 1, f"Expected at least 1 author, got {data['authors']}"


class TestArticleUpdateEdgeCases:
    """Edge cases for article updates."""

    def test_update_body_fields(self, client, seed_user, second_user, auth_user_id):
        """Update title, abstract, keywords, and categories."""
        body = {
            "authors": [seed_user, second_user],
            "title": "Original Title",
            "content": "Content",
            "format": "markdown",
            "self_review": {"originality": 3, "rigor": 3, "completeness": 3,
                           "pedagogy": 3, "impact": 3},
        }
        resp = client.post("/api/v1/articles", json=body)
        article_id = resp.json()["id"]

        update = {
            "title": "Updated Title",
            "abstract": "Updated abstract text.",
            "keywords": ["keyword1", "keyword2"],
            "categories": ["category1", "category2"],
        }
        resp2 = client.put(f"/api/v1/articles/{article_id}", json=update)
        assert resp2.status_code == 200
        data = resp2.json()
        assert data["title"] == "Updated Title"


class TestHasForked:
    """GET /articles/{id}/has-forked — check if user forked an article."""

    def test_has_forked_returns_false(self, client, seed_user):
        """Returns false when user hasn't forked the article."""
        body = {
            "authors": [seed_user],
            "title": "Unforked",
            "content": "Content",
            "format": "markdown",
            "self_review": {"originality": 3, "rigor": 3, "completeness": 3,
                           "pedagogy": 3, "impact": 3},
        }
        resp = client.post("/api/v1/articles", json=body)
        article_id = resp.json()["id"]

        check = client.get(f"/api/v1/articles/{article_id}/has-forked")
        assert check.status_code == 200
        assert check.json()["has_forked"] is False

    def test_has_forked_returns_true(self, client, seed_user, db_engine):
        """Returns true after user forks a published article."""
        body = {
            "authors": [seed_user],
            "title": "WillBeForked",
            "content": "Content",
            "format": "markdown",
            "self_review": {"originality": 3, "rigor": 3, "completeness": 3,
                           "pedagogy": 3, "impact": 3},
        }
        resp = client.post("/api/v1/articles", json=body)
        article_id = resp.json()["id"]

        # Must be published to be forkable
        s = get_session(db_engine)
        a = s.get(Article, article_id)
        a.status = "published"
        s.commit()
        s.close()

        # Fork it
        fork_resp = client.post(f"/api/v1/articles/{article_id}/fork")
        assert fork_resp.status_code == 201

        # Now has_forked should return true
        check = client.get(f"/api/v1/articles/{article_id}/has-forked")
        assert check.status_code == 200
        assert check.json()["has_forked"] is True

    def test_fork_nonexistent_article_returns_404(self, client):
        """Forking a non-existent article returns 404."""
        resp = client.post("/api/v1/articles/nonexistent-id/fork")
        assert resp.status_code == 404


class TestDiffEdgeCases:
    """Edge cases for git diff endpoints."""

    def test_diff_invalid_hashes_returns_400(self, client, seed_user):
        """Diff with non-existent commit hashes returns 400."""
        body = {
            "authors": [seed_user],
            "title": "Diff Test",
            "content": "Content for diff test.",
            "format": "markdown",
            "self_review": {"originality": 3, "rigor": 3, "completeness": 3,
                           "pedagogy": 3, "impact": 3},
        }
        resp = client.post("/api/v1/articles", json=body)
        article_id = resp.json()["id"]
        # Try diff with invalid hashes
        diff_resp = client.get(
            f"/api/v1/articles/{article_id}/diff/badhash1/badhash2"
        )
        assert diff_resp.status_code == 400


class TestExtendSinkEdgeCase:
    """More extend_sink edge cases."""

    def test_extend_sink_nonexistent_article_returns_404(self, client):
        """Extending sink for a non-existent article returns 404."""
        resp = client.put(
            "/api/v1/articles/nonexistent-id/sink-extension",
            json={"extra_days": 5},
        )
        assert resp.status_code == 404


class TestArticleSource:
    """Source file retrieval edge cases."""

    def test_source_typst(self, client, seed_user):
        """Getting Typst source returns correct format."""
        body = {
            "authors": [seed_user],
            "title": "Typst Article",
            "content": "= Hello\nWorld",
            "format": "typst",
            "self_review": {"originality": 3, "rigor": 3, "completeness": 3,
                           "pedagogy": 3, "impact": 3},
        }
        resp = client.post("/api/v1/articles", json=body)
        article_id = resp.json()["id"]

        src = client.get(f"/api/v1/articles/{article_id}/source")
        assert src.status_code == 200
        assert src.json()["format"] == "typst"

    def test_source_not_found_returns_404(self, client):
        """Missing source returns 404."""
        resp = client.get("/api/v1/articles/nonexistent-id/source")
        assert resp.status_code == 404


class TestUpdatePublishWithContributions:
    """Update + publish article with contributions to cover all branches."""

    def test_update_publish_with_contributions(self, client, seed_user, second_user, auth_user_id):
        """Updating and publishing with self_review + contributions."""
        body = {
            "authors": [seed_user, second_user],
            "title": "Contrib Test",
            "content": "Initial content.",
            "format": "markdown",
            "self_review": {"originality": 3, "rigor": 3, "completeness": 3,
                           "pedagogy": 3, "impact": 3},
        }
        resp = client.post("/api/v1/articles", json=body)
        article_id = resp.json()["id"]

        update = {
            "content": "Updated content with contributions.",
            "publish": True,
            "self_review": {"originality": 4, "rigor": 4, "completeness": 4,
                           "pedagogy": 4, "impact": 4},
            "contributions": {
                seed_user: {"originality": 1.0, "rigor": 1.0, "completeness": 1.0,
                            "pedagogy": 1.0, "impact": 1.0},
            },
        }
        resp2 = client.put(f"/api/v1/articles/{article_id}", json=update)
        assert resp2.status_code == 200


class TestDownloadPdf:
    """PDF download edge cases."""

    def test_download_pdf_not_found_returns_404(self, client):
        """Download PDF for non-existent article returns 404."""
        resp = client.get("/api/v1/articles/nonexistent-id/download/pdf")
        assert resp.status_code == 404

    def test_download_source_not_found(self, client):
        """Download source for non-existent article returns 404."""
        resp = client.get("/api/v1/articles/nonexistent-id/download/source")
        assert resp.status_code == 404


class TestArticleNotFound:
    """404 responses for various article endpoints."""

    def test_get_nonexistent_article_source(self, client):
        resp = client.get("/api/v1/articles/nonexistent-id/source")
        assert resp.status_code == 404

    def test_download_nonexistent_article_source(self, client):
        resp = client.get("/api/v1/articles/nonexistent-id/download/source")
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# Bundle Sync Endpoints (Phase B — git-first network model)
# ═══════════════════════════════════════════════════════════════════════════════


class TestBundleSyncEndpoints:
    """Tests for GET /head, GET /bundle?since=, POST /sync."""

    @pytest.fixture
    def article_with_repo(self, client, auth_user_id, db_engine):
        """Create an article with a git repo and return (article_id, head_hash).

        Uses auth_user_id so the article is owned by the client's implicit auth user.
        """
        from peerpedia_core.storage.db.engine import get_session
        from peerpedia_core.storage.git_backend import (
            DEFAULT_ARTICLES_DIR,
            commit_article,
        )

        # Create article via API — auth_user_id matches the client's require_user override
        body = {
            "authors": [auth_user_id],
            "content": "# Test Bundle\n\nInitial content.",
            "format": "markdown",
            "self_review": {"originality": 4, "rigor": 3, "completeness": 4,
                            "pedagogy": 3, "impact": 3},
        }
        resp = client.post("/api/v1/articles", json=body)
        assert resp.status_code == 201
        article_id = resp.json()["id"]

        rp = DEFAULT_ARTICLES_DIR / article_id
        assert (rp / ".git").is_dir()

        # Make a second commit so we have something to bundle
        (rp / "article.md").write_text("# Test Bundle\n\nUpdated content.")
        h2 = commit_article(rp, "second commit", "Author", f"{auth_user_id}@peerpedia")
        assert h2

        # Rebuild authors in DB so get_author_ids works for auth checks
        s = get_session(db_engine)
        from peerpedia_core.storage.db.crud_article import rebuild_article_authors
        rebuild_article_authors(s, article_id, {auth_user_id})
        s.close()

        return article_id, h2

    # ── GET /{id}/head ──────────────────────────────────────────────────

    def test_get_head_returns_hash(self, client, article_with_repo):
        """GET /head returns the current HEAD commit hash."""
        article_id, head_hash = article_with_repo
        resp = client.get(f"/api/v1/articles/{article_id}/head")
        assert resp.status_code == 200
        assert resp.json()["hash"] == head_hash

    def test_get_head_nonexistent_article(self, client):
        """GET /head for non-existent article returns 404."""
        resp = client.get("/api/v1/articles/nonexistent/head")
        assert resp.status_code == 404

    def test_get_head_no_repo(self, client, seed_user, db_engine):
        """GET /head for article with no git repo returns 404."""
        from peerpedia_core.storage.db.engine import get_session
        from peerpedia_core.storage.db.models import Article, ArticleAuthor

        s = get_session(db_engine)
        a = Article(status="draft")
        s.add(a)
        s.flush()
        s.add(ArticleAuthor(article_id=a.id, author_id=seed_user, position=0))
        s.commit()
        aid = a.id
        s.close()

        resp = client.get(f"/api/v1/articles/{aid}/head")
        assert resp.status_code == 404

    def test_get_head_empty_repo(self, client, auth_user_id, db_engine):
        """GET /head for article with empty git repo (no commits) returns 404."""
        from peerpedia_core.storage.db.engine import get_session
        from peerpedia_core.storage.db.models import Article, ArticleAuthor
        from peerpedia_core.storage.git_backend import init_article_repo

        s = get_session(db_engine)
        a = Article(status="draft")
        s.add(a)
        s.flush()
        s.add(ArticleAuthor(article_id=a.id, author_id=auth_user_id, position=0))
        s.commit()
        aid = a.id
        s.close()

        init_article_repo(aid)  # git init only, no commits
        resp = client.get(f"/api/v1/articles/{aid}/head")
        assert resp.status_code == 404

    # ── GET /{id}/bundle?since= ─────────────────────────────────────────

    def test_get_bundle_returns_octet_stream(self, client, article_with_repo):
        """GET /bundle returns incremental bundle as octet-stream."""
        import git as gitmod
        from peerpedia_core.storage.git_backend import DEFAULT_ARTICLES_DIR

        article_id, _ = article_with_repo
        rp = DEFAULT_ARTICLES_DIR / article_id
        repo = gitmod.Repo(rp)

        # Get the first commit hash (since point)
        commits = list(repo.iter_commits())
        first_hash = commits[-1].hexsha  # oldest commit

        resp = client.get(f"/api/v1/articles/{article_id}/bundle?since={first_hash}")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/octet-stream"
        assert len(resp.content) > 0

    def test_get_bundle_nonexistent_article(self, client):
        """GET /bundle for non-existent article returns 404."""
        resp = client.get("/api/v1/articles/nonexistent/bundle?since=0000000000000000000000000000000000000000")
        assert resp.status_code == 404

    def test_get_bundle_bad_since_hash(self, client, article_with_repo):
        """GET /bundle with non-ancestor since returns 422."""
        article_id, _ = article_with_repo
        # A hash that doesn't exist in the repo
        resp = client.get(f"/api/v1/articles/{article_id}/bundle?since={'0' * 40}")
        assert resp.status_code == 422

    def test_get_bundle_empty_repo(self, client, auth_user_id, db_engine):
        """GET /bundle for article with empty repo (no commits) returns 404."""
        from peerpedia_core.storage.db.engine import get_session
        from peerpedia_core.storage.db.models import Article, ArticleAuthor
        from peerpedia_core.storage.git_backend import init_article_repo

        s = get_session(db_engine)
        a = Article(status="draft")
        s.add(a)
        s.flush()
        s.add(ArticleAuthor(article_id=a.id, author_id=auth_user_id, position=0))
        s.commit()
        aid = a.id
        s.close()

        init_article_repo(aid)
        resp = client.get(f"/api/v1/articles/{aid}/bundle?since={'0' * 40}")
        assert resp.status_code == 404

    def test_get_bundle_requires_auth(self, client, article_with_repo):
        """GET /bundle returns 401 without authentication."""
        from peerpedia_api import deps

        article_id, _ = article_with_repo
        app = client.app
        old_req = app.dependency_overrides.get(deps.require_user)
        old_cur = app.dependency_overrides.get(deps.get_current_user)
        try:
            app.dependency_overrides.pop(deps.require_user, None)
            app.dependency_overrides.pop(deps.get_current_user, None)
            resp = client.get(f"/api/v1/articles/{article_id}/bundle?since={'0' * 40}")
            assert resp.status_code == 401
        finally:
            if old_req is not None:
                app.dependency_overrides[deps.require_user] = old_req
            if old_cur is not None:
                app.dependency_overrides[deps.get_current_user] = old_cur

    # ── POST /{id}/sync ─────────────────────────────────────────────────

    def test_sync_applies_bundle_and_returns_head(self, client, article_with_repo):
        """POST /sync applies an incremental bundle and returns new HEAD."""
        from peerpedia_core.storage.git_backend import (
            DEFAULT_ARTICLES_DIR,
            commit_article,
            create_bundle,
        )

        article_id, current_head = article_with_repo
        rp = DEFAULT_ARTICLES_DIR / article_id

        # Create a new commit on the repo
        (rp / "article.md").write_text("# Test Bundle\n\nThird content.")
        h3 = commit_article(rp, "third commit", "Author", "author@peerpedia.com")
        assert h3
        assert h3 != current_head

        # Create incremental bundle from current_head to h3
        bundle_bytes = create_bundle(rp, current_head)
        assert len(bundle_bytes) > 0

        # POST the bundle
        resp = client.post(
            f"/api/v1/articles/{article_id}/sync",
            files={"file": ("bundle", bundle_bytes, "application/octet-stream")},
        )
        assert resp.status_code == 200
        assert resp.json()["head"] == h3

    def test_sync_nonexistent_article(self, client):
        """POST /sync for non-existent article returns 404."""
        resp = client.post(
            "/api/v1/articles/nonexistent/sync",
            files={"file": ("bundle", b"garbage", "application/octet-stream")},
        )
        assert resp.status_code == 404

    def test_sync_without_repo(self, client, auth_user_id, db_engine):
        """POST /sync for article without git repo returns 404."""
        from peerpedia_core.storage.db.engine import get_session
        from peerpedia_core.storage.db.models import Article, ArticleAuthor

        s = get_session(db_engine)
        a = Article(status="draft")
        s.add(a)
        s.flush()
        s.add(ArticleAuthor(article_id=a.id, author_id=auth_user_id, position=0))
        s.commit()
        aid = a.id
        s.close()

        resp = client.post(
            f"/api/v1/articles/{aid}/sync",
            files={"file": ("bundle", b"bundle", "application/octet-stream")},
        )
        assert resp.status_code == 404

    def test_sync_invalid_bundle(self, client, article_with_repo):
        """POST /sync with corrupt bundle returns 422."""
        article_id, _ = article_with_repo
        resp = client.post(
            f"/api/v1/articles/{article_id}/sync",
            files={"file": ("bundle", b"not a valid git bundle", "application/octet-stream")},
        )
        assert resp.status_code == 422

    def test_sync_empty_bundle_rejected(self, client, article_with_repo):
        """POST /sync with empty bundle bytes returns 422 (invalid bundle)."""
        article_id, _ = article_with_repo
        resp = client.post(
            f"/api/v1/articles/{article_id}/sync",
            files={"file": ("bundle", b"", "application/octet-stream")},
        )
        assert resp.status_code == 422

    def test_sync_requires_auth(self, client, article_with_repo):
        """POST /sync returns 401 without authentication."""
        from peerpedia_api import deps

        article_id, _ = article_with_repo
        app = client.app
        old_req = app.dependency_overrides.get(deps.require_user)
        old_cur = app.dependency_overrides.get(deps.get_current_user)
        try:
            app.dependency_overrides.pop(deps.require_user, None)
            app.dependency_overrides.pop(deps.get_current_user, None)
            resp = client.post(
                f"/api/v1/articles/{article_id}/sync",
                files={"file": ("bundle", b"x", "application/octet-stream")},
            )
            assert resp.status_code == 401
        finally:
            if old_req is not None:
                app.dependency_overrides[deps.require_user] = old_req
            if old_cur is not None:
                app.dependency_overrides[deps.get_current_user] = old_cur

    def test_sync_non_author_forbidden(self, client, article_with_repo, db_engine):
        """POST /sync from non-author returns 403."""
        from peerpedia_api import deps
        from peerpedia_core.storage.db.engine import get_session
        from peerpedia_core.storage.db.models import User

        article_id, _ = article_with_repo

        # Create a different user who is NOT an author
        s = get_session(db_engine)
        other = User(username="not_an_author", password_hash="",
                     name="Other", anonymous_name="anon_other", affiliation="U")
        s.add(other)
        s.commit()
        other_obj = s.get(User, other.id)
        s.close()

        app = client.app
        old = app.dependency_overrides.get(deps.require_user)
        try:
            app.dependency_overrides[deps.require_user] = lambda: other_obj
            resp = client.post(
                f"/api/v1/articles/{article_id}/sync",
                files={"file": ("bundle", b"x", "application/octet-stream")},
            )
            assert resp.status_code == 403
        finally:
            if old is not None:
                app.dependency_overrides[deps.require_user] = old

    def test_get_bundle_no_repo(self, client, auth_user_id, db_engine):
        """GET /bundle for article without git repo returns 404."""
        from peerpedia_core.storage.db.engine import get_session
        from peerpedia_core.storage.db.models import Article, ArticleAuthor

        s = get_session(db_engine)
        a = Article(status="draft")
        s.add(a)
        s.flush()
        s.add(ArticleAuthor(article_id=a.id, author_id=auth_user_id, position=0))
        s.commit()
        aid = a.id
        s.close()

        resp = client.get(f"/api/v1/articles/{aid}/bundle?since={'0' * 40}")
        assert resp.status_code == 404

    def test_sync_divergent_history_returns_409(self, client, article_with_repo):
        """POST /sync with divergent history returns 409 with server_head."""
        import git as gitmod
        from peerpedia_core.storage.git_backend import (
            DEFAULT_ARTICLES_DIR,
            commit_article,
            init_article_repo,
        )

        article_id, _ = article_with_repo
        rp = DEFAULT_ARTICLES_DIR / article_id

        # Create a divergent commit directly on the server repo
        # (simulates a review commit from another user)
        (rp / "reviews").mkdir(exist_ok=True)
        (rp / "reviews/review.md").write_text("server-side change")
        commit_article(rp, "server commit", "Server", "server@peerpedia.com")
        server_head = gitmod.Repo(rp).head.commit.hexsha

        # Create a bundle from a completely different repo with divergent history
        import tempfile
        from pathlib import Path

        tmp = tempfile.mkdtemp()
        try:
            other_rp = init_article_repo("other", base_dir=Path(tmp))
            (other_rp / "article.md").write_text("divergent content")
            commit_article(other_rp, "other commit", "Other", "other@test.com")
            other_repo = gitmod.Repo(other_rp)
            with tempfile.NamedTemporaryFile(suffix=".bundle", delete=False) as f:
                other_repo.git.bundle("create", f.name, "--all")
                bundle_bytes = Path(f.name).read_bytes()
            Path(f.name).unlink(missing_ok=True)

            resp = client.post(
                f"/api/v1/articles/{article_id}/sync",
                files={"file": ("bundle", bundle_bytes, "application/octet-stream")},
            )
            assert resp.status_code == 409
            detail = resp.json()["detail"]
            assert detail["server_head"] == server_head
            assert "Fast-forward merge failed" in detail["error"]
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════════════
# _refresh_db_from_git — DB cache sync from article.json
# ═══════════════════════════════════════════════════════════════════════════════


class TestRefreshDbFromGit:
    """Test the _refresh_db_from_git helper used by bundle sync paths."""

    def test_syncs_title_abstract_keywords(self, client, auth_user_id, db_engine):
        """_refresh_db_from_git copies title/abstract/keywords from article.json to DB."""
        import json

        from peerpedia_api.routes.articles import _refresh_db_from_git
        from peerpedia_core.storage.db.engine import get_session
        from peerpedia_core.storage.db.models import Article, ArticleAuthor
        from peerpedia_core.storage.git_backend import (
            commit_article,
            init_article_repo,
        )

        # Create article in DB with repo
        s = get_session(db_engine)
        a = Article(title="Old Title", abstract="Old Abstract",
                    keywords=["old"], categories=["old-cat"], status="draft")
        s.add(a)
        s.flush()
        s.add(ArticleAuthor(article_id=a.id, author_id=auth_user_id, position=0))
        s.commit()
        aid = a.id
        s.close()

        rp = init_article_repo(aid)
        (rp / "article.md").write_text("# Content")
        commit_article(rp, "init", "A", f"{auth_user_id}@peerpedia")

        # Write article.json with new values
        meta = {
            "title": "New Title",
            "abstract": "New Abstract",
            "keywords": ["new", "kw"],
            "categories": ["new-cat"],
            "status": "draft",
        }
        (rp / "article.json").write_text(json.dumps(meta))

        # Sync
        s2 = get_session(db_engine)
        _refresh_db_from_git(aid, rp, s2)
        s2.close()

        # Verify DB was updated
        s3 = get_session(db_engine)
        from peerpedia_core.storage.db.crud_article import get_article
        updated = get_article(s3, aid)
        assert updated.title == "New Title"
        assert updated.abstract == "New Abstract"
        assert updated.keywords == ["new", "kw"]
        assert updated.categories == ["new-cat"]
        s3.close()

    def test_clears_keywords_to_empty(self, client, auth_user_id, db_engine):
        """_refresh_db_from_git can clear keywords to empty list."""
        import json

        from peerpedia_api.routes.articles import _refresh_db_from_git
        from peerpedia_core.storage.db.engine import get_session
        from peerpedia_core.storage.db.models import Article, ArticleAuthor
        from peerpedia_core.storage.git_backend import (
            commit_article,
            init_article_repo,
        )

        s = get_session(db_engine)
        a = Article(keywords=["old", "kw"], status="draft")
        s.add(a)
        s.flush()
        s.add(ArticleAuthor(article_id=a.id, author_id=auth_user_id, position=0))
        s.commit()
        aid = a.id
        s.close()

        rp = init_article_repo(aid)
        (rp / "article.md").write_text("# C")
        commit_article(rp, "init", "A", f"{auth_user_id}@peerpedia")
        (rp / "article.json").write_text(json.dumps({"keywords": [], "status": "draft"}))

        s2 = get_session(db_engine)
        _refresh_db_from_git(aid, rp, s2)
        s2.close()

        s3 = get_session(db_engine)
        from peerpedia_core.storage.db.crud_article import get_article
        assert get_article(s3, aid).keywords == []
        s3.close()

    def test_no_article_json_is_noop(self, client, auth_user_id, db_engine):
        """_refresh_db_from_git returns early when article.json doesn't exist."""
        from peerpedia_api.routes.articles import _refresh_db_from_git
        from peerpedia_core.storage.db.engine import get_session
        from peerpedia_core.storage.db.models import Article, ArticleAuthor
        from peerpedia_core.storage.git_backend import commit_article, init_article_repo

        s = get_session(db_engine)
        a = Article(status="draft")
        s.add(a)
        s.flush()
        s.add(ArticleAuthor(article_id=a.id, author_id=auth_user_id, position=0))
        s.commit()
        aid = a.id
        s.close()

        rp = init_article_repo(aid)
        (rp / "article.md").write_text("# C")
        commit_article(rp, "init", "A", f"{auth_user_id}@peerpedia")

        s2 = get_session(db_engine)
        _refresh_db_from_git(aid, rp, s2)  # no article.json → no-op
        s2.close()

    def test_no_db_session_skips_sync(self, client, auth_user_id, db_engine):
        """_refresh_db_from_git with db=None returns early."""
        import json

        from peerpedia_api.routes.articles import _refresh_db_from_git
        from peerpedia_core.storage.db.engine import get_session
        from peerpedia_core.storage.db.models import Article, ArticleAuthor
        from peerpedia_core.storage.git_backend import commit_article, init_article_repo

        s = get_session(db_engine)
        a = Article(status="draft")
        s.add(a)
        s.flush()
        s.add(ArticleAuthor(article_id=a.id, author_id=auth_user_id, position=0))
        s.commit()
        aid = a.id
        s.close()

        rp = init_article_repo(aid)
        (rp / "article.md").write_text("# C")
        commit_article(rp, "init", "A", f"{auth_user_id}@peerpedia")
        (rp / "article.json").write_text(json.dumps({"title": "X", "status": "draft"}))

        # db=None → should not raise
        _refresh_db_from_git(aid, rp, None)

    def test_bad_json_logs_warning(self, client, auth_user_id, db_engine, caplog):
        """_refresh_db_from_git logs a warning for unparseable article.json."""
        from peerpedia_api.routes.articles import _refresh_db_from_git
        from peerpedia_core.storage.db.engine import get_session
        from peerpedia_core.storage.db.models import Article, ArticleAuthor
        from peerpedia_core.storage.git_backend import commit_article, init_article_repo

        s = get_session(db_engine)
        a = Article(status="draft")
        s.add(a)
        s.flush()
        s.add(ArticleAuthor(article_id=a.id, author_id=auth_user_id, position=0))
        s.commit()
        aid = a.id
        s.close()

        rp = init_article_repo(aid)
        (rp / "article.md").write_text("# C")
        commit_article(rp, "init", "A", f"{auth_user_id}@peerpedia")
        (rp / "article.json").write_text("not valid json {{{")

        s2 = get_session(db_engine)
        _refresh_db_from_git(aid, rp, s2)
        s2.close()

        assert any("Failed to parse article.json" in r.message for r in caplog.records)

    def test_status_pool_triggers_sink(self, client, auth_user_id, db_engine):
        """_refresh_db_from_git triggers sink_start when status changes to pool."""
        import json

        from peerpedia_api.routes.articles import _refresh_db_from_git
        from peerpedia_core.storage.db.engine import get_session
        from peerpedia_core.storage.db.models import Article, ArticleAuthor
        from peerpedia_core.storage.git_backend import commit_article, init_article_repo

        s = get_session(db_engine)
        a = Article(status="draft")
        s.add(a)
        s.flush()
        s.add(ArticleAuthor(article_id=a.id, author_id=auth_user_id, position=0))
        s.commit()
        aid = a.id
        s.close()

        rp = init_article_repo(aid)
        (rp / "article.md").write_text("# C")
        commit_article(rp, "init", "A", f"{auth_user_id}@peerpedia")
        (rp / "article.json").write_text(json.dumps({
            "title": "Publishing", "status": "sedimentation",
            "self_review": {"originality": 5, "rigor": 4, "completeness": 4,
                            "pedagogy": 3, "impact": 4},
        }))

        s2 = get_session(db_engine)
        _refresh_db_from_git(aid, rp, s2)
        s2.close()

        s3 = get_session(db_engine)
        from peerpedia_core.storage.db.crud_article import get_article
        updated = get_article(s3, aid)
        assert updated.status == "sedimentation"  # POOL_STATUS constant
        assert updated.sink_start is not None  # sink was triggered
        assert updated.sink_duration_days > 0  # sink duration was set
        s3.close()

    def test_refresh_db_from_git_sets_sink_on_sedimentation(self, db_engine):
        """REGRESSION: status='sedimentation' in article.json triggers set_sink_start.

        Verifies the sink trigger at articles.py line 738 uses the POOL_STATUS
        constant.  Without this, the sink timer never starts and auto-publish
        silently fails.
        """
        import json

        from peerpedia_api.routes.articles import _refresh_db_from_git
        from peerpedia_core.storage.db.engine import get_session
        from peerpedia_core.storage.db.models import Article, ArticleAuthor, User
        from peerpedia_core.storage.git_backend import commit_article, init_article_repo

        s = get_session(db_engine)
        u = User(username="sink_test_user", password_hash="", name="T", anonymous_name="t")
        s.add(u)
        s.commit()
        uid = u.id

        a = Article(status="draft")
        s.add(a)
        s.flush()
        s.add(ArticleAuthor(article_id=a.id, author_id=uid, position=0))
        s.commit()
        aid = a.id
        s.close()

        rp = init_article_repo(aid)
        (rp / "article.md").write_text("# Sink Trigger Test")
        commit_article(rp, "init", "T", f"{uid}@peerpedia")
        # Write the canonical status — must trigger set_sink_start
        (rp / "article.json").write_text(json.dumps({"status": "sedimentation"}))

        s2 = get_session(db_engine)
        _refresh_db_from_git(aid, rp, s2)
        s2.close()

        s3 = get_session(db_engine)
        from peerpedia_core.storage.db.crud_article import get_article
        updated = get_article(s3, aid)
        assert updated.status == "sedimentation"
        assert updated.sink_start is not None, "sink_start must be set when status is sedimentation"
        assert updated.sink_duration_days > 0, "sink_duration_days must be > 0"
        s3.close()

    def test_create_then_publish_sets_sink_start(self, client, auth_user_id):
        """REGRESSION: Bug 1 — publish flow sets sink_start and returns correct status.

        Create → publish → GET: article must be 'sedimentation' with sink_start set.
        Reproduces the 'article not found after publish' and 'sink timer never starts' bugs.
        """
        # Step 1: Create draft
        create_body = {
            "authors": [auth_user_id],
            "title": "Publish Flow Test",
            "content": "# Publish Test\n\nContent.",
            "format": "markdown",
        }
        resp = client.post("/api/v1/articles", json=create_body)
        assert resp.status_code == 201, f"Create failed: {resp.json()}"
        article_id = resp.json()["id"]
        assert resp.json()["status"] == "draft"

        # Step 2: Publish via PUT with self_review
        publish_body = {
            "content": "# Publish Test\n\nContent. (published)",
            "publish": True,
            "self_review": {"originality": 4, "rigor": 3, "completeness": 4,
                            "pedagogy": 3, "impact": 3},
        }
        resp2 = client.put(f"/api/v1/articles/{article_id}", json=publish_body)
        assert resp2.status_code == 200, f"Publish failed: {resp2.json()}"
        data2 = resp2.json()
        assert data2["status"] == "sedimentation"
        assert data2["sink_eta"] is not None, "sink_eta must be set after publish"
        assert data2["days_remaining"] is not None
        assert data2["sink_duration_days"] is not None

        # Step 3: GET — article must be found (not 404) and show correct status
        resp3 = client.get(f"/api/v1/articles/{article_id}")
        assert resp3.status_code == 200, f"GET after publish failed: {resp3.json()}"
        assert resp3.json()["status"] == "sedimentation"
        assert resp3.json()["sink_eta"] is not None

    def test_list_articles_by_author(self, client, db_engine, auth_user_id):
        """REGRESSION: Bug 2 — articles are returned when filtering by author_id.

        Verifies that get_articles_by_author / list_articles with author_id
        correctly joins ArticleAuthor and returns articles for the author.
        """
        from peerpedia_core.storage.db.engine import get_session
        from peerpedia_core.storage.db.models import Article, ArticleAuthor

        # Create an article by the auth user
        create_body = {
            "authors": [auth_user_id],
            "title": "Author Filter Test",
            "content": "# Author Filter\n\nTesting.",
            "format": "markdown",
        }
        resp = client.post("/api/v1/articles", json=create_body)
        assert resp.status_code == 201, f"Create failed: {resp.json()}"
        article_id = resp.json()["id"]

        # Query by author_id
        resp2 = client.get(f"/api/v1/articles?author_id={auth_user_id}")
        assert resp2.status_code == 200
        articles = resp2.json()["articles"]
        assert len(articles) >= 1, f"Expected ≥1 article for author {auth_user_id}"
        article_ids = [a["id"] for a in articles]
        assert article_id in article_ids, f"Article {article_id} not in author-filtered results"


class TestAuthorArticleLink:
    """Verify the article-author link via article_authors join table."""

    def test_created_article_has_authors(self, client, auth_user_id):
        """REGRESSION: article created via POST returns non-empty authors list."""
        body = {
            "authors": [auth_user_id],
            "title": "Author Link Test",
            "content": "# Author Link\n\nTesting.",
            "format": "markdown",
        }
        resp = client.post("/api/v1/articles", json=body)
        assert resp.status_code == 201, f"Create failed: {resp.json()}"
        data = resp.json()
        assert len(data["authors"]) >= 1, f"Expected ≥1 author, got {len(data['authors'])}"
        assert data["authors"][0]["id"] == auth_user_id

    def test_author_filter_returns_article(self, client, auth_user_id):
        """REGRESSION: articles appear when filtering by author_id."""
        body = {
            "authors": [auth_user_id],
            "title": "Filter Test",
            "content": "# Filter\n\nTesting.",
            "format": "markdown",
        }
        resp = client.post("/api/v1/articles", json=body)
        assert resp.status_code == 201
        article_id = resp.json()["id"]

        resp2 = client.get(f"/api/v1/articles?author_id={auth_user_id}")
        assert resp2.status_code == 200
        ids = [a["id"] for a in resp2.json()["articles"]]
        assert article_id in ids, f"Article {article_id} not found in author filter"

    def test_article_detail_includes_author_names(self, client, auth_user_id):
        """REGRESSION: article detail response includes resolved author names."""
        body = {
            "authors": [auth_user_id],
            "title": "Author Name Test",
            "content": "# Name Test",
            "format": "markdown",
        }
        resp = client.post("/api/v1/articles", json=body)
        assert resp.status_code == 201
        article_id = resp.json()["id"]

        resp2 = client.get(f"/api/v1/articles/{article_id}")
        assert resp2.status_code == 200
        authors = resp2.json()["authors"]
        assert len(authors) >= 1
        # Author name should be resolved, not "unknown"
        assert authors[0]["name"] != "unknown", f"Author name is 'unknown': {authors[0]}"
        assert len(authors[0]["name"]) > 0

    def test_sync_auto_create_populates_authors(self, db_engine):
        """REGRESSION: first-time bundle sync creates DB record and populates authors.

        Verifies the sync auto-create path (articles.py:831) passes authors=[]
        and then rebuild_article_authors from git history.
        """
        import json
        import uuid as _uuid
        from peerpedia_core.storage.db.engine import get_session
        from peerpedia_core.storage.db.models import User
        from peerpedia_core.storage.git_backend import commit_article, init_article_repo

        s = get_session(db_engine)
        # Create a user whose UUID matches the git commit email
        u = User(username="sync_test_author", password_hash="", name="SyncAuthor", anonymous_name="sa")
        s.add(u)
        s.commit()
        uid = u.id
        s.close()

        # Create a git repo (simulating Tauri client) — but NO DB article record yet
        aid = str(_uuid.uuid4())
        rp = init_article_repo(aid)
        (rp / "article.md").write_text("# Sync Test")
        commit_article(rp, "init", "SyncAuthor", f"{uid}@peerpedia")
        (rp / "article.json").write_text(json.dumps({"status": "draft", "title": "Sync Article"}))

        # Simulate sync auto-create: create article with empty authors, then rebuild
        from peerpedia_core.storage.db.crud_article import (
            create_article,
            get_authors_from_git,
            get_author_ids,
            rebuild_article_authors,
        )
        s2 = get_session(db_engine)
        a = create_article(s2, authors=[], id=aid, status="draft")
        s2.commit()

        # Rebuild authors from git — this is what the sync endpoint does
        git_authors = get_authors_from_git(rp, s2)
        rebuild_article_authors(s2, aid, git_authors)

        # Verify authors are populated
        s3 = get_session(db_engine)
        author_ids = get_author_ids(s3, aid)
        assert uid in author_ids, f"Author {uid} should be in {author_ids} after rebuild from git"
        s3.close()

    def test_delete_succeeds_for_author(self, client, auth_user_id):
        """REGRESSION: article author can delete their own article (returns 204)."""
        body = {
            "authors": [auth_user_id],
            "title": "Delete Me",
            "content": "# Delete Test",
            "format": "markdown",
        }
        resp = client.post("/api/v1/articles", json=body)
        assert resp.status_code == 201
        article_id = resp.json()["id"]

        # Delete should succeed (the client fixture's require_user is the same auth_user)
        resp2 = client.delete(f"/api/v1/articles/{article_id}")
        assert resp2.status_code == 204, f"Delete failed: {resp2.status_code} {resp2.text}"

        # Verify article is gone
        resp3 = client.get(f"/api/v1/articles/{article_id}")
        assert resp3.status_code == 404

    def test_sync_rebuilds_authors_from_git(self, db_engine):
        """REGRESSION: normal sync path rebuilds article_authors from git history.

        When a bundle sync brings new co-author commits, _refresh_db_from_git alone
        doesn't update article_authors.  The fix adds rebuild_article_authors after
        _refresh_db_from_git on the normal (non-auto-create) sync path.
        """
        import json
        import uuid as _uuid
        from peerpedia_core.storage.db.engine import get_session
        from peerpedia_core.storage.db.models import Article, ArticleAuthor, User
        from peerpedia_core.storage.git_backend import commit_article, init_article_repo
        from peerpedia_core.storage.db.crud_article import (
            create_article,
            get_authors_from_git,
            get_author_ids,
            rebuild_article_authors,
        )

        s = get_session(db_engine)
        # Two authors
        u1 = User(username="sync_auth1", password_hash="", name="A1", anonymous_name="a1")
        u2 = User(username="sync_auth2", password_hash="", name="A2", anonymous_name="a2")
        s.add_all([u1, u2])
        s.commit()
        uid1, uid2 = u1.id, u2.id
        s.close()

        # Article with only u1 as author initially
        aid = str(_uuid.uuid4())
        rp = init_article_repo(aid)
        (rp / "article.md").write_text("# Two Authors")
        commit_article(rp, "first", "A1", f"{uid1}@peerpedia")
        (rp / "article.json").write_text(json.dumps({"status": "draft"}))

        s2 = get_session(db_engine)
        a = create_article(s2, authors=[uid1], id=aid, status="draft")
        s2.commit()

        # u2 adds a co-author commit → simulates what bundle sync brings
        (rp / "article.md").write_text("# Two Authors — co-authored")
        commit_article(rp, "co-author", "A2", f"{uid2}@peerpedia")

        # Normal sync path: refresh from git + rebuild authors
        from peerpedia_api.routes.articles import _refresh_db_from_git
        s3 = get_session(db_engine)
        _refresh_db_from_git(aid, rp, s3)
        git_authors = get_authors_from_git(rp, s3)
        if git_authors:
            rebuild_article_authors(s3, aid, git_authors)
        s3.close()

        # Verify BOTH authors are in the join table
        s4 = get_session(db_engine)
        author_ids = get_author_ids(s4, aid)
        assert uid1 in author_ids, f"Original author {uid1} must be present"
        assert uid2 in author_ids, f"Co-author {uid2} must be added after sync + rebuild"
        s4.close()

    def test_repair_orphan_article_authors(self, db_engine):
        """REGRESSION: startup repair populates article_authors for orphan articles.

        Articles without author links are repaired from git history.
        """
        import json
        import uuid as _uuid
        from peerpedia_core.storage.db.engine import get_session
        from peerpedia_core.storage.db.models import User
        from peerpedia_core.storage.git_backend import commit_article, init_article_repo
        from peerpedia_core.storage.db.crud_article import (
            create_article,
            get_author_ids,
            repair_orphan_article_authors,
        )

        s = get_session(db_engine)
        u = User(username="repair_test_u", password_hash="", name="RepairAuthor", anonymous_name="ra")
        s.add(u)
        s.commit()
        uid = u.id
        s.close()

        # Create article with git history but NO article_authors rows
        aid = str(_uuid.uuid4())
        rp = init_article_repo(aid)
        (rp / "article.md").write_text("# Repair Test")
        commit_article(rp, "init", "RepairAuthor", f"{uid}@peerpedia")
        (rp / "article.json").write_text(json.dumps({"status": "draft", "title": "Repair Me"}))

        # Create article with empty authors (simulating the broken state)
        s2 = get_session(db_engine)
        a = create_article(s2, authors=[], id=aid, status="draft")
        s2.commit()
        # Verify it has no authors
        assert get_author_ids(s2, aid) == []
        s2.close()

        # Run repair
        s3 = get_session(db_engine)
        repaired = repair_orphan_article_authors(s3)
        assert repaired >= 1, f"Expected ≥1 repair, got {repaired}"

        # Verify authors are now populated
        author_ids = get_author_ids(s3, aid)
        assert uid in author_ids, f"Author {uid} should be in {author_ids} after repair"
        s3.close()
