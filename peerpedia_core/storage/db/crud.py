"""CRUD operations — backward-compatible re-exports.

Each function takes a SQLAlchemy Session as the first positional argument
so callers control transaction boundaries.

This module is split by entity for maintainability:
- crud_article.py  — Article + Review
- crud_user.py     — User + Identity + Follow
- crud_proposal.py — EditProposal + ContributionRecord
- crud_events.py   — ClickEvent + NodeInfo

All imports from ``peerpedia_core.storage.db.crud`` continue to work.
Prefer importing from ``peerpedia_core.storage.db`` directly.
"""

from peerpedia_core.storage.db.crud_article import (
    create_article,
    create_review,
    get_article,
    get_review,
    get_reviews_for_article,
    list_articles,
    update_article_cid,
    update_article_founding_authors,
    update_article_status,
    update_article_version,
)
from peerpedia_core.storage.db.crud_user import (
    create_identity,
    create_user,
    follow_user,
    get_follower_count,
    get_followers,
    get_following,
    get_following_count,
    get_identities_for_user,
    get_user,
    is_following,
    unfollow_user,
    update_user_last_active,
)
from peerpedia_core.storage.db.crud_proposal import (
    create_contribution_record,
    create_edit_proposal,
    get_contribution_records,
    get_edit_proposal,
    get_edit_proposals_for_article,
    get_user_contribution_total,
    update_edit_proposal_status,
)
from peerpedia_core.storage.db.crud_events import (
    cleanup_stale_nodes,
    create_click_event,
    get_click_events_for_article,
    get_local_click_counts,
    get_online_nodes,
    upsert_node,
)

__all__ = [n for n in dir() if not n.startswith("_")]
