"""CRUD operations for EditProposal and ContributionRecord models."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from peerpedia_core.storage.db.models import ContributionRecord, EditProposal

# ── ContributionRecord CRUD ─────────────────────────────────────────────────────

def create_contribution_record(
    session: Session,
    *,
    article_id: str,
    user_id: str,
    commit_hash: str,
    commit_message: str = "",
    lines_added: int = 0,
    lines_deleted: int = 0,
    files_changed: Optional[list[str]] = None,
    change_type: str = "content",
    contribution_weight: int = 0,
) -> ContributionRecord:
    """Create a contribution record."""
    record = ContributionRecord(
        id=str(uuid.uuid4()),
        article_id=article_id,
        user_id=user_id,
        commit_hash=commit_hash,
        commit_message=commit_message,
        lines_added=lines_added,
        lines_deleted=lines_deleted,
        files_changed=files_changed or [],
        change_type=change_type,
        contribution_weight=contribution_weight,
    )
    session.add(record)
    return record


def get_contribution_records(
    session: Session,
    article_id: str,
) -> list[ContributionRecord]:
    """Get all contribution records for an article, oldest first."""
    return (
        session.query(ContributionRecord)
        .filter(ContributionRecord.article_id == article_id)
        .order_by(ContributionRecord.timestamp.asc())
        .all()
    )


def get_user_contribution_total(
    session: Session,
    article_id: str,
    user_id: str,
) -> int:
    """Get total contribution weight for a user on an article."""
    result = (
        session.query(func.sum(ContributionRecord.contribution_weight))
        .filter(
            ContributionRecord.article_id == article_id,
            ContributionRecord.user_id == user_id,
        )
        .scalar()
    )
    return result or 0


# ── EditProposal CRUD ───────────────────────────────────────────────────────────

def create_edit_proposal(
    session: Session,
    *,
    article_id: str,
    proposer_id: str,
    proposal_type: str,
    description: str = "",
    git_branch: str = "",
    diff_stat: str = "",
    points_stake: int = 0,
) -> EditProposal:
    """Create an edit proposal record."""
    proposal = EditProposal(
        id=str(uuid.uuid4()),
        article_id=article_id,
        proposer_id=proposer_id,
        proposal_type=proposal_type,
        description=description,
        git_branch=git_branch,
        diff_stat=diff_stat,
        status="pending",
        points_stake=points_stake,
    )
    session.add(proposal)
    return proposal


def get_edit_proposal(session: Session, proposal_id: str) -> Optional[EditProposal]:
    """Get an edit proposal by ID."""
    return session.query(EditProposal).filter(EditProposal.id == proposal_id).first()


def get_edit_proposals_for_article(
    session: Session,
    article_id: str,
    *,
    status: Optional[str] = None,
) -> list[EditProposal]:
    """Get all edit proposals for an article, newest first."""
    q = (
        session.query(EditProposal)
        .filter(EditProposal.article_id == article_id)
        .order_by(EditProposal.created_at.desc())
    )
    if status:
        q = q.filter(EditProposal.status == status)
    return q.all()


def update_edit_proposal_status(
    session: Session,
    proposal_id: str,
    new_status: str,
    *,
    reviewer_id: Optional[str] = None,
    review_comment: str = "",
) -> Optional[EditProposal]:
    """Update an edit proposal's status."""
    proposal = get_edit_proposal(session, proposal_id)
    if proposal:
        proposal.status = new_status
        proposal.resolved_at = datetime.now(timezone.utc)
        if reviewer_id:
            proposal.reviewer_id = reviewer_id
        if review_comment:
            proposal.review_comment = review_comment
    return proposal
