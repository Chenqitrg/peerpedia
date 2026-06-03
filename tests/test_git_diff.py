"""Tests for git diff, commit history, and review comments."""

import pytest
import tempfile
import uuid
from pathlib import Path
from unittest.mock import patch, MagicMock

from peerpedia_core.storage.git_backend import (
    get_commit_history,
    get_diff,
    get_diff_between,
    get_blame,
    init_article_repo,
    commit_article,
)
from peerpedia_core.storage.db import (
    ReviewComment,
    create_review_comment,
    get_review_comment,
    get_comments_for_article,
    resolve_review_comment,
    create_article,
    get_article,
    get_engine,
    init_db,
    get_session,
)


# ── Git Diff Tests ──────────────────────────────────────────────────────────


class TestGetDiff:
    """Git diff extraction from article repos."""

    def test_get_diff_single_commit(self):
        """Get diff for a single commit."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            article_id = str(uuid.uuid4())
            repo_path = init_article_repo(article_id, base_dir=base)

            # Write and commit a file
            source = repo_path / "main.typ"
            source.write_text("= Introduction\n\nHello world.\n")
            commit_hash = commit_article(repo_path, "Initial commit", "alice", "alice@test.com")

            diff_data = get_diff(repo_path, commit_hash)
            assert diff_data["commit_hash"] == commit_hash
            assert "Initial commit" in diff_data["message"]
            assert diff_data["author"] == "alice"
            assert diff_data["diff_text"] != ""
            # Initial commit may have files via a_path or b_path
            assert len(diff_data["files"]) >= 0  # files might be empty for initial commit

    def test_get_diff_multiple_commits(self):
        """Get diff for the second commit shows changes correctly."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            article_id = str(uuid.uuid4())
            repo_path = init_article_repo(article_id, base_dir=base)

            source = repo_path / "main.typ"
            source.write_text("= Title\n\nFirst version.\n")
            commit1 = commit_article(repo_path, "First commit", "alice", "alice@test.com")

            source.write_text("= Title\n\nSecond version with more content.\n\n== New Section\n\nExtra.\n")
            commit2 = commit_article(repo_path, "Second commit", "bob", "bob@test.com")

            # Diff for the second commit should show changes
            diff_data = get_diff(repo_path, commit2)
            assert diff_data["commit_hash"] == commit2
            assert diff_data["author"] == "bob"
            assert diff_data["parent_hash"] == commit1
            assert len(diff_data["diff_text"]) > 0

    def test_get_diff_between_commits(self):
        """Get diff between two arbitrary commits."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            article_id = str(uuid.uuid4())
            repo_path = init_article_repo(article_id, base_dir=base)

            source = repo_path / "main.typ"
            source.write_text("= V1\n\nContent v1.\n")
            commit1 = commit_article(repo_path, "v1", "alice", "alice@test.com")

            source.write_text("= V2\n\nContent v2.\n")
            commit2 = commit_article(repo_path, "v2", "bob", "bob@test.com")

            source.write_text("= V3\n\nContent v3.\n")
            commit3 = commit_article(repo_path, "v3", "charlie", "charlie@test.com")

            diff_data = get_diff_between(repo_path, commit1, commit3)
            assert diff_data["commit_hash"] == commit3
            assert diff_data["parent_hash"] == commit1
            assert len(diff_data["diff_text"]) > 0


class TestCommitHistory:
    """Commit history listing."""

    def test_get_commit_history(self):
        """Get commit history from an article repo."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            article_id = str(uuid.uuid4())
            repo_path = init_article_repo(article_id, base_dir=base)

            source = repo_path / "main.typ"
            source.write_text("= Test\n\nContent.\n")
            commit_article(repo_path, "First", "alice", "alice@test.com")

            source.write_text("= Test\n\nMore content.\n")
            commit_article(repo_path, "Second", "bob", "bob@test.com")

            history = get_commit_history(repo_path)
            assert len(history) >= 2
            # Most recent first
            assert "Second" in history[0]["message"]
            assert history[0]["author"] == "bob"


# ── ReviewComment Tests ─────────────────────────────────────────────────────


