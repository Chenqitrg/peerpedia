"""PeerPedia Core — Protocol Layer 0."""

from peerpedia_core.protocol.addressing import (
    compute_article_cid,
    compute_file_cid,
    resolve_cid,
)
from peerpedia_core.protocol.messages import (
    ArticleMeta,
    ArticleRef,
    ArticleStatus,
    AuthorContrib,
    ChangeType,
    ContributionSnapshot,
    ContributorShare,
    Decision,
    EditProposal,
    EditType,
    Identity,
    IdentityType,
    OriginalWork,
    PIPProposal,
    ProposalStatus,
    ReputationVector,
    ReviewMessage,
    UserProfile,
)
from peerpedia_core.protocol.signing import (
    generate_keypair,
    hash_content,
    sign_message,
    verify_signature,
)

__all__ = [
    # Messages
    "ArticleMeta",
    "ArticleRef",
    "ArticleStatus",
    "AuthorContrib",
    "ChangeType",
    "ContributorShare",
    "ContributionSnapshot",
    "Decision",
    "EditProposal",
    "EditType",
    "Identity",
    "IdentityType",
    "PIPProposal",
    "ProposalStatus",
    "ReputationVector",
    "ReviewMessage",
    "UserProfile",
    # Signing
    "generate_keypair",
    "hash_content",
    "sign_message",
    "verify_signature",
    # Addressing
    "compute_article_cid",
    "compute_file_cid",
    "resolve_cid",
]
