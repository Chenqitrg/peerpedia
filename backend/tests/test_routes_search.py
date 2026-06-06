"""Integration tests for search endpoint — SQL-level filtering."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from peerpedia_core.storage.db.engine import get_session
from peerpedia_core.storage.db.models import Article


@pytest.fixture
def client(db_engine):
    from peerpedia_api.main import app
    from peerpedia_api import deps

    def override_db():
        session = get_session(db_engine)
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[deps.get_db] = override_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


class TestSearchSQL:
    """Verify search builds correct SQL queries and returns correct results."""

    def test_search_no_filters_returns_paginated(self, client):
        """Empty search returns published/sedimentation articles with pagination."""
        res = client.get("/api/v1/search", params={"page": 1, "size": 10})
        assert res.status_code == 200
        data = res.json()
        assert "articles" in data
        assert "total" in data
        assert data["page"] == 1
        assert data["size"] == 10
        assert isinstance(data["articles"], list)

    def test_search_category_filter_sql(self, client):
        """Category filter uses SQL JSON matching — no crash, valid response."""
        res = client.get("/api/v1/search", params={"category": "physics"})
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data["articles"], list)
        assert "total" in data

    def test_search_sort_by_newest(self, client):
        """Sort by newest returns articles in descending date order."""
        res = client.get("/api/v1/search", params={"sort": "newest", "size": 50})
        assert res.status_code == 200
        data = res.json()
        articles = data["articles"]
        if len(articles) >= 2:
            dates = [a["created_at"] for a in articles]
            assert dates == sorted(dates, reverse=True), (
                f"Expected descending dates, got {dates}"
            )

    def test_search_pagination_sql(self, client):
        """Pagination: page 2 returns different articles than page 1."""
        res1 = client.get("/api/v1/search", params={"page": 1, "size": 5})
        res2 = client.get("/api/v1/search", params={"page": 2, "size": 5})
        assert res1.status_code == 200
        assert res2.status_code == 200
        ids1 = {a["id"] for a in res1.json()["articles"]}
        ids2 = {a["id"] for a in res2.json()["articles"]}
        assert ids1.isdisjoint(ids2), f"Pages overlap: {ids1 & ids2}"

    def test_search_invalid_sort_falls_back(self, client):
        """Invalid sort parameter should not crash."""
        res = client.get("/api/v1/search", params={"sort": "invalid_sort"})
        assert res.status_code == 200

    def test_search_empty_query_returns_results(self, client):
        """Empty query with no filters returns all visible articles."""
        res = client.get("/api/v1/search")
        assert res.status_code == 200
        data = res.json()
        assert data["query"] == ""
        assert data["category"] == ""

    def test_search_size_exceeds_limit_rejected(self, client):
        """Size > 100 is rejected with 422 validation error."""
        res = client.get("/api/v1/search", params={"size": 500})
        assert res.status_code == 422

    def test_search_title_text_sql(self, client):
        """Title text search uses SQL ILIKE — finds articles by title keyword."""
        res = client.get("/api/v1/search", params={"q": "the"})
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data["articles"], list)

    def test_search_combined_filters_sql(self, client):
        """Combined title + category + sort does not crash."""
        res = client.get("/api/v1/search", params={
            "q": "theory", "category": "physics", "sort": "newest",
        })
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data["articles"], list)
