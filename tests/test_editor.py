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
