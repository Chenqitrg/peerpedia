"""Database layer — backward-compatible re-exports.

This package replaces the old monolithic db.py. All imports from
``peerpedia_core.storage.db`` continue to work unchanged.
"""

from peerpedia_core.protocol.messages import ArticleStatus
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
from peerpedia_core.storage.db.crud_events import (
    cleanup_stale_nodes,
    create_click_event,
    get_click_events_for_article,
    get_local_click_counts,
    get_online_nodes,
    upsert_node,
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
from peerpedia_core.storage.db.engine import (
    Base,
    JSONDict,
    JSONList,
    get_engine,
    get_session,
    init_db,
)
from peerpedia_core.storage.db.models import (
    Article,
    ClickEvent,
    ContributionRecord,
    EditProposal,
    Follow,
    Identity,
    NodeInfo,
    Review,
    User,
)

__all__ = [
    # engine
    "Base",
    "JSONDict",
    "JSONList",
    "get_engine",
    "get_session",
    "init_db",
    # models
    "Article",
    "ArticleStatus",
    "ContributionRecord",
    "EditProposal",
    "Identity",
    "Review",
    "User",
    # crud — article
    "create_article",
    "get_article",
    "list_articles",
    "update_article_cid",
    "update_article_founding_authors",
    "update_article_status",
    "update_article_version",
    # crud — review
    "create_review",
    "get_review",
    "get_reviews_for_article",
    # crud — contribution
    "create_contribution_record",
    "get_contribution_records",
    "get_user_contribution_total",
    # crud — edit proposal
    "create_edit_proposal",
    "get_edit_proposal",
    "get_edit_proposals_for_article",
    "update_edit_proposal_status",
    # crud — user
    "create_user",
    "get_user",
    "update_user_last_active",
    # crud — identity
    "create_identity",
    "get_identities_for_user",
    # models — click
    "ClickEvent",
    # models — node
    "NodeInfo",
    # models — follow
    "Follow",
    # crud — follow
    "follow_user",
    "unfollow_user",
    "is_following",
    "get_following",
    "get_followers",
    "get_following_count",
    "get_follower_count",
    # crud — click
    "create_click_event",
    "get_click_events_for_article",
    "get_local_click_counts",
    # crud — node
    "upsert_node",
    "get_online_nodes",
    "cleanup_stale_nodes",
]
