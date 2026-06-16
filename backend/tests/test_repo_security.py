# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for repo security — tar extraction, symlink rejection, path traversal."""
import base64
import io
import os
import tarfile
import tempfile
from pathlib import Path

import git as gitmod
import pytest
from fastapi.testclient import TestClient

from peerpedia_api.policies.repo import (
    ensure_inside,
    reject_symlinks,
    safe_extract_tar,
)
from peerpedia_core.storage.db.engine import get_session, init_db
from peerpedia_core.storage.db.models import Article, ArticleAuthor, User
from peerpedia_core.storage.git_backend import commit_article, init_article_repo


# ── safe_extract_tar ─────────────────────────────────────────────────────

class TestSafeExtractTar:
    def test_normal_tar_extracts(self, tmp_path):
        """A clean tar extracts without error."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "README.md").write_text("# Hello")
        (src / ".git").mkdir()

        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            tar.add(str(src), arcname="my-article")

        dest = tmp_path / "dest"
        dest.mkdir()
        buf.seek(0)
        with tarfile.open(fileobj=buf, mode="r:gz") as tar:
            safe_extract_tar(tar, dest)

        assert (dest / "my-article" / "README.md").exists()

    def test_rejects_dotdot_path(self, tmp_path):
        """Tar with ../ path must be rejected."""
        dest = tmp_path / "dest"
        dest.mkdir()

        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            info = tarfile.TarInfo(name="../escape.txt")
            info.size = 4
            buf2 = io.BytesIO(b"evil")
            tar.addfile(info, buf2)

        buf.seek(0)
        with tarfile.open(fileobj=buf, mode="r:gz") as tar:
            with pytest.raises(Exception) as exc:
                safe_extract_tar(tar, dest)
            assert "400" in str(exc.value) or "escape" in str(exc.value).lower() or "Unsafe" in str(exc.value)

    def test_rejects_symlink(self, tmp_path):
        """Tar with symlink member must be rejected."""
        dest = tmp_path / "dest"
        dest.mkdir()

        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            info = tarfile.TarInfo(name="link")
            info.type = tarfile.SYMTYPE
            info.linkname = "/etc/passwd"
            tar.addfile(info)

        buf.seek(0)
        with tarfile.open(fileobj=buf, mode="r:gz") as tar:
            with pytest.raises(Exception) as exc:
                safe_extract_tar(tar, dest)
            assert "400" in str(exc.value) or "symlink" in str(exc.value).lower()

    def test_rejects_absolute_path(self, tmp_path):
        """Tar with absolute path must be rejected."""
        dest = tmp_path / "dest"
        dest.mkdir()

        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            info = tarfile.TarInfo(name="/etc/hacked")
            info.size = 1
            buf2 = io.BytesIO(b"x")
            tar.addfile(info, buf2)

        buf.seek(0)
        with tarfile.open(fileobj=buf, mode="r:gz") as tar:
            with pytest.raises(Exception) as exc:
                safe_extract_tar(tar, dest)
            assert "400" in str(exc.value) or "Unsafe" in str(exc.value)


# ── reject_symlinks ──────────────────────────────────────────────────────

class TestRejectSymlinks:
    def test_clean_dir_passes(self, tmp_path):
        (tmp_path / "file.txt").write_text("ok")
        reject_symlinks(tmp_path)  # no exception

    def test_symlink_raises(self, tmp_path):
        target = tmp_path / "real.txt"
        target.write_text("ok")
        link = tmp_path / "link.txt"
        os.symlink(str(target), str(link))

        with pytest.raises(Exception) as exc:
            reject_symlinks(tmp_path)
        assert "400" in str(exc.value) or "symlink" in str(exc.value).lower()

    def test_nested_symlink_raises(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        target = tmp_path / "real.txt"
        target.write_text("ok")
        os.symlink(str(target), str(sub / "link.txt"))

        with pytest.raises(Exception) as exc:
            reject_symlinks(tmp_path)
        assert "400" in str(exc.value) or "symlink" in str(exc.value).lower()


# ── ensure_inside ────────────────────────────────────────────────────────

class TestEnsureInside:
    def test_inside_returns_same(self, tmp_path):
        base = tmp_path / "repo"
        target = base / "article.md"
        base.mkdir()
        target.write_text("# Hi")
        result = ensure_inside(base, target)
        assert result == target.resolve()

    def test_outside_raises(self, tmp_path):
        base = tmp_path / "repo"
        base.mkdir()
        target = tmp_path / "outside.txt"
        target.write_text("# outside")

        with pytest.raises(Exception) as exc:
            ensure_inside(base, target)
        assert "400" in str(exc.value) or "escape" in str(exc.value).lower()


# ── Integration: repo_bundle create ──────────────────────────────────────

class TestRepoBundleAuthorSecurity:
    def test_bundle_only_grants_current_user(self, db_engine):
        """repo_bundle create gives permission ONLY to the uploading user (2c)."""
        from peerpedia_api import deps
        from peerpedia_api.main import app

        s = get_session(db_engine)
        user = User(id="u-bundle-sec", username="bundle_sec", password_hash="",
                    name="BundleSec", anonymous_name="b", affiliation="X",
                    expertise=[], reputation={})
        s.add(user)
        s.commit()
        uid = user.id

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
            article_id = "a7e01d2a-4f8c-4c1e-9d5a-8e3f2a1b6c0e"
            with tempfile.TemporaryDirectory() as tmp:
                rp = Path(tmp) / article_id
                rp.mkdir()
                repo = gitmod.Repo.init(rp)
                (rp / "article.md").write_text("# Bundle\n")
                repo.index.add(["article.md"])
                repo.index.commit("Init",
                                  author=gitmod.Actor("Test", f"{uid}@peerpedia"),
                                  committer=gitmod.Actor("Test", f"{uid}@peerpedia"))
                # Also add a commit from a "different" user to test anti-spoofing
                repo.index.commit("Fake",
                                  author=gitmod.Actor("Fake", "victim-uuid@peerpedia"),
                                  committer=gitmod.Actor("Fake", "victim-uuid@peerpedia"))
                buf = io.BytesIO()
                with tarfile.open(fileobj=buf, mode="w:gz") as tar:
                    tar.add(str(rp), arcname=article_id)
                bundle_b64 = base64.b64encode(buf.getvalue()).decode()

            with TestClient(app) as client:
                resp = client.post("/api/v1/articles", json={
                    "id": article_id,
                    "title": "Bundle Sec Test",
                    "content": "",
                    "repo_bundle": bundle_b64,
                })
                assert resp.status_code == 201, resp.text

                from peerpedia_core.storage.db.crud_article import get_author_ids
                author_ids = get_author_ids(s, article_id)
                # Only the uploading user should be an author — not the fake one
                assert author_ids == [uid], \
                    f"Expected only [{uid}] as author, got {author_ids}"
        finally:
            app.dependency_overrides.clear()


# ── Integration: fork rejects symlinks ───────────────────────────────────

class TestForkSymlinkRejection:
    def test_fork_rejects_symlink_in_source(self, db_engine):
        """Forking an article with a symlink in its repo must fail."""
        import shutil
        import uuid as _uuid

        from peerpedia_api import deps
        from peerpedia_api.main import app
        from peerpedia_core.storage.git_backend import DEFAULT_ARTICLES_DIR

        s = get_session(db_engine)
        user = User(id="u-fork-sec", username="fork_sec", password_hash="",
                    name="ForkSec", anonymous_name="f", affiliation="X",
                    expertise=[], reputation={})
        s.add(user)
        s.commit()
        uid = user.id

        # Create article with symlink — use unique ID to avoid cached state
        article_id = str(_uuid.uuid4())
        rp = DEFAULT_ARTICLES_DIR / article_id
        init_article_repo(article_id, base_dir=DEFAULT_ARTICLES_DIR)
        (rp / "article.md").write_text("# Fork test")
        os.symlink("/etc/passwd", str(rp / "secret"))

        a = Article(id=article_id, status="published", fork_count=0)
        s.add(a)
        s.flush()
        s.add(ArticleAuthor(article_id=article_id, author_id=uid, position=0))
        s.commit()

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
            with TestClient(app) as client:
                resp = client.post(f"/api/v1/articles/{article_id}/fork")
                assert resp.status_code == 400, \
                    f"Expected 400 for symlink, got {resp.status_code}: {resp.text}"
                assert "symlink" in resp.json()["detail"].lower()
        finally:
            app.dependency_overrides.clear()
            shutil.rmtree(str(rp), ignore_errors=True)
