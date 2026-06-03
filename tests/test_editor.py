"""Tests for the online editor."""

from fastapi.testclient import TestClient

from peerpedia.web.app import app

client = TestClient(app)


def test_edit_page_loads():
    """GET /edit returns the editor page with Monaco."""
    response = client.get("/edit")
    assert response.status_code == 200
    assert "monaco-editor" in response.text
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
            assert "monaco-editor" in response.text
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


# ── Monaco auto-close tests ────────────────────────────────────────────────


def test_monaco_autoclose_dollar_math():
    """Monaco autoClosingPairs handles $$ auto-close natively.

    No custom Enter handler needed — Monaco's built-in autoClosingPairs
    with {open:'$$', close:'$$'} handles insertion, cursor placement,
    and overtype skip automatically.
    """
    response = client.get("/edit")
    assert "autoClosingPairs" in response.text
    assert "'$$'" in response.text or '"$$"' in response.text
    # No custom CodeMirror Enter logic
    assert "CodeMirror.commands" not in response.text


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
    """Monaco editor init uses an IIFE to run immediately.

    The editor init script uses (function(){...})() to run
    immediately without waiting for DOMContentLoaded.
    """
    response = client.get("/edit")
    assert "monaco.editor.create" in response.text
    assert "(function()" in response.text


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


def test_monaco_cdn_and_marked_local():
    """Monaco loaded from CDN (dev), marked.js served locally.

    Monaco is loaded via jsdelivr CDN during development. marked.js
    continues to be served from /static/.
    """
    response = client.get("/edit")
    assert "/static/marked.min.js" in response.text
    assert "cdn.jsdelivr.net/npm/monaco-editor" in response.text
    assert "/static/codemirror/" not in response.text


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
    """Monaco editor and preview are separate panes.

    Monaco renders into a dedicated div, preview is a separate div
    updated via Monaco's onDidChangeModelContent event.
    """
    response = client.get("/edit")
    assert 'id="preview-pane"' in response.text
    assert 'id="monaco-editor"' in response.text
    assert "CodeMirror" not in response.text
    assert "EasyMDE" not in response.text


def test_monaco_container_sized():
    """Monaco container uses flex:1 for equal 50/50 split with preview."""
    response = client.get("/edit")
    html = response.text
    assert 'id="monaco-editor"' in html
    assert 'flex: 1' in html


# ── Monaco-specific tests ──────────────────────────────────────────────────


def test_monaco_theme_toggle_present():
    """Editor page has a theme toggle button for vs/vs-dark."""
    response = client.get("/edit")
    assert "peerpedia-md-dark" in response.text
    assert "setTheme" in response.text


def test_monaco_shortcuts_registered():
    """Editor registers Ctrl+B/I/K shortcuts via addAction."""
    response = client.get("/edit")
    assert "addAction" in response.text
    assert "KeyMod.CtrlCmd" in response.text


def test_monaco_sync_scroll_present():
    """Editor has bidirectional scroll sync with preview."""
    response = client.get("/edit")
    assert "onDidScrollChange" in response.text
    assert "scrollTop" in response.text


def test_monaco_peerpedia_completion():
    """Editor registers a custom completion provider for peerpedia: refs."""
    response = client.get("/edit")
    assert "registerCompletionItemProvider" in response.text
    assert "peerpedia:" in response.text


def test_monaco_markdown_language_set():
    """Editor initializes with markdown language and custom tokenizer."""
    response = client.get("/edit")
    assert "'markdown'" in response.text or '"markdown"' in response.text
    assert "setMonarchTokensProvider" in response.text
    assert "defineTheme" in response.text


# ── Regression: math rendering ────────────────────────────────────────────


def test_math_restore_escapes_dollar_in_replace():
    """Bug: String.replace() treats $$ as escape, stripping display math.

    The restore code uses .replace('MPH' + i, '...$$...'), and
    String.replace interprets $$ as an escaped $ (inserts one $).
    Must use $$$$ (four) to produce $$ (two) in output.

    Verify the template uses $$$$ for display-math delimiters in
    the restore step.
    """
    response = client.get("/edit")
    html = response.text
    # The restore code must use $$$$ (not bare $$) for display math
    assert "$$$$" in html, (
        "Template must use $$$$ in String.replace to produce $$ in output"
    )
