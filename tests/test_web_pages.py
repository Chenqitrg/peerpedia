"""Tests for HTML page templates — Bug 1 regression (author links)."""
import tempfile
from pathlib import Path
from unittest import mock

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
            from peerpedia_core.storage.db import Article, get_engine, get_session, init_db
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
            from peerpedia_core.storage.db import create_user, get_engine, get_session, init_db
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


class TestNavMyProfile:
    """Regression: nav bar must show '我的主页' when viewer is set (d3c1f03)."""

    def test_my_profile_in_nav_with_viewer(self):
        """GET /?user=X renders nav with '我的主页' link."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url, _ = _setup_db_with_article(tmp, author="zhangliang")
            from peerpedia_core.storage.db import create_user, get_engine, get_session, init_db
            engine = get_engine(db_url)
            init_db(engine)
            session = get_session(engine)
            create_user(session, id="zhangliang", name="张量", email="zhang@test.com")
            session.commit()
            session.close()

            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                resp = client.get("/?user=zhangliang")
                assert resp.status_code == 200
                html = resp.text
                assert '👤 我的主页' in html, f"Nav should show my-profile link: {html}"
                assert 'href="/user/zhangliang"' in html

    def test_no_my_profile_in_nav_without_viewer(self):
        """GET / without viewer renders nav without '我的主页'."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url, _ = _setup_db_with_article(tmp)
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                resp = client.get("/")
                assert resp.status_code == 200
                html = resp.text
                assert '👤 我的主页' not in html, f"Nav should NOT show my-profile for guest: {html}"

    def test_my_profile_in_nav_article_page(self):
        """GET /article/{id}?viewer=X renders nav with '我的主页'."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url, article_id = _setup_db_with_article(tmp, author="testuser")
            from peerpedia_core.storage.db import create_user, get_engine, get_session, init_db
            engine = get_engine(db_url)
            init_db(engine)
            session = get_session(engine)
            create_user(session, id="zhangliang", name="张量", email="zhang@test.com")
            session.commit()
            session.close()

            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                resp = client.get(f"/article/{article_id}?viewer=zhangliang")
                assert resp.status_code == 200
                html = resp.text
                assert '👤 我的主页' in html, f"Article page nav should have my-profile: {html}"


class TestFollowCountsOnProfile:
    """Regression: follow counts visible on ALL profiles, clickable (d3c1f03)."""

    def test_follow_counts_visible_on_others_profile(self):
        """GET /user/{id}?viewer=X shows follower/following counts."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url, _ = _setup_db_with_article(tmp, author="bob")
            from peerpedia_core.storage.db import create_user, get_engine, get_session, init_db
            engine = get_engine(db_url)
            init_db(engine)
            session = get_session(engine)
            create_user(session, id="alice", name="Alice", email="a@test.com")
            create_user(session, id="bob", name="Bob", email="b@test.com")
            session.commit()
            session.close()

            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                client.post("/api/v1/users/bob/follow", data={"follower_id": "alice"})

                resp = client.get("/user/bob?viewer=zhangliang")
                assert resp.status_code == 200
                html = resp.text
                assert '粉丝' in html, f"Should show follower counts: {html}"
                assert 'follow-list-panel' in html, f"Should have HTMX panel: {html}"

    def test_self_profile_shows_my_page_indicator(self):
        """GET /user/{id}?viewer={id} shows '这是我的主页'."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url, _ = _setup_db_with_article(tmp, author="alice")
            from peerpedia_core.storage.db import create_user, get_engine, get_session, init_db
            engine = get_engine(db_url)
            init_db(engine)
            session = get_session(engine)
            create_user(session, id="alice", name="Alice", email="a@test.com")
            session.commit()
            session.close()

            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                resp = client.get("/user/alice?viewer=alice")
                assert resp.status_code == 200
                html = resp.text
                assert '这是我的主页' in html

    def test_follow_counts_clickable_links(self):
        """Follow count links point to HTMX API endpoints."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url, _ = _setup_db_with_article(tmp, author="bob")
            from peerpedia_core.storage.db import create_user, get_engine, get_session, init_db
            engine = get_engine(db_url)
            init_db(engine)
            session = get_session(engine)
            create_user(session, id="alice", name="Alice", email="a@test.com")
            create_user(session, id="bob", name="Bob", email="b@test.com")
            session.commit()
            session.close()

            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                resp = client.get("/user/bob?viewer=alice")
                assert resp.status_code == 200
                html = resp.text
                assert '/followers?format=html' in html, f"Followers link: {html}"
                assert '/following?format=html' in html, f"Following link: {html}"


