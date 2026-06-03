"""Tests for community five-dimension review."""
import pytest
import tempfile
from pathlib import Path

from peerpedia.submit import submit_article
from peerpedia_core.workflow.review import assign_reviewer, submit_review
from peerpedia_core.storage.db import (
    get_engine, init_db, get_session, get_article, get_reviews_for_article,
    update_article_status,
)


class TestCommunityReviewSubmit:
    """Community review 5-dimension ratings are stored correctly."""

    def test_review_with_all_five_dimensions(self):
        """Submit review with all 5 dimensions set, verify stored."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            db_path = base / "test.db"
            articles_dir = base / "articles"
            articles_dir.mkdir()

            source = base / "test.md"
            source.write_text("---\ntitle: Reviewed Article\n---\n\n# Test\n")

            result = submit_article(
                source_path=source, database_url=f"sqlite:///{db_path}",
                articles_dir=articles_dir,
            )
            engine = get_engine(f"sqlite:///{db_path}")
            init_db(engine)
            session = get_session(engine)
            update_article_status(session, result.article_id, "submitted")
            session.commit()
            session.close()

            assign_reviewer(article_id=result.article_id, reviewer_id="r1", database_url=f"sqlite:///{db_path}")
            review_result = submit_review(
                article_id=result.article_id, reviewer_id="r1",
                decision="accept", comments="Great.",
                review_originality=4, review_rigor=3,
                review_completeness=2, review_pedagogy=5, review_impact=1,
                database_url=f"sqlite:///{db_path}",
            )
            assert review_result.success is True

            session = get_session(engine)
            reviews = get_reviews_for_article(session, result.article_id)
            r = reviews[0]
            assert r.review_originality == 4
            assert r.review_rigor == 3
            assert r.review_completeness == 2
            assert r.review_pedagogy == 5
            assert r.review_impact == 1
            session.close()

    def test_review_without_dimensions_defaults_zero(self):
        """Submit review without dimensions — all default to 0."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            db_path = base / "test.db"
            articles_dir = base / "articles"
            articles_dir.mkdir()

            source = base / "test.md"
            source.write_text("---\ntitle: Unrated Review\n---\n\n# Test\n")

            result = submit_article(
                source_path=source, database_url=f"sqlite:///{db_path}",
                articles_dir=articles_dir,
            )
            engine = get_engine(f"sqlite:///{db_path}")
            init_db(engine)
            session = get_session(engine)
            update_article_status(session, result.article_id, "submitted")
            session.commit()
            session.close()

            assign_reviewer(article_id=result.article_id, reviewer_id="r1", database_url=f"sqlite:///{db_path}")
            submit_review(
                article_id=result.article_id, reviewer_id="r1",
                decision="accept", comments="No dimensions.",
                database_url=f"sqlite:///{db_path}",
            )

            session = get_session(engine)
            reviews = get_reviews_for_article(session, result.article_id)
            r = reviews[0]
            assert r.review_originality == 0
            assert r.review_rigor == 0
            assert r.review_completeness == 0
            assert r.review_pedagogy == 0
            assert r.review_impact == 0
            session.close()

    def test_review_to_dict_includes_dimensions(self):
        """Review.to_dict() includes all 5 review dimensions."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            db_path = base / "test.db"
            articles_dir = base / "articles"
            articles_dir.mkdir()

            source = base / "test.md"
            source.write_text("---\ntitle: Dict Test\n---\n\n# Test\n")
            result = submit_article(
                source_path=source, database_url=f"sqlite:///{db_path}",
                articles_dir=articles_dir,
            )
            engine = get_engine(f"sqlite:///{db_path}")
            init_db(engine)
            session = get_session(engine)
            update_article_status(session, result.article_id, "submitted")
            session.commit()
            session.close()

            assign_reviewer(article_id=result.article_id, reviewer_id="r1", database_url=f"sqlite:///{db_path}")
            submit_review(
                article_id=result.article_id, reviewer_id="r1",
                decision="accept", comments="OK",
                review_originality=5, review_rigor=5,
                review_completeness=5, review_pedagogy=5, review_impact=5,
                database_url=f"sqlite:///{db_path}",
            )

            session = get_session(engine)
            reviews = get_reviews_for_article(session, result.article_id)
            d = reviews[0].to_dict()
            assert d["review_originality"] == 5
            assert d["review_rigor"] == 5
            assert d["review_completeness"] == 5
            assert d["review_pedagogy"] == 5
            assert d["review_impact"] == 5
            session.close()


class TestCommunityReviewAPI:
    """API accepts 5-dimension review ratings."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from peerpedia.web.app import app
        return TestClient(app)

    def test_api_review_with_dimensions(self, client):
        """POST review with 5 dimensions stores them."""
        with tempfile.TemporaryDirectory() as tmp:
            from peerpedia.config.settings import settings

            base = Path(tmp)
            db_path = base / "test.db"
            articles_dir = base / "articles"
            articles_dir.mkdir()

            source = base / "test.md"
            source.write_text("---\ntitle: API Review Dims\n---\n\n# Test\n")

            result = submit_article(
                source_path=source, database_url=f"sqlite:///{db_path}",
                articles_dir=articles_dir,
            )
            engine = get_engine(f"sqlite:///{db_path}")
            init_db(engine)
            session = get_session(engine)
            update_article_status(session, result.article_id, "submitted")
            session.commit()
            session.close()

            original_url = settings.database_url
            settings.database_url = f"sqlite:///{db_path}"

            try:
                response = client.post(
                    f"/api/v1/articles/{result.article_id}/reviews",
                    data={
                        "reviewer_id": "reviewer1",
                        "decision": "accept",
                        "comments": "Good.",
                        "review_originality": "3",
                        "review_rigor": "4",
                        "review_completeness": "2",
                        "review_pedagogy": "5",
                        "review_impact": "1",
                    },
                )
                assert response.status_code == 200

                session = get_session(engine)
                reviews = get_reviews_for_article(session, result.article_id)
                r = reviews[0]
                assert r.review_originality == 3
                assert r.review_rigor == 4
                session.close()
            finally:
                settings.database_url = original_url


