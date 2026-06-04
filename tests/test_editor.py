"""Tests for the online editor."""

from fastapi.testclient import TestClient

from peerpedia.web.app import app

client = TestClient(app)


def test_edit_page_loads():
    """GET /edit returns the editor page."""
    response = client.get("/edit")
    assert response.status_code == 200
    assert "editor-area" in response.text
    assert "CodeMirror" in response.text


def test_edit_page_has_metadata_form():
    """Editor page includes metadata form for submission."""
    response = client.get("/edit")
    assert response.status_code == 200
    assert 'name="title"' in response.text
    assert 'name="abstract"' in response.text


def test_edit_existing_article_loads():
    """GET /edit/{id} loads existing article source into editor."""
    from peerpedia.config.settings import settings
    from peerpedia_core.storage.db import get_engine, get_session, init_db, list_articles

    engine = get_engine(settings.database_url)
    init_db(engine)
    session = get_session(engine)
    try:
        articles = list_articles(session, limit=1)
        if articles:
            aid = articles[0].id
            response = client.get(f"/edit/{aid}")
            assert response.status_code == 200
            assert "editor-area" in response.text
    finally:
        session.close()


def test_edit_nonexistent_article():
    """GET /edit/{nonexistent} returns 404."""
    response = client.get("/edit/nonexistent-id-12345")
    assert response.status_code == 404
    assert "未找到" in response.text


def test_submit_via_editor():
    """Submit a new article via the editor API endpoint."""
    content = (
        "---\n"
        "title: Test Editor Article\n"
        "abstract: Testing the editor submission.\n"
        "categories:\n"
        "  - math\n"
        "keywords:\n"
        "  - test\n"
        "language: en\n"
        "---\n\n"
        "# Editor Test\n\n"
        "This was submitted from the online editor.\n\n"
        "$$E = mc^2$$\n"
    )
    response = client.post(
        "/api/v1/articles",
        data={
            "title": "Test Editor Article",
            "abstract": "Testing the editor submission.",
            "format": "markdown",
            "categories": "math",
            "keywords": "test",
            "language": "en",
        },
        files={"article_file": ("article.md", content.encode("utf-8"), "text/plain")},
    )
    assert response.status_code == 200
    data = response.json()
    assert "article_id" in data
    assert data["status"] == "submitted"


def test_submit_typst_via_editor():
    """Submit a Typst article via the editor API endpoint."""
    content = (
        "// Typst article\n"
        "#let title = \"Typst Test\"\n"
        "#let abstract = \"Testing typst submission.\"\n\n"
        "= Introduction\n\n"
        "This is a Typst article from the editor.\n"
    )
    response = client.post(
        "/api/v1/articles",
        data={
            "title": "Typst Test",
            "abstract": "Testing typst submission.",
            "format": "typst",
            "categories": "physics",
            "keywords": "typst,test",
            "language": "en",
        },
        files={"article_file": ("article.typ", content.encode("utf-8"), "text/plain")},
    )
    assert response.status_code == 200
    data = response.json()
    assert "article_id" in data


# ── Regression tests for bugs fixed 2026-06-04 ─────────────────────────────


def test_dollar_math_autoclose_script_present():
    """Bug: $$ auto-close used broken command, plain Enter didn't work.

    The template must use CodeMirror.commands.newlineAndIndent (not the
    nonexistent newlineAndIndentContinueMarkdownList).
    """
    response = client.get("/edit")
    assert "CodeMirror.commands.newlineAndIndent" in response.text
    assert "newlineAndIndentContinueMarkdownList" not in response.text


def test_dollar_math_parity_check_present():
    """Bug: $$ auto-close triggered on closing markers too.

    Must count all $$ from doc start to cursor: odd = inside unclosed
    math → auto-close, even = between blocks → normal Enter.
    """
    response = client.get("/edit")
    assert "getRange" in response.text  # scans from doc start to cursor
    assert "totalDollars" in response.text
    assert "% 2" in response.text  # parity check


