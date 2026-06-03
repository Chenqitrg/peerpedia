"""API routes for contribution timeline, git commit history, diffs, and blame."""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from peerpedia.web.routes._helpers import get_article_or_404
from peerpedia.web.db_session import get_db_session
from peerpedia_core.storage.db import (
    get_article,
    get_contribution_records,
)
from peerpedia_core.storage.git_backend import (
    get_blame,
    get_commit_history,
    get_diff,
    get_diff_between,
)
from peerpedia_core.workflow.contribution import (
    compute_contribution_breakdown,
    compute_contribution_timeline,
)

router = APIRouter()


def _render_contribution_timeline_html(article_id: str, timeline: list, breakdown: dict, total: int) -> str:
    """Render contribution timeline as an HTML fragment."""
    if total == 0:
        return '<p style="color: #888;">暂无贡献记录。文章发布后可在此查看贡献历史。</p>'

    # Breakdown bar
    bar_items = []
    colors = ["#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f", "#edc948"]
    for i, (uid, pct) in enumerate(breakdown.items()):
        color = colors[i % len(colors)]
        bar_items.append(
            f'<div style="background:{color};width:{pct}%;display:inline-block;'
            f'text-align:center;color:white;font-size:0.75em;overflow:hidden;'
            f'white-space:nowrap;line-height:24px;" title="{uid}: {pct}%">{uid} {pct}%</div>'
        )

    html = '<div class="contribution-timeline-html">'
    # Breakdown bar
    html += '<div class="contribution-breakdown" style="margin-bottom:16px;">'
    html += '<h4 style="margin:0 0 8px 0;">📊 贡献占比</h4>'
    html += f'<div style="border-radius:4px;overflow:hidden;">{"".join(bar_items)}</div>'
    html += '</div>'

    # Timeline
    html += '<h4 style="margin:0 0 8px 0;">📋 贡献记录 ({})</h4>'.format(total)
    html += '<div class="timeline-list" style="max-height:300px;overflow-y:auto;">'
    for entry in timeline:
        ts = entry.get("timestamp", "")
        if hasattr(ts, "isoformat"):
            ts = ts.isoformat()
        ts_short = str(ts)[:10] if ts else ""
        uid = entry.get("user_id", "unknown")
        msg = entry.get("commit_message", "")[:80]
        lines = f"+{entry.get('lines_added', 0)}/-{entry.get('lines_deleted', 0)}"
        html += (
            f'<div style="padding:6px 0;border-bottom:1px solid #eee;font-size:0.85em;">'
            f'<span style="color:#888;">{ts_short}</span> '
            f'<strong>{uid}</strong> '
            f'<span style="color:#666;">{msg}</span> '
            f'<span style="color:#28a745;">{lines}</span>'
            f'</div>'
        )
    html += '</div></div>'
    return html


@router.get("/articles/{article_id}/contributions")
async def api_get_contribution_timeline(article_id: str, format: str = "json"):
    """Get contribution timeline and breakdown for an article.

    Set ?format=html to get an HTML fragment for HTMX swap.
    """
    session = get_db_session()
    try:
        article = get_article(session, article_id)
        if article is None:
            if format == "html":
                return HTMLResponse('<p style="color:#888;">文章未找到。</p>')
            raise HTTPException(status_code=404, detail="Article not found")

        records = get_contribution_records(session, article_id)
        record_dicts = [r.to_dict() for r in records]
        timeline = compute_contribution_timeline(record_dicts)
        breakdown = compute_contribution_breakdown(record_dicts)

        if format == "html":
            return HTMLResponse(_render_contribution_timeline_html(
                article_id, timeline, breakdown, len(records),
            ))

        return {
            "article_id": article_id,
            "timeline": timeline,
            "breakdown": breakdown,
            "total_records": len(records),
        }
    finally:
        session.close()


# ── Commit history ──────────────────────────────────────────────────────────


@router.get("/articles/{article_id}/commits")
async def api_get_commit_history(article_id: str):
    """Get git commit history for an article."""
    session = get_db_session()
    try:
        article = get_article_or_404(session, article_id)

        repo = Path(article.git_repo_path) if article.git_repo_path else None
        if repo is None or not repo.exists():
            raise HTTPException(status_code=404, detail="Git repository not found")

        commits = get_commit_history(repo)
        return {"article_id": article_id, "commits": commits, "total": len(commits)}
    finally:
        session.close()


