# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for author repair, git email resolution, and sync integrity.

Phase 0 regression tests — ensure PR #63's remaining author/article link
bugs are fixed:

- Partial author loss (1 of N authors)
- Full repair mode (replace, not merge)
- Legacy username@peerpedia email resolution
- repo_bundle create author rebuild
- /sync auto-create doesn't leave orphan articles
"""

from peerpedia_core.storage.db.crud_article import (
    add_article_authors,
    get_author_ids,
    replace_article_authors,
    resolve_user_id_from_git_email,
)
from peerpedia_core.storage.db.engine import get_session
from peerpedia_core.storage.db.models import Article, User

# ── Unit tests: replace_article_authors ──────────────────────────────────


class TestReplaceArticleAuthors:
    def test_replaces_all_authors(self, db_engine):
        s = get_session(db_engine)
        u1 = User(
            id="u-replace-1",
            username="alice",
            password_hash="",
            name="A",
            anonymous_name="a",
            affiliation="X",
            expertise=[],
            reputation={},
        )
        u2 = User(
            id="u-replace-2",
            username="bob",
            password_hash="",
            name="B",
            anonymous_name="b",
            affiliation="X",
            expertise=[],
            reputation={},
        )
        u3 = User(
            id="u-replace-3",
            username="carol",
            password_hash="",
            name="C",
            anonymous_name="c",
            affiliation="X",
            expertise=[],
            reputation={},
        )
        for u in [u1, u2, u3]:
            s.add(u)
        a = Article(id="a-replace", status="draft", fork_count=0)
        s.add(a)
        s.commit()

        # Start with alice + bob
        add_article_authors(s, "a-replace", ["u-replace-1", "u-replace-2"])
        s.commit()
        assert set(get_author_ids(s, "a-replace")) == {"u-replace-1", "u-replace-2"}

        # Replace with carol only
        replace_article_authors(s, "a-replace", {"u-replace-3"})
        s.commit()
        assert set(get_author_ids(s, "a-replace")) == {"u-replace-3"}

        # Replace with empty set
        replace_article_authors(s, "a-replace", set())
        s.commit()
        assert get_author_ids(s, "a-replace") == []

    def test_replace_sorts_by_username(self, db_engine):
        s = get_session(db_engine)
        u1 = User(
            id="u-sort-1",
            username="zebra",
            password_hash="",
            name="Z",
            anonymous_name="z",
            affiliation="X",
            expertise=[],
            reputation={},
        )
        u2 = User(
            id="u-sort-2",
            username="alpha",
            password_hash="",
            name="A",
            anonymous_name="a",
            affiliation="X",
            expertise=[],
            reputation={},
        )
        for u in [u1, u2]:
            s.add(u)
        a = Article(id="a-sort", status="draft", fork_count=0)
        s.add(a)
        s.commit()

        replace_article_authors(s, "a-sort", {"u-sort-1", "u-sort-2"})
        s.commit()
        ids = get_author_ids(s, "a-sort")
        # alpha (u-sort-2) should come before zebra (u-sort-1)
        assert ids[0] == "u-sort-2"
        assert ids[1] == "u-sort-1"


# ── Unit tests: resolve_user_id_from_git_email ───────────────────────────


class TestResolveUserFromGitEmail:
    def test_canonical_uuid_email(self, db_engine):
        s = get_session(db_engine)
        u = User(
            id="u-email-1",
            username="email1",
            password_hash="",
            name="E",
            anonymous_name="e",
            affiliation="X",
            expertise=[],
            reputation={},
        )
        s.add(u)
        s.commit()

        result = resolve_user_id_from_git_email(s, "u-email-1@peerpedia")
        assert result == "u-email-1"

    def test_unknown_email_raises_value_error(self, db_engine):
        """resolve_user_id_from_git_email raises ValueError on unknown email."""
        import pytest

        s = get_session(db_engine)
        with pytest.raises(ValueError, match="No user found for git email"):
            resolve_user_id_from_git_email(s, "noreply@example.com")


# ── Integration tests: repo_bundle create ────────────────────────────────


class TestRepoBundleAuthorRebuild:
    def test_bundle_create_rebuilds_authors_from_git(self, db_engine):
        """After creating via repo_bundle, article_authors should include the
        creating user (Phase 2c will tighten to ONLY current_user)."""
        import base64
        import io
        import tarfile
        import tempfile
        from pathlib import Path

        import git as gitmod
        from fastapi.testclient import TestClient
        from peerpedia_api import deps
        from peerpedia_api.main import app

        s = get_session(db_engine)
        user = User(
            id="u-bundle-1",
            username="bundle_u1",
            password_hash="",
            name="BundleUser",
            anonymous_name="b",
            affiliation="X",
            expertise=[],
            reputation={},
        )
        s.add(user)
        s.commit()
        uid = user.id

        # Override get_db
        def override_db():
            session = get_session(db_engine)
            try:
                yield session
            finally:
                session.close()

        def override_require_user():
            return s.get(User, uid)

        app.dependency_overrides[deps.get_db] = override_db
        app.dependency_overrides[deps.require_user] = override_require_user

        try:
            # Build a minimal git repo tar.gz — arcname must match article ID (UUID)
            article_id = "b7e01d2a-4f8c-4c1e-9d5a-8e3f2a1b6c0d"
            with tempfile.TemporaryDirectory() as tmp:
                rp = Path(tmp) / article_id
                rp.mkdir()
                repo = gitmod.Repo.init(rp)
                (rp / "article.md").write_text("# Bundle Test\n")
                repo.index.add(["article.md"])
                repo.index.commit(
                    "Initial", author=gitmod.Actor("Test", f"{uid}@peerpedia"), committer=gitmod.Actor("Test", f"{uid}@peerpedia")
                )
                buf = io.BytesIO()
                with tarfile.open(fileobj=buf, mode="w:gz") as tar:
                    tar.add(str(rp), arcname=article_id)
                bundle_b64 = base64.b64encode(buf.getvalue()).decode()

            with TestClient(app) as client:
                resp = client.post(
                    "/api/v1/articles",
                    json={
                        "id": article_id,
                        "title": "Bundle Auth Test",
                        "content": "",
                        "repo_bundle": bundle_b64,
                    },
                )
                assert resp.status_code == 201, resp.text
                returned_id = resp.json()["id"]
                assert returned_id == article_id

                # Verify the creating user is recorded as an author
                author_ids = get_author_ids(s, returned_id)
                assert uid in author_ids, f"Expected {uid} in authors, got {author_ids}"
        finally:
            app.dependency_overrides.clear()
