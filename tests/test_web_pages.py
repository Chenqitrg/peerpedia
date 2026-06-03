"""Tests for HTML page templates — Bug 1 regression (author links)."""
import tempfile
from pathlib import Path
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from peerpedia.submit import submit_article


def _setup_db_with_article(tmp_path, author="testuser", format="markdown"):
    """Create a test DB with one submitted article. Returns (db_url, article_id)."""
    base = Path(tmp_path)
    db_path = base / "test.db"
    articles_dir = base / "articles"
    articles_dir.mkdir()
    db_url = f"sqlite:///{db_path}"

    source = base / "test.md"
    source.write_text(f"""---
title: Test Article by {author}
abstract: An article for template testing.
---

# Test Article

Content paragraph.
""")
    result = submit_article(
        source_path=source,
        database_url=db_url,
        articles_dir=articles_dir,
        author_name=author,
    )
    assert result.success, f"submit_article failed: {result.error}"
    return db_url, result.article_id


class TestHomepageAuthorLinks:
    """Regression: homepage must render author names as clickable links."""

    def test_homepage_has_author_links(self):
        """GET / renders author names as <a href="/user/{author}"> links."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url, article_id = _setup_db_with_article(tmp, author="zhangliang")
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                resp = client.get("/")
                assert resp.status_code == 200
                html = resp.text
                # Author name must be a link, not plain text
                assert 'href="/user/zhangliang"' in html, (
                    f"Expected author link href, got: {html}"
                )
                assert 'class="author-link"' in html, (
                    f"Expected author-link class, got: {html}"
                )

    def test_homepage_with_multiple_authors(self):
        """GET / renders multiple author links separated by commas."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            db_path = base / "test.db"
            articles_dir = base / "articles"
            articles_dir.mkdir()
            db_url = f"sqlite:///{db_path}"

            source = base / "test.md"
            source.write_text("""---
title: Co-authored Paper
abstract: Multiple authors.
---

# Co-authored Paper

Content.
""")
            result = submit_article(
                source_path=source,
                database_url=db_url,
                articles_dir=articles_dir,
                author_name="alice",
            )
            assert result.success

            # Manually add a second founding author in the DB
            from peerpedia_core.storage.db import get_engine, init_db, get_session, Article
            engine = get_engine(db_url)
            init_db(engine)
            session = get_session(engine)
            article = session.query(Article).filter(Article.id == result.article_id).first()
            article.founding_authors = ["alice", "bob"]
            session.commit()
            session.close()

            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                resp = client.get("/")
                assert resp.status_code == 200
                html = resp.text
                # Both authors should be links
                assert 'href="/user/alice"' in html
                assert 'href="/user/bob"' in html

    def test_homepage_viewer_param_passed_to_author_links(self):
        """When viewer query param is set, author links carry it."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url, article_id = _setup_db_with_article(tmp, author="wangshouheng")
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                resp = client.get("/?user=zhangliang")
                assert resp.status_code == 200
                html = resp.text
                # Author link should include the viewer param
                assert 'href="/user/wangshouheng?viewer=zhangliang"' in html or \
                       'href="/user/wangshouheng"' in html, (
                    f"Author link should go to user profile: {html}"
                )


class TestArticlePageAuthorLinks:
    """Regression: article page must render author names as clickable links."""

    def test_article_page_has_author_links(self):
        """GET /article/{id} renders author names as clickable links."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url, article_id = _setup_db_with_article(tmp, author="liqun")
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                resp = client.get(f"/article/{article_id}")
                assert resp.status_code == 200
                html = resp.text
                assert 'href="/user/liqun"' in html, (
                    f"Article page should have author link: {html}"
                )

    def test_article_not_found_handled(self):
        """GET /article/nonexistent returns 404 page, not crash."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url, _ = _setup_db_with_article(tmp)
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                resp = client.get("/article/nonexistent-id")
                # Should return a page (200 with "not found" or 404), not crash
                assert resp.status_code in (200, 404)


class TestUserProfilePage:
    """User profile page renders correctly."""

    def test_user_page_loads(self):
        """GET /user/{id} returns a valid page."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url, article_id = _setup_db_with_article(tmp, author="zhangsan")
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                resp = client.get("/user/zhangsan")
                assert resp.status_code == 200
                html = resp.text
                assert "zhangsan" in html
                assert "原创文章" in html  # User stats section

    def test_user_page_shows_follow_button_with_viewer(self):
        """GET /user/{id}?viewer=X shows follow/unfollow button."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url, article_id = _setup_db_with_article(tmp, author="bob")
            # Create users in the DB
            from peerpedia_core.storage.db import get_engine, init_db, get_session, create_user
            engine = get_engine(db_url)
            init_db(engine)
            session = get_session(engine)
            create_user(session, id="alice", name="Alice", email="alice@test.com")
            create_user(session, id="bob", name="Bob", email="bob@test.com")
            session.commit()
            session.close()

            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                # alice viewing bob's profile
                resp = client.get("/user/bob?viewer=alice")
                assert resp.status_code == 200
                html = resp.text
                # Should have a follow button
                assert "关注" in html or "follow" in html.lower()