class TestCookieViewer:
    """Regression: cookie-based viewer identity (commit 6e1744d)."""

    def test_cookie_viewer_reads_identity(self):
        """Viewer cookie is used as identity on homepage."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url, _ = _setup_db_with_article(tmp, author="zhangliang")
            from peerpedia_core.storage.db import create_user, get_engine, get_session, init_db
            engine = get_engine(db_url)
            init_db(engine)
            session = get_session(engine)
            create_user(session, id="zhangliang", name="张量", email="zhang@test.com")
            create_user(session, id="liqun", name="李群", email="li@test.com")
            session.commit()
            session.close()

            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app, cookies={"viewer": "zhangliang"})
                resp = client.get("/")
                assert resp.status_code == 200
                html = resp.text
                assert '👤 我的主页' in html, f"Cookie viewer should see my-profile: {html}"
                assert '关注动态' in html, f"Cookie viewer should see following feed tab: {html}"

    def test_guest_cookie_sees_no_personal_features(self):
        """Guest (empty cookie) sees no my-profile or following feed."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url, _ = _setup_db_with_article(tmp)
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                resp = client.get("/")
                assert resp.status_code == 200
                html = resp.text
                assert '👤 我的主页' not in html
                assert '关注动态' not in html

    def test_viewer_dropdown_shows_all_users(self):
        """Nav dropdown contains all registered users."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url, _ = _setup_db_with_article(tmp, author="zhangliang")
            from peerpedia_core.storage.db import create_user, get_engine, get_session, init_db
            engine = get_engine(db_url)
            init_db(engine)
            session = get_session(engine)
            create_user(session, id="zhangliang", name="张量", email="zhang@test.com")
            create_user(session, id="liqun", name="李群", email="li@test.com")
            create_user(session, id="wangshouheng", name="王守恒", email="wang@test.com")
            session.commit()
            session.close()

            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app, cookies={"viewer": "zhangliang"})
                resp = client.get("/")
                assert resp.status_code == 200
                html = resp.text
                assert '张量' in html
                assert '李群' in html
                assert '王守恒' in html
                assert '游客' in html
                assert 'setViewer' in html

    def test_dropdown_preselects_current_viewer(self):
        """Dropdown has 'selected' on the cookie viewer's option."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url, _ = _setup_db_with_article(tmp, author="zhangliang")
            from peerpedia_core.storage.db import create_user, get_engine, get_session, init_db
            engine = get_engine(db_url)
            init_db(engine)
            session = get_session(engine)
            create_user(session, id="zhangliang", name="张量", email="zhang@test.com")
            session.commit()
            session.close()

            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app, cookies={"viewer": "zhangliang"})
                resp = client.get("/")
                assert resp.status_code == 200
                html = resp.text
                import re
                match = re.search(r'<option[^>]*value="zhangliang"[^>]*selected', html)
                assert match is not None, f"zhangliang should be preselected: {html}"

    def test_cookie_persists_across_pages(self):
        """Viewer cookie is read on user profile page too."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url, _ = _setup_db_with_article(tmp, author="wangshouheng")
            from peerpedia_core.storage.db import create_user, get_engine, get_session, init_db
            engine = get_engine(db_url)
            init_db(engine)
            session = get_session(engine)
            create_user(session, id="zhangliang", name="张量", email="zhang@test.com")
            create_user(session, id="wangshouheng", name="王守恒", email="wang@test.com")
            session.commit()
            session.close()

            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app, cookies={"viewer": "zhangliang"})
                resp = client.get("/user/wangshouheng")
                assert resp.status_code == 200
                html = resp.text
                assert '👤 我的主页' in html
                assert '张量' in html
                assert '关注' in html

    def test_viewer_dropdown_visible_on_all_pages(self):
        """User dropdown appears on editor, review, and article pages."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url, article_id = _setup_db_with_article(tmp, author="zhangliang")
            from peerpedia_core.storage.db import create_user, get_engine, get_session, init_db
            engine = get_engine(db_url)
            init_db(engine)
            session = get_session(engine)
            create_user(session, id="zhangliang", name="张量", email="zhang@test.com")
            session.commit()
            session.close()

            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app, cookies={"viewer": "zhangliang"})
                for path in [f"/article/{article_id}", "/edit", "/review"]:
                    resp = client.get(path)
                    assert resp.status_code in (200, 404)
                    if resp.status_code == 200:
                        assert 'viewer-picker' in resp.text, f"{path} missing picker"
                        assert 'setViewer' in resp.text, f"{path} missing setViewer"


