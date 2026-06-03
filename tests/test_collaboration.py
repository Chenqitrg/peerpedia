"""Tests for collaboration workflow (Mode A: reviewer -> co-author)."""
import tempfile
import uuid
from pathlib import Path

from peerpedia_core.storage.db import (
    create_article,
    get_article,
    get_engine,
    get_session,
    init_db,
    update_article_status,
)
from peerpedia_core.workflow.collaboration import (
    accept_collaboration,
    get_collaboration_status,
)
from peerpedia_core.workflow.review import (
    submit_review,
)


def _create_article_in_review(db_url: str, article_id: str) -> None:
    """Create an article and set it to in_review status."""
    engine = get_engine(db_url)
    init_db(engine)
    session = get_session(engine)
    try:
        create_article(
            session,
            id=article_id,
            title="Test Article",
            founding_authors=["alice"],
            abstract="Test abstract",
            git_repo_path="/tmp/test",
        )
        session.commit()
        update_article_status(session, article_id, "in_review")
        session.commit()
    finally:
        session.close()


class TestCollaborationAccept:
    """Accepting collaboration requests."""

    def test_accept_collaboration_adds_co_author(self):
        """Accepting collaboration adds reviewer to founding_authors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_url = f"sqlite:///{Path(tmpdir) / 'test.db'}"
            article_id = str(uuid.uuid4())

            _create_article_in_review(db_url, article_id)

            submit_review(
                article_id=article_id,
                reviewer_id="bob",
                decision="revise",
                comments="Good work, I'd like to help improve.",
                collaboration_request=True,
                collaboration_message="I can improve the methods section.",
                database_url=db_url,
            )

            result = accept_collaboration(
                article_id=article_id,
                reviewer_id="bob",
                database_url=db_url,
            )

            assert result.success is True
            assert "bob" in result.founding_authors

            # Verify via a fresh session
            engine = get_engine(db_url)
            session = get_session(engine)
            article = get_article(session, article_id)
            assert "bob" in article.founding_authors
            session.close()

    def test_accept_collaboration_requires_collaboration_request(self):
        """Cannot accept if review didn't request collaboration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_url = f"sqlite:///{Path(tmpdir) / 'test.db'}"
            article_id = str(uuid.uuid4())

            _create_article_in_review(db_url, article_id)

            submit_review(
                article_id=article_id,
                reviewer_id="bob",
                decision="accept",
                comments="Looks great.",
                collaboration_request=False,
                database_url=db_url,
            )

            result = accept_collaboration(
                article_id=article_id,
                reviewer_id="bob",
                database_url=db_url,
            )

            assert result.success is False
            assert "collaboration" in result.error.lower()

    def test_accept_collaboration_nonexistent_article(self):
        """Accepting collaboration on nonexistent article fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_url = f"sqlite:///{Path(tmpdir) / 'test.db'}"
            engine = get_engine(db_url)
            init_db(engine)

            result = accept_collaboration(
                article_id="nonexistent",
                reviewer_id="bob",
                database_url=db_url,
            )
            assert result.success is False
            assert "not found" in result.error.lower()

    def test_accept_collaboration_nonexistent_reviewer(self):
        """Accepting collaboration from reviewer who never reviewed fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_url = f"sqlite:///{Path(tmpdir) / 'test.db'}"
            article_id = str(uuid.uuid4())

            _create_article_in_review(db_url, article_id)

            result = accept_collaboration(
                article_id=article_id,
                reviewer_id="charlie",
                database_url=db_url,
            )
            assert result.success is False

    def test_get_collaboration_status(self):
        """Get collaboration status returns correct info."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_url = f"sqlite:///{Path(tmpdir) / 'test.db'}"
            article_id = str(uuid.uuid4())

            _create_article_in_review(db_url, article_id)

            submit_review(
                article_id=article_id,
                reviewer_id="bob",
                decision="revise",
                comments="Needs work, I can help.",
                collaboration_request=True,
                collaboration_message="Let me fix the proofs.",
                database_url=db_url,
            )

            status = get_collaboration_status(
                article_id=article_id,
                reviewer_id="bob",
                database_url=db_url,
            )

            assert status["has_requested"] is True
            assert status["has_accepted"] is False
            assert status["message"] == "Let me fix the proofs."

    def test_get_collaboration_status_after_accept(self):
        """After acceptance, status shows accepted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_url = f"sqlite:///{Path(tmpdir) / 'test.db'}"
            article_id = str(uuid.uuid4())

            _create_article_in_review(db_url, article_id)

            submit_review(
                article_id=article_id,
                reviewer_id="bob",
                decision="revise",
                comments="Help",
                collaboration_request=True,
                collaboration_message="I can help.",
                database_url=db_url,
            )

            accept_collaboration(
                article_id=article_id,
                reviewer_id="bob",
                database_url=db_url,
            )

            status = get_collaboration_status(
                article_id=article_id,
                reviewer_id="bob",
                database_url=db_url,
            )
            assert status["has_requested"] is True
            assert status["has_accepted"] is True