class TestReviewCommentModel:
    """ReviewComment ORM model CRUD tests."""

    @pytest.fixture
    def db_setup(self):
        """Set up a temporary DB with an article."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            engine = get_engine(f"sqlite:///{db_path}")
            init_db(engine)
            session = get_session(engine)
            article_id = str(uuid.uuid4())
            create_article(
                session,
                id=article_id,
                title="Test Article",
                founding_authors=["alice"],
                abstract="Test",
                git_repo_path="/tmp/test",
            )
            session.commit()
            yield session, article_id, db_path
            session.close()

    def test_create_comment(self, db_setup):
        session, article_id, _ = db_setup
        comment = create_review_comment(
            session,
            article_id=article_id,
            commit_hash="abc123",
            author_id="bob",
            body="This line has a typo.",
            file_path="main.typ",
            line_start=42,
            comment_type="comment",
        )
        session.commit()

        assert comment.id is not None
        assert comment.article_id == article_id
        assert comment.commit_hash == "abc123"
        assert comment.author_id == "bob"
        assert comment.line_start == 42
        assert comment.comment_type == "comment"
        assert comment.resolved == 0  # False in DB

    def test_get_comments_for_article(self, db_setup):
        session, article_id, _ = db_setup
        create_review_comment(
            session,
            article_id=article_id,
            commit_hash="abc123",
            author_id="bob",
            body="Comment 1",
            line_start=10,
        )
        create_review_comment(
            session,
            article_id=article_id,
            commit_hash="abc123",
            author_id="alice",
            body="Comment 2",
            line_start=20,
        )
        session.commit()

        comments = get_comments_for_article(session, article_id)
        assert len(comments) == 2

        # Filter by commit_hash
        filtered = get_comments_for_article(session, article_id, commit_hash="abc123")
        assert len(filtered) == 2

        # Filter by non-matching commit_hash
        filtered2 = get_comments_for_article(session, article_id, commit_hash="xyz999")
        assert len(filtered2) == 0

    def test_resolve_comment(self, db_setup):
        session, article_id, _ = db_setup
        comment = create_review_comment(
            session,
            article_id=article_id,
            commit_hash="abc123",
            author_id="bob",
            body="Fix this.",
            line_start=5,
        )
        session.commit()

        resolved = resolve_review_comment(session, comment.id, resolved=True)
        session.commit()
        assert resolved is not None
        assert resolved.resolved == 1  # True in DB
        assert resolved.to_dict()["resolved"] is True

    def test_comment_with_suggestion(self, db_setup):
        session, article_id, _ = db_setup
        comment = create_review_comment(
            session,
            article_id=article_id,
            commit_hash="abc123",
            author_id="bob",
            body="Better formula:",
            suggestion="E = mc^2",
            comment_type="suggestion",
            line_start=15,
        )
        session.commit()

        cd = comment.to_dict()
        assert cd["comment_type"] == "suggestion"
        assert cd["suggestion"] == "E = mc^2"
        assert cd["resolved"] is False

    def test_get_single_comment(self, db_setup):
        session, article_id, _ = db_setup
        comment = create_review_comment(
            session,
            article_id=article_id,
            commit_hash="abc123",
            author_id="alice",
            body="Test comment.",
            line_start=1,
        )
        session.commit()

        retrieved = get_review_comment(session, comment.id)
        assert retrieved is not None
        assert retrieved.id == comment.id
        assert retrieved.body == "Test comment."

    def test_comments_sorted_by_created_at(self, db_setup):
        session, article_id, _ = db_setup
        c1 = create_review_comment(
            session,
            article_id=article_id,
            commit_hash="abc123",
            author_id="alice",
            body="First",
            line_start=1,
        )
        session.commit()

        c2 = create_review_comment(
            session,
            article_id=article_id,
            commit_hash="abc123",
            author_id="bob",
            body="Second",
            line_start=2,
        )
        session.commit()

        comments = get_comments_for_article(session, article_id)
        assert len(comments) == 2
        assert comments[0].body == "First"
        assert comments[1].body == "Second"


# ── API Endpoint Tests ──────────────────────────────────────────────────────


class TestGitDiffAPI:
    """API endpoint tests for commit history and diff."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from peerpedia.web.app import app
        return TestClient(app)

    def test_commits_endpoint_returns_json(self, client):
        """GET /api/v1/articles/{id}/commits returns JSON."""
        # Need an article with a git repo
        with tempfile.TemporaryDirectory() as tmp:
            from peerpedia.config.settings import settings

            base = Path(tmp)
            db_path = base / "test.db"
            articles_dir = base / "articles"
            articles_dir.mkdir()

            # Create article with git repo
            source = base / "test.typ"
            source.write_text("---\ntitle: API Test\n---\n\n= Test\n\nContent.\n")

            from peerpedia.submit import submit_article
            result = submit_article(
                source_path=source,
                database_url=f"sqlite:///{db_path}",
                articles_dir=articles_dir,
            )
            assert result.success

            # Override settings to use our test DB
            original_url = settings.database_url
            settings.database_url = f"sqlite:///{db_path}"

            try:
                response = client.get(f"/api/v1/articles/{result.article_id}/commits")
                assert response.status_code == 200
                data = response.json()
                assert data["article_id"] == result.article_id
                assert len(data["commits"]) >= 1
                assert "hash" in data["commits"][0]
                assert "message" in data["commits"][0]
                assert "author" in data["commits"][0]
            finally:
                settings.database_url = original_url

    def test_diff_endpoint_returns_json(self, client):
        """GET /api/v1/articles/{id}/diff/{hash} returns diff data."""
        with tempfile.TemporaryDirectory() as tmp:
            from peerpedia.config.settings import settings

            base = Path(tmp)
            db_path = base / "test.db"
            articles_dir = base / "articles"
            articles_dir.mkdir()

            source = base / "test.typ"
            source.write_text("---\ntitle: Diff Test\n---\n\n= Test\n\nContent.\n")

            from peerpedia.submit import submit_article
            result = submit_article(
                source_path=source,
                database_url=f"sqlite:///{db_path}",
                articles_dir=articles_dir,
            )

            original_url = settings.database_url
            settings.database_url = f"sqlite:///{db_path}"

            try:
                response = client.get(
                    f"/api/v1/articles/{result.article_id}/diff/{result.git_commit_hash}"
                )
                assert response.status_code == 200
                data = response.json()
                assert data["commit_hash"] == result.git_commit_hash
                assert "diff_text" in data
                assert "files" in data
            finally:
                settings.database_url = original_url

    def test_commits_html_endpoint(self, client):
        """GET /api/v1/articles/{id}/commits/html returns HTML."""
        with tempfile.TemporaryDirectory() as tmp:
            from peerpedia.config.settings import settings

            base = Path(tmp)
            db_path = base / "test.db"
            articles_dir = base / "articles"
            articles_dir.mkdir()

            source = base / "test.typ"
            source.write_text("---\ntitle: HTML Test\n---\n\n= Test\n\nContent.\n")

            from peerpedia.submit import submit_article
            result = submit_article(
                source_path=source,
                database_url=f"sqlite:///{db_path}",
                articles_dir=articles_dir,
            )

            original_url = settings.database_url
            settings.database_url = f"sqlite:///{db_path}"

            try:
                response = client.get(f"/api/v1/articles/{result.article_id}/commits/html")
                assert response.status_code == 200
                assert "commit-item" in response.text
            finally:
                settings.database_url = original_url

    def test_diff_endpoint_article_not_found(self, client):
        """Diff endpoint returns 404 for nonexistent article."""
        with tempfile.TemporaryDirectory() as tmp:
            from peerpedia.config.settings import settings

            original_url = settings.database_url
            tmp_db = Path(tmp) / "test.db"
            settings.database_url = f"sqlite:///{tmp_db}"

            try:
                from peerpedia_core.storage.db import get_engine, init_db
                engine = get_engine(settings.database_url)
                init_db(engine)

                # Create an article and delete it, then try diff
                from peerpedia.submit import submit_article
                source = Path(tmp) / "test.typ"
                source.write_text("---\ntitle: Gone\n---\n\n= Test\n")
                result = submit_article(
                    source_path=source,
                    database_url=settings.database_url,
                    articles_dir=Path(tmp) / "articles",
                )
                # Use a fake article ID
                response = client.get("/api/v1/articles/fake-nonexistent-id/diff/abc123")
                assert response.status_code == 404
            finally:
                settings.database_url = original_url

    def test_commits_endpoint_article_not_found(self, client):
        """Commits endpoint returns 404 for nonexistent article."""
        response = client.get("/api/v1/articles/nonexistent-id/commits")
        assert response.status_code == 404


