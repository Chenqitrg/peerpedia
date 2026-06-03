"""Tests for edit proposal workflow (Mode B: post-publication editing)."""
import tempfile
import uuid

import pytest

from peerpedia_core.storage.db import (
    create_article,
    get_article,
    get_engine,
    get_session,
    init_db,
    update_article_status,
)
from peerpedia_core.workflow.edit_proposal import (
    create_proposal,
    merge_proposal,
    review_proposal,
)


@pytest.fixture
def db_url():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield f"sqlite:///{tmpdir}/test.db"


@pytest.fixture
def published_article(db_url):
    """Create a published article for edit testing."""
    engine = get_engine(db_url)
    init_db(engine)
    session = get_session(engine)
    article_id = str(uuid.uuid4())
    create_article(
        session,
        id=article_id,
        title="Test Article",
        founding_authors=["alice"],
        abstract="An abstract.",
        git_repo_path="/tmp/test_proposal",
    )
    session.commit()
    update_article_status(session, article_id, "published")
    session.commit()
    session.close()
    return article_id


class TestCreateProposal:
    """Creating edit proposals."""

    def test_create_minor_proposal(self, db_url, published_article):
        """Create a minor edit proposal -- auto-approves."""
        result = create_proposal(
            article_id=published_article,
            proposer_id="bob",
            proposal_type="minor",
            description="Fixed a typo in section 1.",
            database_url=db_url,
        )

        assert result.success is True
        assert result.proposal_id is not None
        assert result.proposal_type == "minor"
        assert result.auto_approved is True

    def test_create_medium_proposal(self, db_url, published_article):
        """Create a medium edit proposal -- stays pending."""
        result = create_proposal(
            article_id=published_article,
            proposer_id="bob",
            proposal_type="medium",
            description="Rewrote the methods section.",
            database_url=db_url,
        )

        assert result.success is True
        assert result.auto_approved is False

    def test_create_major_proposal(self, db_url, published_article):
        """Create a major edit proposal."""
        result = create_proposal(
            article_id=published_article,
            proposer_id="bob",
            proposal_type="major",
            description="Added a new chapter.",
            database_url=db_url,
        )
        assert result.success is True
        assert result.proposal_type == "major"

    def test_create_proposal_nonexistent_article(self, db_url):
        """Cannot create proposal for nonexistent article."""
        result = create_proposal(
            article_id="nonexistent",
            proposer_id="bob",
            proposal_type="minor",
            description="Fix typo.",
            database_url=db_url,
        )
        assert result.success is False

    def test_create_proposal_non_published_article(self, db_url):
        """Cannot create proposal for non-published article."""
        engine = get_engine(db_url)
        init_db(engine)
        session = get_session(engine)
        article_id = str(uuid.uuid4())
        create_article(
            session, id=article_id, title="Draft",
            founding_authors=["alice"], abstract="Test",
            git_repo_path="/tmp/test",
        )
        session.commit()
        session.close()

        result = create_proposal(
            article_id=article_id, proposer_id="bob",
            proposal_type="minor", description="Fix.",
            database_url=db_url,
        )
        assert result.success is False
        assert "published" in result.error.lower()

    def test_invalid_proposal_type(self, db_url, published_article):
        """Invalid proposal type is rejected."""
        result = create_proposal(
            article_id=published_article, proposer_id="bob",
            proposal_type="huge", description="Big changes.",
            database_url=db_url,
        )
        assert result.success is False


