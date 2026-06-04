"""Merge proposal API routes."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from peerpedia_api import deps
from peerpedia_core.storage.db.crud_merge import (
    create_merge_proposal, get_merge_proposal, get_merge_proposals_for_article,
    accept_merge_proposal, reject_merge_proposal,
)
from peerpedia_core.storage.db.crud_article import get_article

router = APIRouter(tags=["merge"])


class MergeProposalCreate(BaseModel):
    fork_article_id: str
    proposer_id: str


@router.post("/articles/{article_id}/merge-proposals", status_code=201)
def api_create_merge(article_id: str, body: MergeProposalCreate,
                      db: Session = Depends(deps.get_db)):
    if get_article(db, article_id) is None:
        raise HTTPException(status_code=404, detail="Article not found")
    mp = create_merge_proposal(db, fork_id=body.fork_article_id,
                                target_id=article_id,
                                proposer_id=body.proposer_id)
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
                      db: Session = Depends(deps.get_db)):
    mp = _validate_proposal_target(proposal_id, article_id, db)
    try:
        mp = accept_merge_proposal(db, proposal_id)
        return {"id": mp.id, "status": mp.status}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/articles/{article_id}/merge-proposals/{proposal_id}/reject")
def api_reject_merge(article_id: str, proposal_id: str,
                      db: Session = Depends(deps.get_db)):
    _validate_proposal_target(proposal_id, article_id, db)
    try:
        mp = reject_merge_proposal(db, proposal_id)
        return {"id": mp.id, "status": mp.status}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
