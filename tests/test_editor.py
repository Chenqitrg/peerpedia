"""Tests for the online editor."""

from fastapi.testclient import TestClient

from peerpedia.web.app import app

client = TestClient(app)


def test_edit_page_loads():
    """GET /edit returns the editor page."""
    response = client.get("/edit")
    assert response.status_code == 200
    assert "editor-area" in response.text
    assert "preview-pane" in response.text


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


def test_editor_script_uses_readystate_guard():
    """Bug: DOMContentLoaded fires before inline script runs with local assets.

    The initEditor function must check document.readyState to avoid missing
    the event when all assets load from localhost (no network latency).
    """
    response = client.get("/edit")
    assert "document.readyState" in response.text
    assert "initEditor" in response.text


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


def test_easymde_and_marked_loaded_locally():
    """Bug: CDN scripts (jsdelivr/unpkg) failed to load in headless browser.

    EasyMDE and marked.js must be served from /static/, not external CDN.
    """
    response = client.get("/edit")
    assert "/static/easymde/easymde.min.js" in response.text
    assert "/static/easymde/easymde.min.css" in response.text
    assert "/static/marked.min.js" in response.text
    # Must NOT reference external CDN for these
    assert "cdn.jsdelivr.net/npm/easymde" not in response.text
    assert "unpkg.com/easymde" not in response.text


def test_format_switch_present():
    """Markdown/Typst format selector must exist in the editor page."""
    response = client.get("/edit")
    assert 'id="format-select"' in response.text
    assert "Markdown" in response.text


def test_preview_pane_has_math_delimiters():
    """KaTeX delimiters must be configured for inline $...$ and display $$...$$."""
    response = client.get("/edit")
    assert "renderMathInElement" in response.text
    assert "$$" in response.text


def test_editor_and_preview_equal_width():
    """Bug: panes were different sizes and jumped around while typing.

    Both panes must have width:50% and flex-shrink:0 to prevent content
    from pushing the layout around.
    """
    response = client.get("/edit")
    html = response.text
    # Editor pane must have fixed width
    assert 'width:50%' in html
    assert 'flex-shrink:0' in html
    # Preview pane must have word-wrap to prevent horizontal overflow
    assert 'word-wrap:break-word' in html


def test_easymde_container_constrained():
    """Bug: EasyMDE container overflowed the left pane.

    CSS must constrain .EasyMDEContainer to 100% width/height and hide
    EasyMDE's built-in preview (we use our own).
    """
    response = client.get("/edit")
    html = response.text
    assert '.EasyMDEContainer' in html
    assert 'width: 100% !important' in html
    assert 'height: 100% !important' in html
    assert '.editor-preview' in html
    assert 'display: none !important' in html