def test_dollar_math_cursor_position():
    """Bug: after auto-close, cursor ended after closing $$.

    Must call setCursor to place cursor on the indented middle line.
    """
    response = client.get("/edit")
    assert "setCursor" in response.text
    assert ".replaceSelection" in response.text


def test_math_restore_uses_split_join_not_replace():
    """Bug: String.replace() treats $$ as escape and $& as matched substring.

    Using .replace('MPH' + i, '...$$...') causes display math delimiters
    to collapse to single $ (inline), and $& in math content (e.g. LaTeX
    alignment) leaks the MPH placeholder into the rendered HTML.

    Must use .split('MPH' + i).join(...) to avoid all special-pattern
    interpretation in the replacement string.
    """
    response = client.get("/edit")
    html = response.text
    assert ".split('MPH'" in html or '.split("MPH"' in html, (
        "Math restore must use .split().join() instead of .replace() "
        "to avoid $$ escape and $& substitution"
    )
    assert ".join(" in html


# ── Regression tests for bugs fixed 2026-06-03/04 ─────────────────────────


def test_no_bare_javascript_outside_script_tags():
    """Bug: functions rendered as visible garbled text when outside <script>.

    Every <script> tag must have a matching </script>. Any JS between
    </script> and the next <script> is rendered as visible page text.
    """
    response = client.get("/edit")
    html = response.text
    opens = html.count("<script")
    closes = html.count("</script>")
    assert opens == closes, f"Unbalanced script tags: {opens} open vs {closes} close"


def test_editor_script_uses_iife():
    """Bug: DOMContentLoaded fires before inline script runs with local assets.

    The editor init script uses an IIFE (function(){...})() to run
    immediately without waiting for DOMContentLoaded.
    """
    response = client.get("/edit")
    assert "CodeMirror.fromTextArea" in response.text


def test_five_dimensional_scoring_is_mandatory():
    """Bug: 5D self-assessment was optional; users could submit without scoring.

    The template must label the fieldset as required and the submit handler
    must validate that all five dimensions have non-zero values.
    """
    response = client.get("/edit")
    assert "请完成五维自评" in response.text
    # Check all five dimensions have hidden inputs
    dims = ["self_originality", "self_rigor", "self_completeness", "self_pedagogy", "self_impact"]
    for d in dims:
        assert f'name="{d}"' in response.text, f"Missing mandatory dimension: {d}"


def test_no_yaml_frontmatter_template_in_editor():
    """Bug: editor pre-filled YAML frontmatter that duplicated the metadata form.

    The textarea should be empty by default — users fill the form below.
    """
    response = client.get("/edit")
    # The textarea content comes from Jinja2, not JS — for new articles
    # it should be empty (no default frontmatter)
    assert "---\\ntitle:" not in response.text


def test_codemirror_and_marked_loaded_locally():
    """Bug: CDN scripts failed to load in headless browser.

    CodeMirror and marked.js must be served from /static/, not external CDN.
    """
    response = client.get("/edit")
    assert "/static/codemirror/codemirror.js" in response.text
    assert "/static/codemirror/codemirror.css" in response.text
    assert "/static/codemirror/mode/markdown/markdown.js" in response.text
    assert "/static/marked.min.js" in response.text
    assert "cdn.jsdelivr.net" not in response.text
    assert "unpkg.com" not in response.text


def test_format_switch_present():
    """Markdown/Typst format selector must exist in the editor page."""
    response = client.get("/edit")
    assert 'id="format-select"' in response.text
    assert "Markdown" in response.text


def test_preview_has_math_delimiters():
    """KaTeX delimiters for inline $...$ and display $$...$$."""
    response = client.get("/edit")
    assert "renderMathInElement" in response.text
    assert "$$" in response.text


