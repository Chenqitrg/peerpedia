"""Tests for SQLAlchemy database layer."""
import pytest
import tempfile
from pathlib import Path
from datetime import datetime

from peerpedia_core.storage.db import (
    Article,
    ArticleStatus,
    Base,
    create_article,
    create_review,
    get_article,
    get_engine,
    get_review,
    get_reviews_for_article,
    get_session,
    init_db,
    list_articles,
    Review,
)


class TestArticleModel:
    """SQLAlchemy Article model must store and retrieve fields."""

    def test_article_table_creation(self):
        """init_db should create the articles table."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            engine = get_engine(f"sqlite:///{db_path}")
            init_db(engine)
            from sqlalchemy import inspect
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            assert "articles" in tables

    def test_create_and_get_article(self):
        """Create an article and retrieve it by ID."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            engine = get_engine(f"sqlite:///{db_path}")
            init_db(engine)
            session = get_session(engine)

            article = create_article(
                session,
                title="Test Article",
                founding_authors=["user-1"],
                abstract="A test abstract.",
                categories=["physics", "math"],
                keywords=["test"],
                language="en",
                format="typst",
                git_repo_path="/tmp/articles/test-1",
            )
            session.commit()

            assert article.id is not None
            assert article.title == "Test Article"
            assert article.status == ArticleStatus.DRAFT

            retrieved = get_article(session, article.id)
            assert retrieved is not None
            assert retrieved.title == "Test Article"
            assert retrieved.founding_authors == ["user-1"]
            assert retrieved.categories == ["physics", "math"]

    def test_list_articles(self):
        """list_articles should return all articles ordered by created_at desc."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            engine = get_engine(f"sqlite:///{db_path}")
            init_db(engine)
            session = get_session(engine)

            a1 = create_article(
                session, title="First", founding_authors=["u1"],
                abstract="First article.", git_repo_path="/tmp/a1",
            )
            a2 = create_article(
                session, title="Second", founding_authors=["u2"],
                abstract="Second article.", git_repo_path="/tmp/a2",
            )
            session.commit()

            articles = list_articles(session)
            assert len(articles) == 2
            assert articles[0].title == "Second"
            assert articles[1].title == "First"

    def test_list_articles_empty(self):
        """list_articles on empty DB returns empty list."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            engine = get_engine(f"sqlite:///{db_path}")
            init_db(engine)
            session = get_session(engine)

            articles = list_articles(session)
            assert articles == []

    def test_article_defaults(self):
        """Article model should have correct defaults."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            engine = get_engine(f"sqlite:///{db_path}")
            init_db(engine)
            session = get_session(engine)

            article = create_article(
                session,
                title="Defaults Test",
                founding_authors=["u1"],
                abstract="Testing defaults.",
                git_repo_path="/tmp/defaults",
            )
            session.commit()

            assert article.status == ArticleStatus.DRAFT
            assert article.version == "v0.1"
            assert article.language == "en"
            assert article.format == "typst"
            assert article.categories == []
            assert article.keywords == []
            assert article.cid is None
            assert article.pinned_by == 0
            assert isinstance(article.created_at, datetime)


class TestReviewModel:
    """Review model CRUD tests."""

    def test_create_review(self):
        """Create a review for an article."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            engine = get_engine(f"sqlite:///{db_path}")
            init_db(engine)
            session = get_session(engine)

            # First create an article
            article = create_article(
                session,
                title="Review Target",
                founding_authors=["author-1"],
                abstract="To be reviewed.",
                git_repo_path="/tmp/review-test",
            )
            session.commit()

            review = create_review(
                session,
                article_id=article.id,
                reviewer_id="reviewer-1",
                decision="accept",
                comments="Looks great.",
                scientific_correctness=5,
                clarity=4,
            )
            session.commit()

            assert review.id is not None
            assert review.article_id == article.id
            assert review.reviewer_id == "reviewer-1"
            assert review.decision == "accept"
            assert review.scientific_correctness == 5

    def test_get_reviews_for_article(self):
        """Get all reviews for a specific article."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            engine = get_engine(f"sqlite:///{db_path}")
            init_db(engine)
            session = get_session(engine)

            article = create_article(
                session,
                title="Multi-Review Article",
                founding_authors=["author-1"],
                abstract="Getting multiple reviews.",
                git_repo_path="/tmp/multi-review",
            )
            session.commit()

            r1 = create_review(session, article_id=article.id, reviewer_id="r1", decision="accept", comments="Good", scientific_correctness=4, clarity=4)
            r2 = create_review(session, article_id=article.id, reviewer_id="r2", decision="revise", comments="Needs work", scientific_correctness=3, clarity=3)
            session.commit()

            reviews = get_reviews_for_article(session, article.id)
            assert len(reviews) == 2
            assert reviews[0].reviewer_id == "r1"
            assert reviews[1].reviewer_id == "r2"

    def test_review_defaults(self):
        """Review should have correct default values."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            engine = get_engine(f"sqlite:///{db_path}")
            init_db(engine)
            session = get_session(engine)

            article = create_article(session, title="Default Test", founding_authors=["a1"], abstract="Test", git_repo_path="/tmp/defaults")
            session.commit()

            review = create_review(session, article_id=article.id, reviewer_id="r1", decision="accept", comments="OK")
            session.commit()

            assert review.scientific_correctness == 0
            assert review.clarity == 0
            assert review.collaboration_request == 0  # stored as Integer in SQLite
            assert review.points_earned == 0