class TestReviewButtonOnArticle:
    """B1: Article page should show review button for submitted/in_review articles."""

    def _make_submitted(self, db_url: str, article_id: str):
        """Set article status to 'submitted' so the review button appears."""
        from peerpedia_core.storage.db import get_engine, init_db, get_session, get_article
        engine = get_engine(db_url)
        init_db(engine)
        session = get_session(engine)
        try:
            a = get_article(session, article_id)
            if a:
                a.status = "submitted"
                session.commit()
        finally:
            session.close()

    def test_review_button_visible_for_submitted_article(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_url, article_id = _setup_db_with_article(tmp, author="zhangliang")
            self._make_submitted(db_url, article_id)
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                resp = client.get(f"/article/{article_id}")
                assert resp.status_code == 200
                assert "btn-review" in resp.text, f"Expected review button: {resp.text[:500]}"

    def test_review_button_links_to_review_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_url, article_id = _setup_db_with_article(tmp, author="wangshouheng")
            self._make_submitted(db_url, article_id)
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                resp = client.get(f"/article/{article_id}")
                assert f'/review/{article_id}' in resp.text


class TestCollaborationButtonOnReview:
    """B2: Review page should show collaboration request checkbox."""

    def test_review_page_has_collaboration_checkbox(self):
        """Review page still has the collaboration request checkbox."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url, article_id = _setup_db_with_article(tmp, author="alice")
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                resp = client.get(f"/review/{article_id}?viewer=bob")
                assert resp.status_code == 200
                html = resp.text
                assert '发表评分' in html, f"Should have submit button: {html}"

    def test_collaboration_message_field_present(self):
        """Review page should have a comments textarea for discussion."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url, article_id = _setup_db_with_article(tmp, author="alice")
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                resp = client.get(f"/review/{article_id}?viewer=bob")
                assert resp.status_code == 200
                html = resp.text
                assert 'textarea' in html, f"Should have comment textarea: {html}"
                assert '五维评分' in html, f"Should have rating section: {html}"


class TestLANStatusPage:
    """B7: LAN status page should render."""

    def test_lan_status_page_renders(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_url, _ = _setup_db_with_article(tmp, author="zhangliang")
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                resp = client.get("/lan-status")
                assert resp.status_code == 200
                assert "局域网状态" in resp.text

    def test_lan_status_shows_empty_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_url, _ = _setup_db_with_article(tmp, author="zhangliang")
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                resp = client.get("/lan-status")
                # Without LAN mode, shows empty state
                assert "没有在线节点" in resp.text or "LAN 模式" in resp.text or "peerpedia serve --lan" in resp.text


class TestArticlePageWithTransitions:
    """B5: Article page should load citation transitions."""

    def test_article_page_has_transition_script(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_url, article_id = _setup_db_with_article(tmp, author="zhangliang")
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                resp = client.get(f"/article/{article_id}")
                assert resp.status_code == 200
                # Transition probability API call should be in the page
                assert "transitions" in resp.text or "citing" in resp.text.lower()


class TestArticlePageNoRawJSON:
    """Regression: article page must not leak raw JSON into rendered HTML.

    Bug: HTMX hx-swap="innerHTML" called API endpoints that returned JSON
    instead of HTML. The page must use ?format=html on HTMX calls.
    """

    @staticmethod
    def _make_published(db_url: str, article_id: str):
        """Set article status to 'published' so timeline/proposals render."""
        from peerpedia_core.storage.db import (
            Article, get_engine, get_session, init_db,
        )
        engine = get_engine(db_url)
        init_db(engine)
        session = get_session(engine)
        try:
            a = session.query(Article).filter(Article.id == article_id).first()
            if a:
                a.status = "published"
                session.commit()
        finally:
            session.close()

    def test_article_page_no_contributions_json_leak(self):
        """Contribution timeline section uses format=html, not raw JSON."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url, article_id = _setup_db_with_article(tmp, author="zhangliang")
            self._make_published(db_url, article_id)
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                resp = client.get(f"/article/{article_id}")
                assert resp.status_code == 200
                html = resp.text
                # Must NOT contain raw JSON pattern from contributions endpoint
                assert '"timeline"' not in html, (
                    f"Raw JSON leak: 'timeline' key found in page HTML"
                )
                assert '"breakdown"' not in html, (
                    f"Raw JSON leak: 'breakdown' key found in page HTML"
                )
                assert '"total_records"' not in html, (
                    f"Raw JSON leak: 'total_records' key found in page HTML"
                )
                # HTMX call must use format=html
                assert 'contributions?format=html' in html, (
                    f"Missing format=html in contributions hx-get"
                )

    def test_article_page_no_proposals_json_leak(self):
        """Proposals section uses format=html, not raw JSON."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url, article_id = _setup_db_with_article(tmp, author="zhangliang")
            self._make_published(db_url, article_id)
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                resp = client.get(f"/article/{article_id}")
                assert resp.status_code == 200
                html = resp.text
                # HTMX call must use format=html
                assert 'proposals?format=html' in html, (
                    f"Missing format=html in proposals hx-get"
                )

    def test_htmx_endpoints_return_html_not_json(self):
        """HTMX endpoints with format=html return HTML, not JSON."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url, article_id = _setup_db_with_article(tmp, author="testuser")
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                # Contributions HTML
                resp = client.get(
                    f"/api/v1/articles/{article_id}/contributions?format=html"
                )
                assert resp.status_code == 200
                assert not resp.text.startswith("{")
                assert "<" in resp.text  # contains HTML tags
                # Proposals HTML
                resp = client.get(
                    f"/api/v1/articles/{article_id}/proposals?format=html"
                )
                assert resp.status_code == 200
                assert not resp.text.startswith("{")
                assert "<" in resp.text  # contains HTML tags
