"""PeerPedia Core — Storage module."""

from peerpedia_core.storage.git_backend import (
    DEFAULT_ARTICLES_DIR,
    commit_article,
    get_blame,
    get_commit_history,
    init_article_repo,
)

from peerpedia_core.storage.db import (
    Article,
    ArticleStatus,
    Base,
    ContributionRecord,
    EditProposal,
    create_article,
    create_contribution_record,
    create_edit_proposal,
    get_article,
    get_contribution_records,
    get_edit_proposal,
    get_edit_proposals_for_article,
    get_engine,
    get_session,
    get_user_contribution_total,
    init_db,
    list_articles,
    update_article_cid,
    update_article_founding_authors,
    update_article_status,
    update_article_version,
    update_edit_proposal_status,
)

from peerpedia_core.storage.compiler import (
    CompileResult,
    CompilerBackend,
    MarkdownBackend,
    TypstBackend,
    detect_format,
    extract_frontmatter,
)

__all__ = [
    # git backend
    "DEFAULT_ARTICLES_DIR",
    "commit_article",
    "get_blame",
    "get_commit_history",
    "init_article_repo",
    # db layer — models
    "Article",
    "ArticleStatus",
    "Base",
    "ContributionRecord",
    "EditProposal",
    # db layer — CRUD
    "create_article",
    "create_contribution_record",
    "create_edit_proposal",
    "get_article",
    "get_contribution_records",
    "get_edit_proposal",
    "get_edit_proposals_for_article",
    "get_engine",
    "get_session",
    "get_user_contribution_total",
    "init_db",
    "list_articles",
    "update_article_cid",
    "update_article_founding_authors",
    "update_article_status",
    "update_article_version",
    "update_edit_proposal_status",
    # compiler
    "CompileResult",
    "CompilerBackend",
    "MarkdownBackend",
    "TypstBackend",
    "detect_format",
    "extract_frontmatter",
]