def test_editor_and_preview_separate_panes():
    """Bug: EasyMDE rendered markdown inside the editor.

    CodeMirror is a pure code editor — no markdown rendering.
    Preview is a separate div, updated via CodeMirror change event.
    """
    response = client.get("/edit")
    assert 'id="preview-pane"' in response.text
    assert 'CodeMirror.fromTextArea' in response.text
    assert "EasyMDE" not in response.text


def test_codemirror_container_sized():
    """CodeMirror wrapper must have width:50% to keep panes equal."""
    response = client.get("/edit")
    html = response.text
    assert '#editor-container .CodeMirror { width: 50%' in html.replace('; ', ';')
    assert 'flex-shrink: 0' in html


# ── Typst SVG preview compilation ─────────────────────────────────────────


def test_compile_preview_typst_svg():
    """POST /api/v1/compile-preview compiles Typst source to SVG."""
    if not __import__('shutil').which('typst'):
        __import__('pytest').skip('typst CLI not installed')
    response = client.post(
        '/api/v1/compile-preview',
        data={'source': '= Hello\n\nWorld.', 'format': 'typst'},
    )
    assert response.status_code == 200
    ct = response.headers.get('content-type', '')
    assert 'image/svg+xml' in ct or '<svg' in response.text


def test_compile_preview_typst_error():
    """POST /api/v1/compile-preview returns error HTML on invalid Typst."""
    if not __import__('shutil').which('typst'):
        __import__('pytest').skip('typst CLI not installed')
    response = client.post(
        '/api/v1/compile-preview',
        data={'source': '#invalid syntax!!!', 'format': 'typst'},
    )
    assert response.status_code == 200
    assert '编译错误' in response.text


def test_compile_preview_typst_debounce_logic_present():
    """Editor template has debounced Typst preview fetch."""
    response = client.get('/edit')
    assert 'compile-preview' in response.text
    assert 'typstTimer' in response.text


def test_preview_svg_constrained_to_container():
    """Bug: Typst SVG at A4 width (595pt) overflowed the preview pane.

    The SVG's natural width (~794px at 96dpi) was wider than the ~532px
    preview pane, making content in the right half of the A4 page appear
    pushed to the far right or clipped.

    Fix: CSS rule '#preview-pane svg { max-width: 100% }' constrains
    SVG to fit the container, preserving correct positioning.
    """
    response = client.get('/edit')
    html = response.text
    assert '#preview-pane svg' in html
    assert 'max-width: 100%' in html
    # SVG must also be block-level to avoid whitespace gaps
    assert 'display: block' in html


# ── Merge submit into editor ──────────────────────────────────────────────


def test_submit_redirects_to_edit():
    """GET /submit now redirects to /edit (unified editor)."""
    response = client.get('/submit', follow_redirects=False)
    assert response.status_code == 302
    assert '/edit' in response.headers.get('location', '')


# ── Regression: editor submit → submitted status + correct author ──────────


def test_editor_submit_enters_sedimentation_pool():
    """Bug: editor submissions defaulted to 'draft', never appeared in pool.

    create_article() used DRAFT as default status. Articles submitted via
    the editor skipped the sedimentation pool entirely. Fix: default to
    SUBMITTED so they go straight to /review.
    """
    import tempfile
    from pathlib import Path
    from peerpedia.config.settings import settings
    from peerpedia_core.storage.db import (
        get_engine, init_db, get_session, get_article, ArticleStatus,
    )

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        db_path = base / "test.db"
        articles_dir = base / "articles"
        articles_dir.mkdir()

        md = "---\ntitle: Pool Test\nabstract: Should go to pool.\n---\n\n# Test\n"
        original_url = settings.database_url
        settings.database_url = f"sqlite:///{db_path}"
        try:
            resp = client.post(
                "/api/v1/articles",
                data={
                    "title": "Pool Test",
                    "abstract": "Should go to pool.",
                    "format": "markdown",
                    "categories": "test",
                    "keywords": "test",
                    "language": "en",
                },
                files={"article_file": ("test.md", md.encode(), "text/plain")},
            )
            assert resp.status_code == 200
            aid = resp.json()["article_id"]

            engine = get_engine(f"sqlite:///{db_path}")
            init_db(engine)
            session = get_session(engine)
            article = get_article(session, aid)
            assert article.status == ArticleStatus.SUBMITTED, (
                f"Editor submission must be 'submitted' for "
                f"sedimentation pool, got '{article.status}'"
            )
            session.close()
        finally:
            settings.database_url = original_url


