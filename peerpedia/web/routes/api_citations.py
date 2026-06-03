"""Web — Citation click tracking and citation graph API endpoints."""

from fastapi import APIRouter, Form, HTTPException, Query

from peerpedia.web.db_session import get_db_session
from peerpedia_core.workflow.citations import get_citation_info

router = APIRouter()


@router.get("/articles/{article_id}/citations")
async def api_get_citations(article_id: str):
    """Get citation graph info (cites + cited_by) for an article."""
    session = get_db_session()
    try:
        info = get_citation_info(session, article_id)
        return info
    finally:
        session.close()


@router.post("/citations/click")
async def api_record_click(
    from_article_id: str = Form(...),
    to_article_id: str = Form(...),
    user_id: str = Form(""),
    node_id: str = Form("unknown"),
):
    """Record a citation click event for transition probability tracking."""
    from peerpedia_core.workflow.citations import record_click

    if from_article_id == to_article_id:
        raise HTTPException(status_code=400, detail="Self-referential click is not allowed")

    session = get_db_session()
    try:
        result = record_click(
            session,
            from_article_id=from_article_id,
            to_article_id=to_article_id,
            node_id=node_id or "unknown",
            user_id=user_id or None,
        )
        session.commit()
        return {
            "status": "recorded",
            "from_article_id": result["from_article_id"],
            "to_article_id": result["to_article_id"],
        }
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/citations/transitions")
async def api_get_transitions(
    article_id: str = Query(...),
    source: str = Query("local"),
):
    """Get click-based transition probabilities from an article."""
    from peerpedia_core.workflow.citations import compute_transition_probabilities

    if source not in ("local", "merged"):
        raise HTTPException(status_code=400, detail=f"Unknown source: '{source}'. Use 'local' or 'merged'.")

    session = get_db_session()
    try:
        other_clicks = None

        result = compute_transition_probabilities(
            session,
            from_article_id=article_id,
            other_nodes_clicks=other_clicks,
        )
        result["source"] = source
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()
