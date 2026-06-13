"""Merge proposal API routes."""
from fastapi import APIRouter, Depends, HTTPException
from peerpedia_core.storage.db.crud_article import get_article, get_author_ids
from peerpedia_core.storage.db.crud_merge import (
    accept_merge_proposal,
    create_merge_proposal,
    get_merge_proposal,
    get_merge_proposals_for_article,
    reject_merge_proposal,
)
from peerpedia_core.storage.db.models import User
from pydantic import BaseModel
from sqlalchemy.orm import Session

from peerpedia_api import deps

router = APIRouter(tags=["merge"])


class MergeProposalCreate(BaseModel):
    fork_article_id: str


@router.post("/articles/{article_id}/merge-proposals", status_code=201)
def api_create_merge(article_id: str, body: MergeProposalCreate,
                      current_user: User = Depends(deps.require_user),
                      db: Session = Depends(deps.get_db)):
    if get_article(db, article_id) is None:
        raise HTTPException(status_code=404, detail="Article not found")
    mp = create_merge_proposal(db, fork_id=body.fork_article_id,
                                target_id=article_id,
                                proposer_id=current_user.id)
    return {
        "id": mp.id, "fork_article_id": mp.fork_article_id,
        "target_article_id": mp.target_article_id,
        "proposer_id": mp.proposer_id, "status": mp.status,
        "thread": mp.thread, "created_at": mp.created_at.isoformat(),
    }


@router.get("/articles/{article_id}/merge-proposals")
def api_list_merges(article_id: str, db: Session = Depends(deps.get_db)):
    proposals = get_merge_proposals_for_article(db, article_id)
    return {
        "proposals": [
            {"id": p.id, "fork_article_id": p.fork_article_id,
             "target_article_id": p.target_article_id, "proposer_id": p.proposer_id,
             "status": p.status, "thread": p.thread,
             "created_at": p.created_at.isoformat()}
            for p in proposals
        ]
    }


def _validate_proposal_target(proposal_id: str, article_id: str, db: Session):
    mp = get_merge_proposal(db, proposal_id)
    if mp is None:
        raise HTTPException(status_code=404, detail="Merge proposal not found")
    if mp.target_article_id != article_id:
        raise HTTPException(status_code=400, detail="Proposal does not belong to this article")
    return mp


@router.post("/articles/{article_id}/merge-proposals/{proposal_id}/accept")
def api_accept_merge(article_id: str, proposal_id: str,
                      current_user: User = Depends(deps.require_user),
                      db: Session = Depends(deps.get_db)):
    mp = _validate_proposal_target(proposal_id, article_id, db)
    if current_user.id not in get_author_ids(db, article_id):
        raise HTTPException(status_code=403, detail="Only article authors can accept/reject merges")
    try:
        # Execute git merge — fork repo contents merged into target
        from peerpedia_core.storage.db.crud_article import (
            get_authors_from_git,
            rebuild_article_authors,
        )
        from peerpedia_core.storage.git_backend import (
            MergeConflictError,
            merge_git_repos,
        )

        from peerpedia_api.helpers import repo_path

        target_repo = repo_path(article_id)
        fork_repo = repo_path(mp.fork_article_id)

        if not (target_repo / ".git").is_dir() or not (fork_repo / ".git").is_dir():
            # Repos don't exist — accept the proposal without git merge
            # (e.g., tests or articles created before git repos were added)
            mp = accept_merge_proposal(db, proposal_id)
            return {"id": mp.id, "status": mp.status}

        merge_git_repos(target_repo, fork_repo, current_user.name)

        # Rebuild authors from merged git history
        all_authors = get_authors_from_git(target_repo, db)
        rebuild_article_authors(db, article_id, all_authors)

        mp = accept_merge_proposal(db, proposal_id)
        return {"id": mp.id, "status": mp.status}
    except MergeConflictError:
        # Proposal stays open — both sides notified
        return {
            "status": "conflict",
            "message": "Merge conflicts detected. Both authors need to resolve conflicts manually.",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/articles/{article_id}/merge-proposals/{proposal_id}/reject")
def api_reject_merge(article_id: str, proposal_id: str,
                      current_user: User = Depends(deps.require_user),
                      db: Session = Depends(deps.get_db)):
    _validate_proposal_target(proposal_id, article_id, db)
    if current_user.id not in get_author_ids(db, article_id):
        raise HTTPException(status_code=403, detail="Only article authors can accept/reject merges")
    try:
        mp = reject_merge_proposal(db, proposal_id)
        return {"id": mp.id, "status": mp.status}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