def test_editor_submit_uses_cookie_as_author():
    """Bug: editor always attributed articles to 'peerpedia'.

    The submit API didn't accept an author parameter, and the editor JS
    didn't send the viewer identity. All articles appeared as authored by
    'peerpedia' regardless of who was logged in.

    Fix: API accepts 'author' Form field, editor JS reads viewer cookie
    and sends it as 'author'.
    """
    import tempfile
    from pathlib import Path
    from peerpedia.config.settings import settings
    from peerpedia_core.storage.db import (
        get_engine, init_db, get_session, get_article, create_user,
    )

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        db_path = base / "test.db"
        articles_dir = base / "articles"
        articles_dir.mkdir()

        # Create the user in DB so it exists
        engine = get_engine(f"sqlite:///{db_path}")
        init_db(engine)
        session = get_session(engine)
        create_user(session, id="liqun", name="李群", email="liqun@test.com")
        session.commit()
        session.close()

        md = "---\ntitle: Author Test\n---\n\n# Test\n"
        original_url = settings.database_url
        settings.database_url = f"sqlite:///{db_path}"
        try:
            resp = client.post(
                "/api/v1/articles",
                data={
                    "title": "Author Test",
                    "format": "markdown",
                    "author": "liqun",
                },
                files={"article_file": ("test.md", md.encode(), "text/plain")},
            )
            assert resp.status_code == 200
            aid = resp.json()["article_id"]

            engine2 = get_engine(f"sqlite:///{db_path}")
            init_db(engine2)
            session2 = get_session(engine2)
            article = get_article(session2, aid)
            assert "liqun" in article.founding_authors, (
                f"Editor submission must use 'author' field as "
                f"founding author, got {article.founding_authors}"
            )
            session2.close()
        finally:
            settings.database_url = original_url


def test_editor_has_upload_button():
    """Editor page has file upload button for importing .typ/.md files."""
    response = client.get('/edit')
    assert '📂 上传' in response.text
    assert 'upload-input' in response.text
    assert 'upload-btn' in response.text
    assert 'FileReader' in response.text
    # Upload warning
    assert '替换编辑器' in response.text


def test_editor_no_more_separate_submit_link():
    """Nav bar no longer has a separate 提交 link (merged into 写作)."""
    response = client.get('/edit')
    assert 'href="/submit"' not in response.text


# ── Regression: Typst YAML frontmatter stripped ───────────────────────────


def test_typst_frontmatter_stripped_on_submit():
    """Bug: YAML frontmatter (---...---) rendered as visible content in Typst.

    Typst treats --- as an em-dash, so frontmatter blocks appeared in
    compiled output. Must strip before saving to git repo.
    """
    import tempfile
    from pathlib import Path
    from peerpedia.config.settings import settings
    from peerpedia_core.storage.db import get_engine, init_db, get_session, get_article, create_user

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        db_path = base / "test.db"
        articles_dir = base / "articles"
        articles_dir.mkdir()

        engine = get_engine(f"sqlite:///{db_path}")
        init_db(engine)
        session = get_session(engine)
        create_user(session, id="zhangliang", name="张量", email="z@test.com")
        session.commit()
        session.close()

        typst_src = "---\ntitle: My Article\n---\n\n= Heading\n\nContent."
        original_url = settings.database_url
        settings.database_url = f"sqlite:///{db_path}"
        try:
            resp = client.post(
                "/api/v1/articles",
                data={"title": "My Article", "format": "typst", "author": "zhangliang"},
                files={"article_file": ("article.typ", typst_src.encode(), "text/plain")},
            )
            assert resp.status_code == 200
            aid = resp.json()["article_id"]

            engine2 = get_engine(f"sqlite:///{db_path}")
            init_db(engine2)
            session2 = get_session(engine2)
            article = get_article(session2, aid)
            repo = Path(article.git_repo_path)
            source_files = list(repo.glob("*.typ"))
            assert source_files, "Should have source file"
            saved = source_files[0].read_text()
            # Frontmatter must NOT be in the saved file
            assert "---" not in saved, (
                f"Typst source must not contain YAML frontmatter: {saved[:200]}"
            )
            assert "= Heading" in saved, "Content after frontmatter must be preserved"
            session2.close()
        finally:
            settings.database_url = original_url