@router.get("/articles/{article_id}/commits/html")
async def api_get_commit_history_html(article_id: str):
    """Get git commit history as an HTML fragment for HTMX swap."""
    session = get_db_session()
    try:
        article = get_article(session, article_id)
        if article is None:
            return HTMLResponse('<p style="color:#888;">文章未找到。</p>')

        repo = Path(article.git_repo_path) if article.git_repo_path else None
        if repo is None or not repo.exists():
            return HTMLResponse('<p style="color:#888;">Git 仓库未找到。</p>')

        commits = get_commit_history(repo)

        # Also include contribution records (merge, fork, etc.)
        records = get_contribution_records(session, article_id)

        if not commits and not records:
            return HTMLResponse('<p style="color:#888;">暂无提交记录。</p>')

        html = '<div class="commit-list-html">'
        # Git commits
        for i, c in enumerate(commits):
            short_hash = c["hash"][:8]
            msg = c["message"][:80]
            author = c["author"]
            ts = c["timestamp"][:10] if c["timestamp"] else ""
            active = "active" if i == 0 else ""
            files_count = len(c.get("stats", {}).get("files", []))
            event_icon = ""
            if "Merge:" in msg:
                event_icon = "🔀 "
            elif "Fork" in msg:
                event_icon = "🍴 "
            html += (
                f'<div class="commit-item {active}" data-hash="{c["hash"]}"'
                f' onclick="loadDiff(\'{article_id}\', \'{c["hash"]}\')"'
                f' style="padding:8px;border-bottom:1px solid #eee;cursor:pointer;'
                f'font-size:0.85em;border-radius:4px;transition:background 0.15s;">'
                f'<code style="color:#2563eb;font-size:0.8em;">{event_icon}{short_hash}</code> '
                f'<strong>{author}</strong>'
                f'<div style="color:#666;font-size:0.85em;margin-top:2px;">{msg}</div>'
                f'<span style="color:#888;font-size:0.75em;">{ts}'
            )
            if files_count:
                html += f' · {files_count} file(s)'
            html += '</span></div>'

        # Contribution records (non-git events: merge proposals, etc.)
        for r in records:
            msg = (r.commit_message or "")[:80]
            if not msg:
                continue
            uid = r.user_id or "unknown"
            ts = r.timestamp.isoformat()[:10] if r.timestamp else ""
            icon = "🔀 " if "merge" in msg.lower() else "📝 "
            html += (
                f'<div class="commit-item"'
                f' style="padding:8px;border-bottom:1px solid #eee;'
                f'font-size:0.85em;border-radius:4px;opacity:0.8;">'
                f'<code style="color:#16a34a;font-size:0.8em;">{icon}</code> '
                f'<strong>{uid}</strong>'
                f'<div style="color:#666;font-size:0.85em;margin-top:2px;">{msg}</div>'
                f'<span style="color:#888;font-size:0.75em;">{ts}</span>'
                f'</div>'
            )

        html += '</div>'
        return HTMLResponse(html)
    finally:
        session.close()


# ── Diff view ───────────────────────────────────────────────────────────────


@router.get("/articles/{article_id}/diff/{commit_hash}")
async def api_get_diff(article_id: str, commit_hash: str):
    """Get the diff for a specific commit as unified diff text.

    Returns JSON with commit metadata and unified diff text suitable
    for rendering with diff2html.
    """
    session = get_db_session()
    try:
        article = get_article_or_404(session, article_id)

        repo = Path(article.git_repo_path) if article.git_repo_path else None
        if repo is None or not repo.exists():
            raise HTTPException(status_code=404, detail="Git repository not found")

        diff_data = get_diff(repo, commit_hash)
        return diff_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Diff failed: {e}")
    finally:
        session.close()


@router.get("/articles/{article_id}/diff/{hash1}/{hash2}")
async def api_get_diff_between(article_id: str, hash1: str, hash2: str):
    """Get the diff between two commits."""
    session = get_db_session()
    try:
        article = get_article_or_404(session, article_id)

        repo = Path(article.git_repo_path) if article.git_repo_path else None
        if repo is None or not repo.exists():
            raise HTTPException(status_code=404, detail="Git repository not found")

        diff_data = get_diff_between(repo, hash1, hash2)
        return diff_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Diff failed: {e}")
    finally:
        session.close()


@router.get("/articles/{article_id}/blame")
async def api_get_blame(article_id: str):
    """Get git blame data for an article's main source file."""
    session = get_db_session()
    try:
        article = get_article_or_404(session, article_id)

        repo = Path(article.git_repo_path) if article.git_repo_path else None
        if repo is None or not repo.exists():
            raise HTTPException(status_code=404, detail="Git repository not found")

        # Find the main source file
        ext = "*.typ" if article.format == "typst" else "*.md"
        source_files = list(repo.glob(ext))
        if not source_files:
            raise HTTPException(status_code=404, detail="No source files found")

        blame_data = get_blame(repo, str(source_files[0].name))
        return {"article_id": article_id, "file": source_files[0].name, "blame": blame_data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Blame failed: {e}")
    finally:
        session.close()
