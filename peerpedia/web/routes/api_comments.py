"""API routes for line-level diff review comments."""

from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import HTMLResponse

from peerpedia.web.routes._helpers import get_article_or_404
from peerpedia.web.db_session import get_db_session
from peerpedia_core.storage.db import (
    create_review_comment,
    get_comments_for_article,
    resolve_review_comment,
)

router = APIRouter()


@router.get("/articles/{article_id}/comments")
async def api_get_comments(
    article_id: str,
    commit_hash: str = "",
    resolved: bool = None,
):
    """Get review comments for an article, optionally filtered by commit."""
    session = get_db_session()
    try:
        article = get_article_or_404(session, article_id)

        comments = get_comments_for_article(
            session,
            article_id,
            commit_hash=commit_hash or None,
            resolved=resolved,
        )
        return {
            "article_id": article_id,
            "comments": [c.to_dict() for c in comments],
            "total": len(comments),
        }
    finally:
        session.close()


@router.post("/articles/{article_id}/comments")
async def api_create_comment(
    article_id: str,
    commit_hash: str = Form(...),
    author_id: str = Form(...),
    body: str = Form(...),
    file_path: str = Form(""),
    line_start: int = Form(0),
    line_end: int = Form(None),
    comment_type: str = Form("comment"),
    suggestion: str = Form(""),
):
    """Add a line-level comment to a commit diff."""
    if comment_type not in ("comment", "suggestion"):
        raise HTTPException(status_code=400, detail="comment_type must be 'comment' or 'suggestion'")

    session = get_db_session()
    try:
        article = get_article_or_404(session, article_id)

        comment = create_review_comment(
            session,
            article_id=article_id,
            commit_hash=commit_hash,
            author_id=author_id,
            body=body,
            file_path=file_path,
            line_start=line_start,
            line_end=line_end,
            comment_type=comment_type,
            suggestion=suggestion,
        )
        session.commit()
        return {"comment": comment.to_dict(), "status": "created"}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/articles/{article_id}/comments/{comment_id}/resolve")
async def api_resolve_comment(article_id: str, comment_id: str):
    """Mark a review comment as resolved."""
    session = get_db_session()
    try:
        comment = resolve_review_comment(session, comment_id, resolved=True)
        if comment is None:
            raise HTTPException(status_code=404, detail="Comment not found")
        session.commit()
        return {"comment_id": comment_id, "resolved": True}
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/articles/{article_id}/comments/html")
async def api_get_comments_html(
    article_id: str,
    commit_hash: str = "",
):
    """Get comments as HTML fragment for HTMX swap."""
    from peerpedia_core.storage.db import get_article

    session = get_db_session()
    try:
        article = get_article(session, article_id)
        if article is None:
            return HTMLResponse('<p style="color:#888;">文章未找到。</p>')

        comments = get_comments_for_article(
            session,
            article_id,
            commit_hash=commit_hash or None,
        )
        if not comments:
            return HTMLResponse(
                '<p style="color:#888;font-size:0.85em;margin-top:8px;">'
                '此版本暂无评论。</p>'
            )

        html = '<div class="comments-html">'
        html += f'<h4 style="margin:12px 0 4px;">💬 评论 ({len(comments)})</h4>'
        for c in comments:
            cd = c.to_dict()
            suggestion_badge = ""
            if cd["comment_type"] == "suggestion":
                suggestion_badge = (
                    ' <span style="background:#fef3c7;color:#92400e;'
                    'padding:1px 4px;border-radius:2px;font-size:0.75em;">建议</span>'
                )
            resolved_badge = ""
            if cd["resolved"]:
                resolved_badge = (
                    ' <span style="color:#16a34a;font-size:0.75em;">✓ 已解决</span>'
                )
            line_info = f"L{cd['line_start']}"
            if cd["line_end"] and cd["line_end"] != cd["line_start"]:
                line_info += f"-{cd['line_end']}"

            html += (
                f'<div style="padding:6px 8px;margin:4px 0;background:#fff;'
                f'border:1px solid var(--border);border-radius:4px;font-size:0.85em;">'
                f'<strong>{cd["author_id"]}</strong> '
                f'<span style="color:#888;">{line_info}</span>'
                f'{suggestion_badge}{resolved_badge}'
                f'<div style="margin-top:2px;">{cd["body"]}</div>'
            )
            if cd["suggestion"]:
                html += (
                    f'<pre style="background:#f8f9fa;padding:4px;margin-top:4px;'
                    f'font-size:0.8em;overflow-x:auto;border-radius:3px;">'
                    f'<code>{cd["suggestion"]}</code></pre>'
                )
            if not cd["resolved"]:
                html += (
                    f'<button '
                    f'hx-post="/api/v1/articles/{article_id}/comments/{cd["id"]}/resolve" '
                    f'hx-swap="outerHTML" '
                    f'style="margin-top:4px;padding:2px 8px;font-size:0.75em;'
                    f'background:#16a34a;color:#fff;border:none;border-radius:3px;'
                    f'cursor:pointer;">✓ 标记已解决</button>'
                )
            html += '</div>'
        html += '</div>'
        return HTMLResponse(html)
    finally:
        session.close()