class TestCommunityReviewWebPages:
    """Article page shows community review comparison."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from peerpedia.web.app import app
        return TestClient(app)

    def test_article_page_shows_community_review(self, client):
        """Article page renders community review scores."""
        with tempfile.TemporaryDirectory() as tmp:
            from peerpedia.config.settings import settings

            base = Path(tmp)
            db_path = base / "test.db"
            articles_dir = base / "articles"
            articles_dir.mkdir()

            source = base / "test.md"
            source.write_text("---\ntitle: Community Review Page\n---\n\n# Test\n")

            result = submit_article(
                source_path=source, database_url=f"sqlite:///{db_path}",
                articles_dir=articles_dir,
            )
            engine = get_engine(f"sqlite:///{db_path}")
            init_db(engine)
            session = get_session(engine)
            update_article_status(session, result.article_id, "submitted")
            session.commit()
            session.close()

            # Submit a review with dimensions
            assign_reviewer(article_id=result.article_id, reviewer_id="r1", database_url=f"sqlite:///{db_path}")
            submit_review(
                article_id=result.article_id, reviewer_id="r1",
                decision="accept", comments="Good.",
                review_originality=4, review_rigor=3,
                review_completeness=2, review_pedagogy=5, review_impact=1,
                database_url=f"sqlite:///{db_path}",
            )

            original_url = settings.database_url
            settings.database_url = f"sqlite:///{db_path}"

            try:
                response = client.get(f"/article/{result.article_id}")
                assert response.status_code == 200
                assert "社区评分" in response.text
                assert "1人审稿" in response.text
            finally:
                settings.database_url = original_url

    def test_article_page_no_reviews_shows_placeholder(self, client):
        """Article page shows placeholder when no reviews exist."""
        with tempfile.TemporaryDirectory() as tmp:
            from peerpedia.config.settings import settings

            base = Path(tmp)
            db_path = base / "test.db"
            articles_dir = base / "articles"
            articles_dir.mkdir()

            source = base / "test.md"
            source.write_text("---\ntitle: No Reviews Yet\n---\n\n# Test\n")

            result = submit_article(
                source_path=source, database_url=f"sqlite:///{db_path}",
                articles_dir=articles_dir,
            )

            original_url = settings.database_url
            settings.database_url = f"sqlite:///{db_path}"

            try:
                response = client.get(f"/article/{result.article_id}")
                assert response.status_code == 200
                assert "社区审稿后此处显示评分对比" in response.text
            finally:
                settings.database_url = original_url