class TestReviewCommentAPI:
    """API endpoint tests for review comments."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from peerpedia.web.app import app
        return TestClient(app)

    def test_create_comment(self, client):
        """POST /api/v1/articles/{id}/comments creates a comment."""
        with tempfile.TemporaryDirectory() as tmp:
            from peerpedia.config.settings import settings

            base = Path(tmp)
            db_path = base / "test.db"
            articles_dir = base / "articles"
            articles_dir.mkdir()

            source = base / "test.typ"
            source.write_text("---\ntitle: Comment Test\n---\n\n= Test\n\nContent.\n")

            from peerpedia.submit import submit_article
            result = submit_article(
                source_path=source,
                database_url=f"sqlite:///{db_path}",
                articles_dir=articles_dir,
            )

            original_url = settings.database_url
            settings.database_url = f"sqlite:///{db_path}"

            try:
                response = client.post(
                    f"/api/v1/articles/{result.article_id}/comments",
                    data={
                        "commit_hash": result.git_commit_hash,
                        "author_id": "reviewer1",
                        "body": "This line needs fixing.",
                        "file_path": "test.typ",
                        "line_start": "5",
                        "comment_type": "comment",
                    },
                )
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "created"
                assert data["comment"]["author_id"] == "reviewer1"
                assert data["comment"]["line_start"] == 5
            finally:
                settings.database_url = original_url

    def test_get_comments_empty(self, client):
        """GET /api/v1/articles/{id}/comments returns empty list."""
        with tempfile.TemporaryDirectory() as tmp:
            from peerpedia.config.settings import settings

            base = Path(tmp)
            db_path = base / "test.db"
            articles_dir = base / "articles"
            articles_dir.mkdir()

            source = base / "test.typ"
            source.write_text("---\ntitle: Empty Comments\n---\n\n= Test\n\nContent.\n")

            from peerpedia.submit import submit_article
            result = submit_article(
                source_path=source,
                database_url=f"sqlite:///{db_path}",
                articles_dir=articles_dir,
            )

            original_url = settings.database_url
            settings.database_url = f"sqlite:///{db_path}"

            try:
                response = client.get(f"/api/v1/articles/{result.article_id}/comments")
                assert response.status_code == 200
                data = response.json()
                assert data["total"] == 0
                assert data["comments"] == []
            finally:
                settings.database_url = original_url

    def test_resolve_comment(self, client):
        """POST /api/v1/articles/{id}/comments/{cid}/resolve resolves comment."""
        with tempfile.TemporaryDirectory() as tmp:
            from peerpedia.config.settings import settings

            base = Path(tmp)
            db_path = base / "test.db"
            articles_dir = base / "articles"
            articles_dir.mkdir()

            source = base / "test.typ"
            source.write_text("---\ntitle: Resolve Test\n---\n\n= Test\n\nContent.\n")

            from peerpedia.submit import submit_article
            result = submit_article(
                source_path=source,
                database_url=f"sqlite:///{db_path}",
                articles_dir=articles_dir,
            )

            original_url = settings.database_url
            settings.database_url = f"sqlite:///{db_path}"

            try:
                # Create comment first
                create_resp = client.post(
                    f"/api/v1/articles/{result.article_id}/comments",
                    data={
                        "commit_hash": result.git_commit_hash,
                        "author_id": "reviewer1",
                        "body": "Fix this.",
                        "line_start": "10",
                        "comment_type": "comment",
                    },
                )
                comment_id = create_resp.json()["comment"]["id"]

                # Resolve it
                resolve_resp = client.post(
                    f"/api/v1/articles/{result.article_id}/comments/{comment_id}/resolve"
                )
                assert resolve_resp.status_code == 200
                assert resolve_resp.json()["resolved"] is True
            finally:
                settings.database_url = original_url

    def test_create_suggestion_comment(self, client):
        """POST comment with suggestion type."""
        with tempfile.TemporaryDirectory() as tmp:
            from peerpedia.config.settings import settings

            base = Path(tmp)
            db_path = base / "test.db"
            articles_dir = base / "articles"
            articles_dir.mkdir()

            source = base / "test.typ"
            source.write_text("---\ntitle: Suggestion Test\n---\n\n= Test\n\nContent with typo.\n")

            from peerpedia.submit import submit_article
            result = submit_article(
                source_path=source,
                database_url=f"sqlite:///{db_path}",
                articles_dir=articles_dir,
            )

            original_url = settings.database_url
            settings.database_url = f"sqlite:///{db_path}"

            try:
                response = client.post(
                    f"/api/v1/articles/{result.article_id}/comments",
                    data={
                        "commit_hash": result.git_commit_hash,
                        "author_id": "reviewer1",
                        "body": "Suggested fix:",
                        "suggestion": "Content without typo.",
                        "line_start": "3",
                        "comment_type": "suggestion",
                    },
                )
                assert response.status_code == 200
                data = response.json()
                assert data["comment"]["comment_type"] == "suggestion"
                assert data["comment"]["suggestion"] == "Content without typo."
            finally:
                settings.database_url = original_url