class TestReviewProposal:
    """Reviewing edit proposals."""

    def test_approve_medium_proposal(self, db_url, published_article):
        """Approve a medium proposal."""
        create_result = create_proposal(
            article_id=published_article, proposer_id="bob",
            proposal_type="medium", description="Rewrote methods.",
            database_url=db_url,
        )

        result = review_proposal(
            proposal_id=create_result.proposal_id,
            reviewer_id="alice", decision="approve",
            comment="Good improvement.",
            database_url=db_url,
        )

        assert result.success is True
        assert result.new_status == "approved"

    def test_reject_proposal(self, db_url, published_article):
        """Reject a proposal."""
        create_result = create_proposal(
            article_id=published_article, proposer_id="bob",
            proposal_type="medium", description="Not needed.",
            database_url=db_url,
        )

        result = review_proposal(
            proposal_id=create_result.proposal_id,
            reviewer_id="alice", decision="reject",
            comment="This change is unnecessary.",
            database_url=db_url,
        )

        assert result.success is True
        assert result.new_status == "rejected"

    def test_cannot_review_auto_approved_proposal(self, db_url, published_article):
        """Cannot review an already auto-approved (minor) proposal."""
        create_result = create_proposal(
            article_id=published_article, proposer_id="bob",
            proposal_type="minor", description="Typo fix.",
            database_url=db_url,
        )

        result = review_proposal(
            proposal_id=create_result.proposal_id,
            reviewer_id="alice", decision="reject",
            comment="No.", database_url=db_url,
        )
        assert result.success is False

    def test_invalid_review_decision(self, db_url, published_article):
        """Invalid decision string is rejected."""
        create_result = create_proposal(
            article_id=published_article, proposer_id="bob",
            proposal_type="medium", description="Change.",
            database_url=db_url,
        )

        result = review_proposal(
            proposal_id=create_result.proposal_id,
            reviewer_id="alice", decision="maybe",
            comment="Hmm.", database_url=db_url,
        )
        assert result.success is False


class TestMergeProposal:
    """Merging approved proposals."""

    def test_merge_approved_proposal(self, db_url, published_article):
        """Merge an approved proposal updates article version."""
        create_result = create_proposal(
            article_id=published_article, proposer_id="bob",
            proposal_type="medium", description="Rewrote methods.",
            database_url=db_url,
        )
        review_proposal(
            proposal_id=create_result.proposal_id,
            reviewer_id="alice", decision="approve",
            comment="Good.", database_url=db_url,
        )

        result = merge_proposal(
            proposal_id=create_result.proposal_id,
            article_id=published_article, proposer_id="bob",
            repository_url="/tmp/test_proposal",
            database_url=db_url,
        )

        assert result.success is True
        assert result.new_version is not None
        assert result.new_version != "v0.1"
        assert result.contribution_record_id != ""

    def test_merge_auto_approved_minor_proposal(self, db_url, published_article):
        """Merge an auto-approved minor proposal works directly."""
        create_result = create_proposal(
            article_id=published_article, proposer_id="bob",
            proposal_type="minor", description="Typo fix.",
            database_url=db_url,
        )

        result = merge_proposal(
            proposal_id=create_result.proposal_id,
            article_id=published_article, proposer_id="bob",
            repository_url="/tmp/test_proposal",
            database_url=db_url,
        )

        assert result.success is True

    def test_cannot_merge_pending_proposal(self, db_url, published_article):
        """Cannot merge a pending (unreviewed) proposal."""
        create_result = create_proposal(
            article_id=published_article, proposer_id="bob",
            proposal_type="medium", description="Changes.",
            database_url=db_url,
        )

        result = merge_proposal(
            proposal_id=create_result.proposal_id,
            article_id=published_article, proposer_id="bob",
            repository_url="/tmp/test_proposal",
            database_url=db_url,
        )

        assert result.success is False

    def test_merge_adds_proposer_as_coauthor(self, db_url, published_article):
        """Merging a proposal adds proposer to founding_authors."""
        create_result = create_proposal(
            article_id=published_article, proposer_id="bob",
            proposal_type="minor", description="Typo fix.",
            database_url=db_url,
        )

        merge_proposal(
            proposal_id=create_result.proposal_id,
            article_id=published_article, proposer_id="bob",
            repository_url="/tmp/test_proposal",
            database_url=db_url,
        )

        engine = get_engine(db_url)
        init_db(engine)
        session = get_session(engine)
        article = get_article(session, published_article)
        assert "bob" in article.founding_authors
        session.close()
