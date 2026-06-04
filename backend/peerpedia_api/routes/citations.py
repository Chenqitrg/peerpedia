"""Citation API routes."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from peerpedia_api import deps
from peerpedia_core.storage.db.crud_citation import (
    create_or_update_citation, get_cites, get_cited_by, get_citations,
)
from peerpedia_core.storage.db.crud_article import get_article

router = APIRouter(tags=["citations"])


class ClickRequest(BaseModel):
    from_article_id: str
    to_article_id: str


@router.get("/articles/{article_id}/citations")
def api_get_citations(article_id: str, db: Session = Depends(deps.get_db)):
    if get_article(db, article_id) is None:
        raise HTTPException(status_code=404, detail="Article not found")
    cites = get_cites(db, article_id)
    cited_by = get_cited_by(db, article_id)
    return {
        "cites": [{"id": c.to_article_id, "forward_prob": c.forward_prob,
                    "backward_prob": c.backward_prob} for c in cites],
        "cited_by": [{"id": c.from_article_id, "forward_prob": c.forward_prob,
                       "backward_prob": c.backward_prob} for c in cited_by],
    }


@router.post("/citations/click", status_code=201)
def api_record_click(body: ClickRequest, db: Session = Depends(deps.get_db)):
    # Simple: just create/update the citation edge
    create_or_update_citation(db, body.from_article_id, body.to_article_id,
                              forward=0.5, backward=0.0)
    return {"status": "ok"}