# ── Regression: button text ───────────────────────────────────────────────


def test_editor_button_update_when_editing():
    """Bug: editing existing article still showed '提交沉淀池'.

    When article_id is present (edit mode), the button must show
    '🔄 更新' instead of '🚀 提交沉淀池'.
    """
    import tempfile
    from pathlib import Path
    from peerpedia.config.settings import settings

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        db_path = base / "test.db"
        articles_dir = base / "articles"
        articles_dir.mkdir()

        md = "---\ntitle: Edit Test\n---\n\n# Test\n"
        original_url = settings.database_url
        settings.database_url = f"sqlite:///{db_path}"
        try:
            resp = client.post(
                "/api/v1/articles",
                data={"title": "Edit Test", "format": "markdown", "author": "zhangliang"},
                files={"article_file": ("test.md", md.encode(), "text/plain")},
            )
            aid = resp.json()["article_id"]

            # New editor (no article_id) → 提交沉淀池
            resp_new = client.get("/edit")
            assert "🚀 提交沉淀池" in resp_new.text
            assert "🔄 更新" not in resp_new.text

            # Edit existing article → 更新
            resp_edit = client.get(f"/edit/{aid}")
            assert "🔄 更新" in resp_edit.text
        finally:
            settings.database_url = original_url


# ── Regression: commit history shows +X −Y line counts ────────────────────


# ── Regression: version preview when clicking commit ────────────────────


def test_version_history_click_triggers_preview():
    """Bug: clicking a commit in version history shows nothing useful.

    The commit list must have onclick='loadVersion(...)' so clicking
    compiles and shows the version content in the right panel.
    """
    import tempfile
    from pathlib import Path
    from peerpedia.config.settings import settings

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        db_path = base / "test.db"
        articles_dir = base / "articles"
        articles_dir.mkdir()

        md = "---\ntitle: Version Preview Test\n---\n\n# Test\n"
        original_url = settings.database_url
        settings.database_url = f"sqlite:///{db_path}"
        try:
            resp = client.post(
                "/api/v1/articles",
                data={"title": "Version Preview Test", "format": "markdown",
                      "author": "zhangliang"},
                files={"article_file": ("test.md", md.encode(), "text/plain")},
            )
            aid = resp.json()["article_id"]

            # The commit history HTML must use loadVersion (not old loadDiff)
            resp_commits = client.get(f"/api/v1/articles/{aid}/commits/html")
            assert resp_commits.status_code == 200
            html = resp_commits.text
            assert "loadVersion" in html, (
                "Commit items must call loadVersion() to preview version content"
            )
            assert "loadDiff" not in html, (
                "Must use loadVersion, not old loadDiff"
            )
            # Must include article format so we know how to compile
            assert ".format" not in html or "article.format" in html or "loadVersion('" in html, (
                "loadVersion must receive article format to choose compilation method"
            )

            # The article page must have version-preview div for showing output
            resp_page = client.get(f"/article/{aid}")
            assert resp_page.status_code == 200
            assert 'version-preview' in resp_page.text, (
                "Article page must have #version-preview div for showing version content"
            )
            assert 'version-header' in resp_page.text, (
                "Article page must have #version-header for commit metadata"
            )
        finally:
            settings.database_url = original_url
