"""API routes for collaboration, edit proposals, and health check."""

from fastapi import APIRouter, Form, HTTPException

from peerpedia.config.settings import settings
from peerpedia.web.db_session import get_db_session
from peerpedia_core.storage.db import (
    get_article,
    get_edit_proposals_for_article,
)

router = APIRouter()


# ── Collaboration ────────────────────────────────────────────────────────────

@router.post("/articles/{article_id}/collaborate")
async def api_accept_collaboration(article_id: str, reviewer_id: str = Form(...)):
    """Accept a reviewer's collaboration request."""
    from peerpedia_core.workflow.collaboration import accept_collaboration

    result = accept_collaboration(
        article_id=article_id,
        reviewer_id=reviewer_id,
        database_url=settings.database_url,
    )
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)

    return {
        "article_id": article_id,
        "founding_authors": result.founding_authors,
        "status": "collaboration_accepted",
    }


@router.get("/articles/{article_id}/collaboration/{reviewer_id}")
async def api_get_collaboration_status(article_id: str, reviewer_id: str):
    """Get collaboration status for a reviewer on an article."""
    from peerpedia_core.workflow.collaboration import get_collaboration_status

    return get_collaboration_status(
        article_id=article_id,
        reviewer_id=reviewer_id,
        database_url=settings.database_url,
    )


# ── Edit Proposals ───────────────────────────────────────────────────────────

@router.post("/articles/{article_id}/proposals")
async def api_create_proposal(
    article_id: str,
    proposer_id: str = Form(...),
    proposal_type: str = Form(...),
    description: str = Form(""),
):
    """Create an edit proposal for a published article."""
    from peerpedia_core.workflow.edit_proposal import create_proposal

    result = create_proposal(
        article_id=article_id,
        proposer_id=proposer_id,
        proposal_type=proposal_type,
        description=description,
        database_url=settings.database_url,
    )
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)

    return {
        "proposal_id": result.proposal_id,
        "article_id": result.article_id,
        "proposal_type": result.proposal_type,
        "auto_approved": result.auto_approved,
        "status": "created",
    }


def _render_proposals_html(article_id: str, proposals: list, total: int) -> str:
    """Render edit proposals as an HTML fragment."""
    if total == 0:
        return '<p style="color:#888;font-size:0.85em;">暂无修改提案。</p>'

    status_labels = {
        "pending": "⏳ 待审",
        "approved": "✅ 已通过",
        "rejected": "❌ 已拒绝",
        "auto_approved": "⚡ 自动通过",
        "merged": "🔀 已合并",
    }
    type_labels = {
        "minor": "微小修改",
        "medium": "中等修改",
        "major": "重大修改",
    }

    items = []
    for p in proposals:
        pd = p.to_dict()
        s = pd.get("status", "pending")
        pt = pd.get("proposal_type", "minor")
        desc = (pd.get("description") or "")[:100]
        proposer = pd.get("proposer_id", "unknown")
        ts = str(pd.get("created_at", ""))[:10] if pd.get("created_at") else ""
        items.append(
            f'<div style="padding:8px 0;border-bottom:1px solid #eee;font-size:0.85em;">'
            f'<span>{status_labels.get(s, s)}</span> '
            f'<span style="color:#888;">[{type_labels.get(pt, pt)}]</span> '
            f'<strong>{proposer}</strong> '
            f'<span style="color:#666;">{desc}</span>'
            f'<span style="float:right;color:#aaa;">{ts}</span>'
            f'</div>'
        )

    html = '<div class="proposals-list-html">'
    html += '<h4 style="margin:0 0 8px 0;">📋 修改提案 ({})</h4>'.format(total)
    html += "".join(items)
    html += "</div>"
    return html


@router.get("/articles/{article_id}/proposals")
async def api_list_proposals(article_id: str, format: str = "json", status: str | None = None):
    """List edit proposals for an article.

    Set ?format=html to get an HTML fragment for HTMX swap.
    """
    from fastapi.responses import HTMLResponse

    session = get_db_session()
    try:
        article = get_article(session, article_id)
        if article is None:
            if format == "html":
                return HTMLResponse('<p style="color:#888;">文章未找到。</p>')
            raise HTTPException(status_code=404, detail="Article not found")
        proposals = get_edit_proposals_for_article(session, article_id, status=status)
        if format == "html":
            return HTMLResponse(_render_proposals_html(
                article_id, proposals, len(proposals),
            ))
        return {
            "article_id": article_id,
            "proposals": [p.to_dict() for p in proposals],
            "total": len(proposals),
        }
    finally:
        session.close()


@router.post("/proposals/{proposal_id}/review")
async def api_review_proposal(
    proposal_id: str,
    reviewer_id: str = Form(...),
    decision: str = Form(...),
    comment: str = Form(""),
):
    """Review (approve/reject) an edit proposal."""
    from peerpedia_core.workflow.edit_proposal import review_proposal

    result = review_proposal(
        proposal_id=proposal_id,
        reviewer_id=reviewer_id,
        decision=decision,
        comment=comment,
        database_url=settings.database_url,
    )
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)

    return {"proposal_id": proposal_id, "new_status": result.new_status}


@router.post("/proposals/{proposal_id}/merge")
async def api_merge_proposal(
    proposal_id: str,
    article_id: str = Form(...),
    proposer_id: str = Form(...),
    change_type: str = Form("content"),
):
    """Merge an approved edit proposal."""
    from peerpedia_core.workflow.edit_proposal import merge_proposal

    result = merge_proposal(
        proposal_id=proposal_id,
        article_id=article_id,
        proposer_id=proposer_id,
        repository_url=str(settings.articles_dir / article_id),
        database_url=settings.database_url,
        change_type=change_type,
    )
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)

    return {
        "proposal_id": proposal_id,
        "article_id": article_id,
        "new_version": result.new_version,
        "contribution_record_id": result.contribution_record_id,
    }


# ── Health ───────────────────────────────────────────────────────────────────

@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "version": "0.1.0"}
