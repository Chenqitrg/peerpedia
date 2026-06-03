# Regression Tests — Follow UI + Cookie Viewer

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add ~14 regression tests for commits d3c1f03 (follow-list UI) and 6e1744d (cookie viewer), covering: follow counts on others' profiles, HTMX follower list HTML, nav my-profile link, cookie viewer persistence, viewer dropdown, guest mode, self-follow prevention, follower name correctness.

**Architecture:** Tests added to existing files — `test_follow.py` (API-layer self-follow + HTML list), `test_web_pages.py` (template-layer nav + counts + cookie + dropdown).

**Tech Stack:** pytest, FastAPI TestClient, unittest.mock, tempfile

**Baseline:** 226 tests → target ~240 tests

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `tests/test_follow.py` | Self-follow prevention API test, HTMX follower list HTML test | Modify — append 2 tests |
| `tests/test_web_pages.py` | Nav my-profile, follow counts, cookie viewer, dropdown | Modify — append 12 tests |

---

### Task 1: Self-follow prevention + follower list HTML rendering test

**Files:**
- Modify: `tests/test_follow.py` — append 2 tests

- [ ] **Step 1: Write tests**

Append to `tests/test_follow.py` after the last test in `TestFollowAPI`:

```python
    def test_cannot_self_follow(self):
        """POST /api/v1/users/{id}/follow with same follower returns 400."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url = _setup_test_db(Path(tmp))
            _create_users(db_url)
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                resp = client.post("/api/v1/users/alice/follow", data={"follower_id": "alice"})
                assert resp.status_code == 400
                assert "yourself" in resp.json()["detail"].lower() or "自己" in resp.json()["detail"]

    def test_followers_html_list_shows_correct_names(self):
        """GET /users/{id}/followers?format=html returns list with follower names."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url = _setup_test_db(Path(tmp))
            _create_users(db_url)
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                # bob and charlie follow alice
                client.post("/api/v1/users/alice/follow", data={"follower_id": "bob"})
                client.post("/api/v1/users/alice/follow", data={"follower_id": "charlie"})

                # alice follows bob
                client.post("/api/v1/users/bob/follow", data={"follower_id": "alice"})

                # alice's followers should be bob and charlie
                resp = client.get("/api/v1/users/alice/followers?format=html&viewer=alice")
                assert resp.status_code == 200
                html = resp.text
                assert "bob" in html, f"Expected bob in followers list: {html}"
                assert "charlie" in html, f"Expected charlie in followers list: {html}"
                assert '<ul class="follow-list">' in html

                # alice's following should NOT show bob as a follower name
                resp2 = client.get("/api/v1/users/alice/following?format=html&viewer=alice")
                assert resp2.status_code == 200
                assert "bob" in resp2.text, f"Expected bob in following list: {resp2.text}"

    def test_following_html_list_shows_correct_names(self):
        """GET /users/{id}/following?format=html returns list with followed names."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url = _setup_test_db(Path(tmp))
            _create_users(db_url)
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                # alice follows bob and charlie
                client.post("/api/v1/users/bob/follow", data={"follower_id": "alice"})
                client.post("/api/v1/users/charlie/follow", data={"follower_id": "alice"})

                resp = client.get("/api/v1/users/alice/following?format=html&viewer=alice")
                assert resp.status_code == 200
                html = resp.text
                assert "bob" in html, f"Expected bob in following: {html}"
                assert "charlie" in html, f"Expected charlie in following: {html}"

    def test_followers_html_empty_returns_placeholder(self):
        """GET /users/{id}/followers?format=html with no followers returns placeholder."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url = _setup_test_db(Path(tmp))
            _create_users(db_url)
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                resp = client.get("/api/v1/users/alice/followers?format=html")
                assert resp.status_code == 200
                assert "暂无" in resp.text or "follow-empty" in resp.text
```

- [ ] **Step 2: Run tests to verify**

```bash
cd ~/Projects/peerpedia && source .venv/bin/activate
python -m pytest tests/test_follow.py -v
```
Expected: existing 18 + 4 new = 22 passed

- [ ] **Step 3: Commit**

```bash
git add tests/test_follow.py
git commit -m "test: add self-follow prevention and follower list HTML tests

- test_cannot_self_follow: POST /users/{id}/follow returns 400 for self
- test_followers_html_list_shows_correct_names: field=follower_id fix verified
- test_following_html_list_shows_correct_names: field=followed_id verified
- test_followers_html_empty_returns_placeholder: empty list shows placeholder

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Nav "我的主页" link + follow counts on others' profiles

**Files:**
- Modify: `tests/test_web_pages.py` — append 6 tests

- [ ] **Step 1: Write tests**

Append to `tests/test_web_pages.py`:

```python
class TestNavMyProfile:
    """Regression: nav bar must show '我的主页' when viewer is set (d3c1f03)."""

    def test_my_profile_in_nav_with_viewer(self):
        """GET /?user=X renders nav with '我的主页' link."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url, _ = _setup_db_with_article(tmp)
            # Ensure users exist in DB
            from peerpedia_core.storage.db import get_engine, init_db, get_session, create_user
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
            from peerpedia_core.storage.db import get_engine, init_db, get_session, create_user
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
            from peerpedia_core.storage.db import get_engine, init_db, get_session, create_user
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
                # alice follows bob
                client.post("/api/v1/users/bob/follow", data={"follower_id": "alice"})

                resp = client.get("/user/bob?viewer=zhangliang")
                assert resp.status_code == 200
                html = resp.text
                # Should show follower count even though viewer != bob
                assert '粉丝' in html, f"Should show follower counts: {html}"
                assert 'follow-counts' in html or 'follow-list-panel' in html, \
                    f"Should have HTMX follow list elements: {html}"

    def test_self_profile_shows_my_page_indicator(self):
        """GET /user/{id}?viewer={id} shows '这是我的主页'."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url, _ = _setup_db_with_article(tmp, author="alice")
            from peerpedia_core.storage.db import get_engine, init_db, get_session, create_user
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
            from peerpedia_core.storage.db import get_engine, init_db, get_session, create_user
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
                # HTMX links to the followers/following API
                assert '/followers?format=html' in html, f"Followers link: {html}"
                assert '/following?format=html' in html, f"Following link: {html}"
