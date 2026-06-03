"""Tests for five-dimension self-review feature."""
import pytest
import tempfile
from pathlib import Path

from peerpedia.submit import submit_article
from peerpedia_core.storage.db import get_engine, get_session, init_db, get_article


class TestSelfReviewSubmit:
    """Self-rating dimensions are stored correctly on submit."""

    def test_submit_with_all_self_ratings(self):
        """Submit article with all 5 self-ratings set, verify stored."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            db_path = base / "test.db"
            articles_dir = base / "articles"
            articles_dir.mkdir()

            source = base / "test.md"
            source.write_text("---\ntitle: Rated Article\nabstract: Test.\n---\n\n# Test\n")

            result = submit_article(
                source_path=source,
                database_url=f"sqlite:///{db_path}",
                articles_dir=articles_dir,
                self_originality=4,
                self_rigor=3,
                self_completeness=2,
                self_pedagogy=5,
                self_impact=1,
            )

            assert result.success is True
            assert result.self_originality == 4
            assert result.self_rigor == 3
            assert result.self_completeness == 2
            assert result.self_pedagogy == 5
            assert result.self_impact == 1

            # Verify in DB
            engine = get_engine(f"sqlite:///{db_path}")
            init_db(engine)
            session = get_session(engine)
            article = get_article(session, result.article_id)
            assert article.self_originality == 4
            assert article.self_rigor == 3
            assert article.self_completeness == 2
            assert article.self_pedagogy == 5
            assert article.self_impact == 1
            session.close()

    def test_submit_without_self_ratings_defaults_to_zero(self):
        """Submit article without self-ratings - all should be 0."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            db_path = base / "test.db"
            articles_dir = base / "articles"
            articles_dir.mkdir()

            source = base / "test.md"
            source.write_text("---\ntitle: Unrated Article\n---\n\n# Test\n")

            result = submit_article(
                source_path=source,
                database_url=f"sqlite:///{db_path}",
                articles_dir=articles_dir,
            )

            assert result.success is True
            assert result.self_originality == 0
            assert result.self_rigor == 0
            assert result.self_completeness == 0
            assert result.self_pedagogy == 0
            assert result.self_impact == 0

            engine = get_engine(f"sqlite:///{db_path}")
            init_db(engine)
            session = get_session(engine)
            article = get_article(session, result.article_id)
            assert article.self_originality == 0
            session.close()

    def test_to_dict_includes_self_ratings(self):
        """Article.to_dict() includes all self-rating fields."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            db_path = base / "test.db"
            articles_dir = base / "articles"
            articles_dir.mkdir()

            source = base / "test.md"
            source.write_text("---\ntitle: Dict Test\n---\n\n# Test\n")

            result = submit_article(
                source_path=source,
                database_url=f"sqlite:///{db_path}",
                articles_dir=articles_dir,
                self_originality=5, self_rigor=5,
                self_completeness=5, self_pedagogy=5, self_impact=5,
            )

            engine = get_engine(f"sqlite:///{db_path}")
            init_db(engine)
            session = get_session(engine)
            article = get_article(session, result.article_id)
            d = article.to_dict()
            assert d["self_originality"] == 5
            assert d["self_rigor"] == 5
            assert d["self_completeness"] == 5
            assert d["self_pedagogy"] == 5
            assert d["self_impact"] == 5
            assert d["forked_from"] is None
            session.close()


class TestSelfReviewAPI:
    """API accepts and returns self-rating fields."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from peerpedia.web.app import app
        return TestClient(app)

    def test_api_submit_with_self_ratings(self, client):
        """POST /api/v1/articles with self-rating fields stores them."""
        with tempfile.TemporaryDirectory() as tmp:
            from peerpedia.config.settings import settings

            base = Path(tmp)
            db_path = base / "test.db"
            articles_dir = base / "articles"
            articles_dir.mkdir()

            original_url = settings.database_url
            settings.database_url = f"sqlite:///{db_path}"

            try:
                md = "---\ntitle: API Self Review\nabstract: Testing API.\n---\n\n# Test\n"
                response = client.post(
                    "/api/v1/articles",
                    data={
                        "title": "API Self Review",
                        "abstract": "Testing API.",
                        "format": "markdown",
                        "self_originality": "3",
                        "self_rigor": "4",
                        "self_completeness": "2",
                        "self_pedagogy": "5",
                        "self_impact": "1",
                    },
                    files={"article_file": ("test.md", md.encode(), "text/markdown")},
                )
                assert response.status_code == 200
                data = response.json()
                aid = data["article_id"]

                from peerpedia_core.storage.db import get_engine, init_db, get_session, get_article
                engine = get_engine(f"sqlite:///{db_path}")
                init_db(engine)
                session = get_session(engine)
                article = get_article(session, aid)
                assert article.self_originality == 3
                assert article.self_rigor == 4
                assert article.self_completeness == 2
                assert article.self_pedagogy == 5
                assert article.self_impact == 1
                session.close()
            finally:
                settings.database_url = original_url


class TestSelfReviewWebPages:
    """Article page renders self-ratings."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from peerpedia.web.app import app
        return TestClient(app)

    def test_article_page_shows_self_ratings(self, client):
        """Article page renders self-rating display."""
        with tempfile.TemporaryDirectory() as tmp:
            from peerpedia.config.settings import settings

            base = Path(tmp)
            db_path = base / "test.db"
            articles_dir = base / "articles"
            articles_dir.mkdir()

            source = base / "test.md"
            source.write_text("---\ntitle: Rated Page Test\n---\n\n# Test\n")

            result = submit_article(
                source_path=source,
                database_url=f"sqlite:///{db_path}",
                articles_dir=articles_dir,
                self_originality=4, self_rigor=3,
                self_completeness=2, self_pedagogy=5, self_impact=1,
            )

            original_url = settings.database_url
            settings.database_url = f"sqlite:///{db_path}"

            try:
                response = client.get(f"/article/{result.article_id}")
                assert response.status_code == 200
                assert "作者自评" in response.text
                assert "self-review-display" in response.text
            finally:
                settings.database_url = original_url

    def test_article_page_shows_not_rated_when_all_zero(self, client):
        """Article page shows 'not rated' when all self-ratings are 0."""
        with tempfile.TemporaryDirectory() as tmp:
            from peerpedia.config.settings import settings

            base = Path(tmp)
            db_path = base / "test.db"
            articles_dir = base / "articles"
            articles_dir.mkdir()

            source = base / "test.md"
            source.write_text("---\ntitle: Unrated Page Test\n---\n\n# Test\n")

            result = submit_article(
                source_path=source,
                database_url=f"sqlite:///{db_path}",
                articles_dir=articles_dir,
            )

            original_url = settings.database_url
            settings.database_url = f"sqlite:///{db_path}"

            try:
                response = client.get(f"/article/{result.article_id}")
                assert response.status_code == 200
                assert "作者未自评" in response.text
            finally:
                settings.database_url = original_url
