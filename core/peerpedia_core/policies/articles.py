# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Article permission policy — centralized visibility and authorization.

Every read/write endpoint must call the appropriate ``assert_can_*``
function instead of duplicating ``current_user.id in get_author_ids(...)``
checks.

All functions raise semantic exceptions from ``peerpedia_core.exceptions``
— no HTTP dependency. Backend routes rely on the ``PeerpediaError`` handler
in ``main.py`` to translate to HTTP status codes.
"""

from __future__ import annotations

from typing import Optional

import git as gitmod
from sqlalchemy.orm import Session

from peerpedia_core.exceptions import BadRequestError, ConflictError, NotAuthorizedError, NotFoundError
from peerpedia_core.storage.db.crud_article import get_article, get_author_ids
from peerpedia_core.storage.db.models import Article, User

# ═══════════════════════════════════════════════════════════════════════════════
# Visibility rules
# ═══════════════════════════════════════════════════════════════════════════════

# Statuses readable by anyone (unauthenticated included).
PUBLIC_READABLE_STATUSES = {"sedimentation", "published"}

# Only published articles can be forked.
FORKABLE_STATUSES = {"published"}

# Only published articles can be downloaded as a full git repo.
# (Pool / sedimentation cannot be forked, so repo download is author-only.)
REPO_DOWNLOADABLE_STATUSES = {"published"}


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def get_article_or_raise(db: Session, article_id: str) -> Article:
    a = get_article(db, article_id)
    if a is None:
        raise NotFoundError("Article not found")
    return a


def _is_author(db: Session, article_id: str, user: Optional[User]) -> bool:
    if user is None:
        return False
    return user.id in get_author_ids(db, article_id)


def visible_statuses_for_user(current_user: Optional[User]) -> set[str]:
    """Return the set of statuses visible to *current_user*.

    Anonymous users see ``sedimentation`` + ``published``.
    Authenticated users additionally see their own ``draft`` articles
    (the caller must still filter by author for drafts).
    """
    if current_user is not None:
        return {"draft", "sedimentation", "published"}
    return {"sedimentation", "published"}


# ═══════════════════════════════════════════════════════════════════════════════
# Read permissions
# ═══════════════════════════════════════════════════════════════════════════════


def assert_can_read_article(
    db: Session,
    article_id: str,
    current_user: Optional[User],
) -> Article:
    """Raise if *current_user* is not allowed to read this article."""
    a = get_article_or_raise(db, article_id)
    if a.status in PUBLIC_READABLE_STATUSES:
        return a
    if _is_author(db, article_id, current_user):
        return a
    raise NotAuthorizedError("Article is private")


def assert_can_download_repo(
    db: Session,
    article_id: str,
    current_user: Optional[User],
) -> Article:
    """Raise if *current_user* cannot download the full git repo.

    Pool/sedimentation articles cannot be forked, so exporting the
    complete git history is treated as equivalent to a fork.
    """
    a = get_article_or_raise(db, article_id)
    if a.status in REPO_DOWNLOADABLE_STATUSES:
        return a
    if _is_author(db, article_id, current_user):
        return a
    raise NotAuthorizedError("Repo download not available for this article")


# ═══════════════════════════════════════════════════════════════════════════════
# Write permissions — author-only
# ═══════════════════════════════════════════════════════════════════════════════


def _assert_is_author(
    db: Session,
    article_id: str,
    current_user: User,
    action: str,
) -> Article:
    # Check author membership first (one query).  If the article
    # does not exist, get_author_ids returns an empty list.
    if _is_author(db, article_id, current_user):
        # Return a lightweight stub — callers that need full Article
        # data should call get_article_or_raise themselves.
        return get_article_or_raise(db, article_id)
    # Confirm whether the article exists at all so we return the
    # right error: NotFound vs NotAuthorized.
    exists = db.query(Article.id).filter(Article.id == article_id).first() is not None
    if not exists:
        raise NotFoundError("Article not found")
    raise NotAuthorizedError(f"Only authors can {action} this article")


def assert_can_edit_article(db: Session, article_id: str, current_user: User) -> Article:
    return _assert_is_author(db, article_id, current_user, "edit")


def assert_can_delete_article(db: Session, article_id: str, current_user: User) -> Article:
    return _assert_is_author(db, article_id, current_user, "delete")


def assert_can_rollback_article(db: Session, article_id: str, current_user: User) -> Article:
    return _assert_is_author(db, article_id, current_user, "rollback")


def assert_can_publish_article(db: Session, article_id: str, current_user: User) -> Article:
    return _assert_is_author(db, article_id, current_user, "publish")


def assert_can_extend_sink(db: Session, article_id: str, current_user: User) -> Article:
    return _assert_is_author(db, article_id, current_user, "extend sink")


def assert_can_sync_article(db: Session, article_id: str, current_user: User) -> Article:
    return _assert_is_author(db, article_id, current_user, "sync")


# ═══════════════════════════════════════════════════════════════════════════════
# Fork — status-gated + duplicate check
# ═══════════════════════════════════════════════════════════════════════════════


def assert_can_fork_article(
    db: Session,
    article_id: str,
    current_user: User,
) -> Article:
    """Raise if the article cannot be forked by *current_user*.

    Checks (in order):
    1. Article exists
    2. Status is forkable (``published`` only)
    3. User has not already forked this article
    """
    from peerpedia_core.storage.db.crud_article import get_article_by_fork_and_author

    a = get_article_or_raise(db, article_id)

    if a.status not in FORKABLE_STATUSES:
        raise NotAuthorizedError("Only published articles can be forked")

    existing = get_article_by_fork_and_author(
        db,
        forked_from=article_id,
        author_id=current_user.id,
    )
    if existing is not None:
        raise ConflictError("Already forked this article")

    return a


# ═══════════════════════════════════════════════════════════════════════════════
# Publish — self-review gate
# ═══════════════════════════════════════════════════════════════════════════════


def require_self_review_for_publish(
    db: Session,
    article_id: str,
    current_user: User,
) -> None:
    """Raise if the current HEAD lacks a pool-scoped self-review
    by *current_user*.
    """
    from peerpedia_core.storage.db.crud_review import get_review_by_user_scope
    from peerpedia_core.storage.git_backend import DEFAULT_ARTICLES_DIR

    rp = DEFAULT_ARTICLES_DIR / article_id
    if not (rp / ".git").is_dir():
        raise BadRequestError(
            "self_review is required before publishing — no git repo found",
        )

    repo = gitmod.Repo(rp)
    if not repo.head.is_valid():
        raise BadRequestError(
            "self_review is required before publishing — no commits yet",
        )

    head = repo.head.commit.hexsha
    existing = get_review_by_user_scope(
        db,
        article_id,
        current_user.id,
        "pool",
        commit_hash=head,
    )
    if existing is None:
        raise BadRequestError("self_review is required before publishing")
