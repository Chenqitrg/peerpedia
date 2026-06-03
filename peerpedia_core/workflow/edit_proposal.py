"""Layer 1: Edit proposal workflow (Mode B: post-publication open editing).

Handles the full lifecycle of post-publication edit proposals:
    create -> review -> merge -> contribution record updated
"""

from __future__ import annotations

from dataclasses import dataclass

from peerpedia_core.storage.db import (
    create_contribution_record,
    create_edit_proposal,
    get_article,
    get_edit_proposal,
    update_article_founding_authors,
    update_article_status,
    update_article_version,
    update_edit_proposal_status,
)
from peerpedia_core.storage.db.session_utils import db_session_scope
from peerpedia_core.workflow.contribution import compute_change_type_weight
from peerpedia_core.workflow.state_machine import ArticleStatus
from peerpedia_core.workflow.versioning import bump_minor_version

VALID_PROPOSAL_TYPES = {"minor", "medium", "major"}


# -- Result types -----------------------------------------------------------------

@dataclass
class CreateProposalResult:
    success: bool
    proposal_id: str = ""
    article_id: str = ""
    proposal_type: str = ""
    auto_approved: bool = False
    error: str = ""


@dataclass
class ReviewProposalResult:
    success: bool
    proposal_id: str = ""
    new_status: str = ""
    error: str = ""


@dataclass
class MergeProposalResult:
    success: bool
    proposal_id: str = ""
    article_id: str = ""
    new_version: str = ""
    contribution_record_id: str = ""
    error: str = ""


# -- Create proposal --------------------------------------------------------------

def create_proposal(
    article_id: str,
    proposer_id: str,
    proposal_type: str,
    description: str,
    *,
    database_url: str,
    git_branch: str = "",
    diff_stat: str = "",
) -> CreateProposalResult:
    """Create a new edit proposal on a published article.

    Minor proposals auto-approve. Medium and major stay pending for review.
    """
    if proposal_type not in VALID_PROPOSAL_TYPES:
        return CreateProposalResult(
            success=False,
            error=f"Invalid proposal type '{proposal_type}'. Must be one of: {', '.join(sorted(VALID_PROPOSAL_TYPES))}",
        )

    try:
        with db_session_scope(database_url) as session:
            article = get_article(session, article_id)
            if article is None:
                return CreateProposalResult(
                    success=False,
                    article_id=article_id,
                    error="Article not found",
                )

            if article.status != ArticleStatus.PUBLISHED:
                return CreateProposalResult(
                    success=False,
                    article_id=article_id,
                    error=f"Article must be 'published' to accept edit proposals (current: '{article.status}')",
                )

            auto_approved = proposal_type == "minor"
            status = "auto_approved" if auto_approved else "pending"

            # Transition article: published -> edit_proposed (for medium/major)
            if not auto_approved:
                update_article_status(session, article_id, ArticleStatus.EDIT_PROPOSED)

            proposal = create_edit_proposal(
                session,
                article_id=article_id,
                proposer_id=proposer_id,
                proposal_type=proposal_type,
                description=description,
                git_branch=git_branch,
                diff_stat=diff_stat,
            )
            proposal.status = status

            return CreateProposalResult(
                success=True,
                proposal_id=proposal.id,
                article_id=article_id,
                proposal_type=proposal_type,
                auto_approved=auto_approved,
            )
    except Exception as e:
        return CreateProposalResult(
            success=False,
            article_id=article_id,
            error=str(e),
        )


# -- Review proposal --------------------------------------------------------------

def review_proposal(
    proposal_id: str,
    reviewer_id: str,
    decision: str,
    comment: str = "",
    *,
    database_url: str,
) -> ReviewProposalResult:
    """Review an edit proposal (approve or reject).

    Only pending proposals can be reviewed. Auto-approved proposals skip this step.
    """
    if decision not in ("approve", "reject"):
        return ReviewProposalResult(
            success=False,
            proposal_id=proposal_id,
            error=f"Decision must be 'approve' or 'reject', got '{decision}'",
        )

    try:
        with db_session_scope(database_url) as session:
            proposal = get_edit_proposal(session, proposal_id)
            if proposal is None:
                return ReviewProposalResult(
                    success=False,
                    proposal_id=proposal_id,
                    error="Proposal not found",
                )

            if proposal.status != "pending":
                return ReviewProposalResult(
                    success=False,
                    proposal_id=proposal_id,
                    error=f"Cannot review proposal with status '{proposal.status}'. Only 'pending' proposals can be reviewed.",
                )

            new_status = "approved" if decision == "approve" else "rejected"
            update_edit_proposal_status(
                session,
                proposal_id,
                new_status,
                reviewer_id=reviewer_id,
                review_comment=comment,
            )

            return ReviewProposalResult(
                success=True,
                proposal_id=proposal_id,
                new_status=new_status,
            )
    except Exception as e:
        return ReviewProposalResult(
            success=False,
            proposal_id=proposal_id,
            error=str(e),
        )


# -- Merge proposal ---------------------------------------------------------------

def merge_proposal(
    proposal_id: str,
    article_id: str,
    proposer_id: str,
    *,
    repository_url: str,
    database_url: str,
    change_type: str = "content",
) -> MergeProposalResult:
    """Merge an approved (or auto-approved) proposal.

    This:
    1. Validates proposal is approved/auto_approved
    2. Updates article version
    3. Transitions article status back to published
    4. Creates a contribution record for the proposer
    5. Adds proposer as co-author if not already
    """
    try:
        with db_session_scope(database_url) as session:
            proposal = get_edit_proposal(session, proposal_id)
            if proposal is None:
                return MergeProposalResult(
                    success=False,
                    proposal_id=proposal_id,
                    error="Proposal not found",
                )

            if proposal.status not in ("approved", "auto_approved"):
                return MergeProposalResult(
                    success=False,
                    proposal_id=proposal_id,
                    error=f"Proposal has not been approved (status: '{proposal.status}')",
                )

            article = get_article(session, article_id)
            if article is None:
                return MergeProposalResult(
                    success=False,
                    error="Article not found",
                )

            # Bump version
            new_version = bump_minor_version(article.version or "v0.1")

            update_article_version(session, article_id, new_version)

            # Transition status back to published (if currently in edit_proposed)
            if article.status == ArticleStatus.EDIT_PROPOSED:
                update_article_status(session, article_id, ArticleStatus.PUBLISHED)

            # Create contribution record
            weight = compute_change_type_weight(change_type)
            contribution = create_contribution_record(
                session,
                article_id=article_id,
                user_id=proposer_id,
                commit_hash="pending",
                commit_message=f"Edit proposal: {proposal.description[:80]}",
                lines_added=0,
                lines_deleted=0,
                change_type=change_type,
                contribution_weight=weight,
            )

            # Add proposer as co-author if not already
            update_article_founding_authors(session, article_id, proposer_id)

            return MergeProposalResult(
                success=True,
                proposal_id=proposal_id,
                article_id=article_id,
                new_version=new_version,
                contribution_record_id=contribution.id,
            )
    except Exception as e:
        return MergeProposalResult(
            success=False,
            proposal_id=proposal_id,
            error=str(e),
        )
