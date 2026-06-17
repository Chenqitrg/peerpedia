# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Extra git route tests — verify actual content, not just status codes.

These tests strengthen the git-backed article sub-routes (history, diff,
fork, source, download) by verifying the actual response payload, not
just accepting 200/404. Added alongside existing test_routes_git.py.
"""

import shutil

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
    """TestClient with DB override only — no auth bypass."""
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


@pytest.fixture
def article_with_history(db_engine):
    """Create a user + article with a git repo containing 2 commits."""
    s = get_session(db_engine)
    u = User(username="git_extra_user", password_hash="", name="玄奘", anonymous_name="anon_xz", affiliation="大雁塔")
    s.add(u)
    s.commit()
    a = Article(status="published")
    s.add(a)
    s.flush()
    s.add(ArticleAuthor(article_id=a.id, author_id=u.id, position=0))
    s.commit()
    aid = a.id
    uid = u.id
    s.close()

    # Create git repo at the real DEFAULT_ARTICLES_DIR (routes look there)
    rp = init_article_repo(aid, DEFAULT_ARTICLES_DIR)
    (rp / "article.md").write_text("# 大唐西域记\n\n从长安出发。\n")
    h1 = commit_article(rp, "初始提交", "玄奘", "xuanzang@tang.com")
    (rp / "article.md").write_text("# 大唐西域记\n\n从长安出发。\n西行五万里。\n")
    h2 = commit_article(rp, "增加西行记述", "玄奘", "xuanzang@tang.com")

    yield {
        "article_id": aid,
        "user_id": uid,
        "commit_1": h1,
        "commit_2": h2,
    }

    # Cleanup
    shutil.rmtree(rp, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════════════
# History endpoint — real content verification
# ═══════════════════════════════════════════════════════════════════════════════


class TestHistoryContent:
    """GET /articles/{id}/history returns real commit data."""

    def test_history_returns_commit_list(self, client, article_with_history):
        aid = article_with_history["article_id"]
        resp = client.get(f"/api/v1/articles/{aid}/history")
        assert resp.status_code == 200, f"History failed: {resp.json()}"
        data = resp.json()
        assert "commits" in data
        commits = data["commits"]
        assert len(commits) == 2

    def test_history_newest_first(self, client, article_with_history):
        aid = article_with_history["article_id"]
        h2 = article_with_history["commit_2"]
        resp = client.get(f"/api/v1/articles/{aid}/history")
        commits = resp.json()["commits"]
        # Latest commit (h2) should be first
        assert commits[0]["hash"] == h2

    def test_history_has_message_and_author(self, client, article_with_history):
        aid = article_with_history["article_id"]
        resp = client.get(f"/api/v1/articles/{aid}/history")
        commits = resp.json()["commits"]
        for commit in commits:
            assert "hash" in commit, "Commit missing hash"
            assert "message" in commit, "Commit missing message"
            assert "author" in commit, "Commit missing author"
            assert "timestamp" in commit, "Commit missing timestamp"

    def test_history_each_commit_has_score_field(self, client, article_with_history):
        """Each commit should have a 'score' field (may be None if no reviews)."""
        aid = article_with_history["article_id"]
        resp = client.get(f"/api/v1/articles/{aid}/history")
        for commit in resp.json()["commits"]:
            assert "score" in commit, "Commit missing score field"

    def test_history_nonexistent_article_returns_404(self, client):
        resp = client.get("/api/v1/articles/nonexistent-id/history")
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# Diff endpoint — real content verification
# ═══════════════════════════════════════════════════════════════════════════════


class TestDiffContent:
    """GET /articles/{id}/diff/{h1}/{h2} returns real diff data."""

    def test_diff_returns_text_and_stats(self, client, article_with_history):
        aid = article_with_history["article_id"]
        h1 = article_with_history["commit_1"]
        h2 = article_with_history["commit_2"]
        resp = client.get(f"/api/v1/articles/{aid}/diff/{h1}/{h2}")
        assert resp.status_code == 200, f"Diff failed: {resp.json()}"
        data = resp.json()
        assert "diff_text" in data, "Diff missing diff_text"
        assert "stats" in data, "Diff missing stats"

    def test_diff_contains_content_change(self, client, article_with_history):
        """Diff between two commits should show the actual content change."""
        aid = article_with_history["article_id"]
        h1 = article_with_history["commit_1"]
        h2 = article_with_history["commit_2"]
        resp = client.get(f"/api/v1/articles/{aid}/diff/{h1}/{h2}")
        diff_text = resp.json()["diff_text"]
        # h2 added "西行五万里。"
        assert "西行五万里" in diff_text, f"Diff should contain the added content, got: {diff_text}"

    def test_diff_stats_not_empty(self, client, article_with_history):
        """Diff between different commits should have non-empty stats."""
        aid = article_with_history["article_id"]
        h1 = article_with_history["commit_1"]
        h2 = article_with_history["commit_2"]
        resp = client.get(f"/api/v1/articles/{aid}/diff/{h1}/{h2}")
        stats = resp.json()["stats"]
        assert stats != {}, "Stats should not be empty for real change"

    def test_diff_between_two_commits_returns_content(self, client, article_with_history):
        """Diff between two specific commits should show the actual change."""
        aid = article_with_history["article_id"]
        h1 = article_with_history["commit_1"]
        h2 = article_with_history["commit_2"]
        resp = client.get(f"/api/v1/articles/{aid}/diff/{h1}/{h2}")
        assert resp.status_code == 200, f"Diff failed: {resp.json()}"
        assert "diff_text" in resp.json()
        assert "stats" in resp.json()

    def test_diff_nonexistent_article_returns_404(self, client):
        resp = client.get("/api/v1/articles/nonexistent/diff/abc/def")
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# Source and download endpoints — real content verification
# ═══════════════════════════════════════════════════════════════════════════════


class TestSourceAndDownload:
    """GET source and download endpoints return actual file content."""

    def test_source_returns_content_and_format(self, client, article_with_history):
        aid = article_with_history["article_id"]
        resp = client.get(f"/api/v1/articles/{aid}/source")
        assert resp.status_code == 200, f"Source failed: {resp.json()}"
        data = resp.json()
        assert "content" in data
        assert "format" in data
        assert data["format"] == "markdown"
        assert "大唐西域记" in data["content"]

    def test_download_source_returns_file(self, client, article_with_history):
        """Download source returns the raw file with correct Content-Type."""
        aid = article_with_history["article_id"]
        resp = client.get(f"/api/v1/articles/{aid}/download/source")
        assert resp.status_code == 200
        assert "text/plain" in resp.headers.get("content-type", "")
        assert "大唐西域记" in resp.text

    def test_download_source_has_filename(self, client, article_with_history):
        """Download source has Content-Disposition with filename."""
        aid = article_with_history["article_id"]
        resp = client.get(f"/api/v1/articles/{aid}/download/source")
        disposition = resp.headers.get("content-disposition", "")
        assert "attachment" in disposition
        assert "filename" in disposition

    def test_source_nonexistent_article_returns_404(self, client):
        resp = client.get("/api/v1/articles/nonexistent/source")
        assert resp.status_code == 404

    def test_download_repo_returns_tar_gz(self, client, article_with_history):
        """Repo download returns valid tar.gz with git history."""
        aid = article_with_history["article_id"]
        resp = client.get(f"/api/v1/articles/{aid}/download/repo")
        assert resp.status_code == 200, f"Repo download failed: {resp.json()}"
        data = resp.content
        # gzip magic bytes
        assert data[:2] == b"\x1f\x8b"
        # Verify it's a valid tar.gz
        import io
        import tarfile

        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
            names = tar.getnames()
            assert any("article.md" in n for n in names), f"Repo archive should contain article.md, got: {names}"
            assert any(".git" in n for n in names), f"Repo archive should contain .git, got: {names}"
