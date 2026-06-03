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