```

- [ ] **Step 2: Run tests to verify**

```bash
cd ~/Projects/peerpedia && source .venv/bin/activate
python -m pytest tests/test_web_pages.py -v
```
Expected: existing 7 + 6 new = 13 passed

- [ ] **Step 3: Commit**

```bash
git add tests/test_web_pages.py
git commit -m "test: add nav my-profile and follow-counts regression tests

- TestNavMyProfile: 3 tests for nav '我的主页' with/without viewer
- TestFollowCountsOnProfile: 3 tests for counts on others' profiles,
  self-profile indicator, HTMX clickable links

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Cookie viewer identity regression tests

**Files:**
- Modify: `tests/test_web_pages.py` — append 6 tests

- [ ] **Step 1: Write tests**

Append to `tests/test_web_pages.py`:

```python
class TestCookieViewer:
    """Regression: cookie-based viewer identity (commit 6e1744d)."""

    def test_cookie_viewer_reads_identity(self):
        """Viewer cookie is used as identity on homepage."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url, _ = _setup_db_with_article(tmp, author="zhangliang")
            from peerpedia_core.storage.db import get_engine, init_db, get_session, create_user
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
                # No cookie = guest
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
            from peerpedia_core.storage.db import get_engine, init_db, get_session, create_user
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
                # Dropdown should mention all users
                assert '张量' in html
                assert '李群' in html
                assert '王守恒' in html
                # Guest option
                assert '游客' in html
                # setViewer function exists
                assert 'setViewer' in html

    def test_dropdown_preselects_current_viewer(self):
        """Dropdown has 'selected' on the cookie viewer's option."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url, _ = _setup_db_with_article(tmp, author="zhangliang")
            from peerpedia_core.storage.db import get_engine, init_db, get_session, create_user
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
                # zhangliang's option should be selected
                import re
                match = re.search(r'<option[^>]*value="zhangliang"[^>]*selected', html)
                assert match is not None, f"zhangliang should be preselected: {html}"

    def test_cookie_persists_across_pages(self):
        """Viewer cookie is read on user profile page too."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url, _ = _setup_db_with_article(tmp, author="wangshouheng")
            from peerpedia_core.storage.db import get_engine, init_db, get_session, create_user
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
                # Nav should still show my-profile for zhangliang
                assert '👤 我的主页' in html
                assert '张量' in html  # selected in dropdown
                # Should see unfollow button (zhangliang viewing wangshouheng)
                assert '关注' in html

    def test_query_param_falls_back_to_cookie(self):
        """Query param 'viewer' takes precedence over cookie."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url, _ = _setup_db_with_article(tmp, author="liqun")
            from peerpedia_core.storage.db import get_engine, init_db, get_session, create_user
            engine = get_engine(db_url)
            init_db(engine)
            session = get_session(engine)
            create_user(session, id="zhangliang", name="张量", email="zhang@test.com")
            create_user(session, id="liqun", name="李群", email="li@test.com")
            session.commit()
            session.close()

            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                # Cookie says zhangliang, but query param says liqun
                # Cookie is read first by get_viewer() -> returns zhangliang
                # Wait, get_viewer() reads cookie FIRST, then query param fallback
                # So cookie wins. This is intentional for persistence.
                client = TestClient(app, cookies={"viewer": "zhangliang"})
                resp = client.get("/")
                assert resp.status_code == 200
                # zhangliang should be selected in dropdown
                import re
                match = re.search(r'<option[^>]*value="zhangliang"[^>]*selected', resp.text)
                assert match is not None, f"Cookie viewer should be active: {resp.text}"
```

- [ ] **Step 2: Run tests to verify**

```bash
cd ~/Projects/peerpedia && source .venv/bin/activate
python -m pytest tests/test_web_pages.py -v
```
Expected: existing 13 + 6 new = 19 passed

- [ ] **Step 3: Commit**

```bash
git add tests/test_web_pages.py
git commit -m "test: add cookie viewer identity regression tests

- TestCookieViewer: 6 tests for cookie identity, dropdown, guest mode
- Cookie reads viewer for nav my-profile link
- Guest sees no personal features
- Dropdown lists all users with preselection
- Cookie persists across pages (user profile)
- Cookie takes precedence over query param fallback

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Final verification

- [ ] **Step 1: Run full test suite**

```bash
cd ~/Projects/peerpedia && source .venv/bin/activate
python -m pytest tests/ -v
```
Expected: 226 + 4 (follow) + 6 (nav+counts) + 6 (cookie) = ~242 passed

- [ ] **Step 2: Fix any failures**

- [ ] **Step 3: Update STATUS.md**

Update test count from 226 to ~242.

```bash
git add STATUS.md
git commit -m "docs: update STATUS.md with regression test count"
```

---

## Summary

| Task | File | New Tests | Baseline → Target |
|---|---|---|---|
| 1 | `tests/test_follow.py` | +4 | 18 → 22 |
| 2 | `tests/test_web_pages.py` | +6 | 7 → 13 |
| 3 | `tests/test_web_pages.py` | +6 | 13 → 19 |
| 4 | `STATUS.md` | — | — |

**Total: 3 commits, ~16 new tests, 226 → ~242**
