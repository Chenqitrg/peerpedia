"""Layer 1: Collaboration workflow (Mode A: reviewer -> co-author).

Handles the reviewer-to-coauthor transition during peer review.
When an author accepts a review's collaboration request, the reviewer
becomes a co-author and can contribute directly via git branches.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from peerpedia_core.storage.db import (
    get_article,
    get_engine,
    get_reviews_for_article,
    get_session,
    init_db,
    update_article_founding_authors,
)


@dataclass
class CollaborationResult:
    """Result of accepting a collaboration request."""
    success: bool
    article_id: str = ""
    reviewer_id: str = ""
    founding_authors: list[str] = field(default_factory=list)
    error: str = ""


def accept_collaboration(
    article_id: str,
    reviewer_id: str,
    *,
    database_url: str,
) -> CollaborationResult:
    """Accept a reviewer's collaboration request. Adds reviewer as co-author.

    The reviewer must have submitted a review with collaboration_request=True
    for this article.
    """
    engine = get_engine(database_url)
    init_db(engine)
    session = get_session(engine)

    try:
        article = get_article(session, article_id)
        if article is None:
            return CollaborationResult(
                success=False,
                article_id=article_id,
                error="Article not found",
            )

        # Check reviewer has a collaboration request
        reviews = get_reviews_for_article(session, article_id)
        collab_review = None
        for r in reviews:
            if r.reviewer_id == reviewer_id and r.collaboration_request:
                collab_review = r
                break

        if collab_review is None:
            return CollaborationResult(
                success=False,
                article_id=article_id,
                reviewer_id=reviewer_id,
                error=f"Reviewer '{reviewer_id}' has not requested collaboration on this article",
            )

        # Add reviewer as co-author
        update_article_founding_authors(session, article_id, reviewer_id)
        session.commit()

        # Re-read to get updated authors
        updated = get_article(session, article_id)
        return CollaborationResult(
            success=True,
            article_id=article_id,
            reviewer_id=reviewer_id,
            founding_authors=list(updated.founding_authors) if updated else [],
        )
    except Exception as e:
        session.rollback()
        return CollaborationResult(
            success=False,
            article_id=article_id,
            error=str(e),
        )
    finally:
        session.close()


def get_collaboration_status(
    article_id: str,
    reviewer_id: str,
    *,
    database_url: str,
) -> dict:
    """Get the collaboration status for a reviewer on an article.

    Returns:
        Dict with keys: has_requested, has_accepted, message, reviewer_id, article_id.
    """
    engine = get_engine(database_url)
    init_db(engine)
    session = get_session(engine)

    try:
        article = get_article(session, article_id)
        has_accepted = reviewer_id in (article.founding_authors if article else [])

        reviews = get_reviews_for_article(session, article_id)
        has_requested = False
        message = ""
        for r in reviews:
            if r.reviewer_id == reviewer_id and r.collaboration_request:
                has_requested = True
                message = r.collaboration_message
                break

        return {
            "reviewer_id": reviewer_id,
            "article_id": article_id,
            "has_requested": has_requested,
            "has_accepted": has_accepted,
            "message": message,
        }
    finally:
        session.close()
