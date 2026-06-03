"""Tests for user profile page."""
import tempfile
from pathlib import Path

from peerpedia.submit import submit_article
from peerpedia_core.storage.db import (
    Article,
    create_review,
    get_engine,
    get_session,
    init_db,
)


class TestUserActivity:
    """User activity queries."""

    def test_user_authored_articles(self):
        """Find articles by a specific user."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            db_path = base / "test.db"
            articles_dir = base / "articles"
            articles_dir.mkdir()
            db_url = f"sqlite:///{db_path}"

            source = base / "test.typ"
            source.write_text("""---
title: User Test Article
abstract: Testing user queries.
---

= User Test

Content.
""")
            result = submit_article(
                source_path=source,
                database_url=db_url,
                articles_dir=articles_dir,
                author_name="user-alice",
            )
            assert result.success

            # Query articles by founding author
            engine = get_engine(db_url)
            init_db(engine)
            session = get_session(engine)
            articles = (
                session.query(Article)
                .filter(Article.founding_authors.contains("user-alice"))
                .all()
            )
            assert len(articles) == 1
            assert articles[0].title == "User Test Article"
            session.close()

    def test_user_scoring_includes_review_points(self):
        """User earns points from reviews."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            db_path = base / "test.db"
            articles_dir = base / "articles"
            articles_dir.mkdir()
            db_url = f"sqlite:///{db_path}"

            source = base / "test.typ"
            source.write_text("""---
title: Review Target
abstract: For review.
---

= Review Target

Content.
""")
            result = submit_article(source_path=source, database_url=db_url, articles_dir=articles_dir)
            assert result.success

            engine = get_engine(db_url)
            init_db(engine)
            session = get_session(engine)

            # Create reviews for different reviewers
            r1 = create_review(session, article_id=result.article_id, reviewer_id="alice", decision="accept", comments="OK", points_earned=20)
            r2 = create_review(session, article_id=result.article_id, reviewer_id="bob", decision="revise", comments="Fix", points_earned=20)
            session.commit()

            # Sum alice's points
            from peerpedia_core.storage.db import Review
            alice_reviews = session.query(Review).filter(Review.reviewer_id == "alice").all()
            alice_points = sum(r.points_earned for r in alice_reviews)
            assert alice_points == 20

            bob_reviews = session.query(Review).filter(Review.reviewer_id == "bob").all()
            bob_points = sum(r.points_earned for r in bob_reviews)
            assert bob_points == 20
            session.close()

    def test_mirrored_articles_tracked(self):
        """Mirrored articles should have mirror_by set."""
        # Uses the mirror module
        from unittest.mock import patch

        from peerpedia.mirror import ArxivMetadata, mirror_arxiv

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            db_path = base / "test.db"
            articles_dir = base / "articles"
            articles_dir.mkdir()
            db_url = f"sqlite:///{db_path}"

            with patch("peerpedia.mirror.fetch_arxiv_metadata") as mock_fetch:
                mock_fetch.return_value = ArxivMetadata(
                    arxiv_id="2301.00001",
                    title="Test Mirror Paper",
                    abstract="Test.",
                    authors=["John Smith"],
                    categories=["quant-ph"],
                    published_date="2023-01-01",
                    pdf_url="https://arxiv.org/pdf/2301.00001",
                )
                result = mirror_arxiv(
                    arxiv_id="2301.00001",
                    mirror_user_id="user-alice",
                    database_url=db_url,
                    articles_dir=articles_dir,
                )
                assert result.success
                assert result.mirror_points == 5

            # Query mirrored articles
            engine = get_engine(db_url)
            init_db(engine)
            session = get_session(engine)
            mirrored = session.query(Article).filter(Article.mirror_by == "user-alice").all()
            assert len(mirrored) == 1
            assert mirrored[0].source_arxiv_id == "2301.00001"
            session.close()
