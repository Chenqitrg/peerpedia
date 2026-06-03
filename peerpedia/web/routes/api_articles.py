"""API routes for articles, reviews, compilation, citations, commits, and diffs."""

import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from peerpedia.config.settings import settings
from peerpedia.submit import submit_article
from peerpedia.web.db_session import get_db_session
from peerpedia_core.storage.db import (
    get_article,
    get_reviews_for_article,
    list_articles,
)
from peerpedia_core.workflow.citations import get_citation_info, inject_citation_links

router = APIRouter()


@router.get("/articles")
async def api_list_articles():
    """List all articles (most recent first)."""
    session = get_db_session()
    try:
        articles = list_articles(session)
        return {"articles": [a.to_dict() for a in articles], "total": len(articles)}
    finally:
        session.close()


@router.get("/articles/{article_id}")
async def api_get_article(article_id: str):
    """Get article metadata by ID."""
    session = get_db_session()
    try:
        article = get_article(session, article_id)
        if article is None:
            raise HTTPException(status_code=404, detail="Article not found")
        return article.to_dict()
    finally:
        session.close()


@router.post("/articles")
async def api_create_article(
    title: str = Form(...),
    abstract: str = Form(""),
    format: str = Form("typst"),
    categories: str = Form(""),
    keywords: str = Form(""),
    language: str = Form("en"),
    article_file: UploadFile = File(...),
    self_originality: int = Form(0),
    self_rigor: int = Form(0),
    self_completeness: int = Form(0),
    self_pedagogy: int = Form(0),
    self_impact: int = Form(0),
):
    """Submit a new article via file upload (multipart form)."""
    if format not in ("typst", "markdown"):
        raise HTTPException(status_code=400, detail="Format must be 'typst' or 'markdown'")

    suffix = ".typ" if format == "typst" else ".md"
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=suffix, delete=False, encoding="utf-8"
    ) as tmp:
        content = await article_file.read()
        text = content.decode("utf-8")
        if not text.startswith("---"):
            cats = [c.strip() for c in categories.split(",") if c.strip()]
            kws = [k.strip() for k in keywords.split(",") if k.strip()]
            cats_yaml = "\n".join(f"  - {c}" for c in cats) if cats else ""
            kws_yaml = "\n".join(f"  - {k}" for k in kws) if kws else ""
            fm = f"---\ntitle: {title}\nabstract: {abstract}\nlanguage: {language}\n"
            if cats_yaml:
                fm += f"categories:\n{cats_yaml}\n"
            if kws_yaml:
                fm += f"keywords:\n{kws_yaml}\n"
            fm += "---\n\n"
            text = fm + text
        tmp.write(text)
        tmp_path = Path(tmp.name)

    try:
        settings.ensure_dirs()
        result = submit_article(
            source_path=tmp_path,
            database_url=settings.database_url,
            articles_dir=settings.articles_dir,
            self_originality=self_originality,
            self_rigor=self_rigor,
            self_completeness=self_completeness,
            self_pedagogy=self_pedagogy,
            self_impact=self_impact,
        )
        if not result.success:
            raise HTTPException(status_code=500, detail=result.error)
        return {
            "article_id": result.article_id,
            "title": result.title,
            "commit": result.git_commit_hash,
            "status": "submitted",
        }
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


@router.post("/articles/{article_id}/fork")
async def api_fork_article(article_id: str, forker_id: str = Form(...)):
    """Fork an article — clone git repo, create new draft with forked_from."""
    import shutil
    import uuid

    from peerpedia.config.settings import settings as s
    from peerpedia_core.storage.git_backend import commit_article

    session = get_db_session()
    try:
        article = get_article(session, article_id)
        if article is None:
            raise HTTPException(status_code=404, detail="Article not found")

        # Clone the git repo
        src_repo = Path(article.git_repo_path) if article.git_repo_path else None
        if src_repo is None or not src_repo.exists():
            raise HTTPException(status_code=404, detail="Source git repository not found")

        new_id = str(uuid.uuid4())
        new_repo = s.articles_dir / new_id
        new_repo.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src_repo, new_repo, dirs_exist_ok=True)

        # Remove .git and re-init to give the fork its own history
        old_git = new_repo / ".git"
        if old_git.exists():
            shutil.rmtree(old_git)

        from peerpedia_core.storage.git_backend import init_article_repo
        init_article_repo(new_id, base_dir=s.articles_dir)

        # Find source files and commit
        source_files = list(new_repo.glob("*.md")) + list(new_repo.glob("*.typ"))
        if not source_files:
            shutil.rmtree(new_repo, ignore_errors=True)
            raise HTTPException(status_code=500, detail="No source files found in fork")

        commit_article(new_repo, f"Fork from: {article.title}",
                       author_name=forker_id, author_email=f"{forker_id}@peerpedia.local")

        from peerpedia_core.storage.db import create_article
        fork = create_article(
            session, id=new_id,
            title=f"{article.title} (Fork)",
            founding_authors=[forker_id],
            abstract=article.abstract or "",
            git_repo_path=str(new_repo),
            format=article.format,
            language=article.language,
            categories=article.categories or [],
            keywords=article.keywords or [],
        )
        fork.forked_from = article_id
        # Bump fork count on source
        article.fork_count = (article.fork_count or 0) + 1
        session.commit()

        return {"article_id": fork.id, "title": fork.title, "forked_from": article_id}
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/articles/{article_id}/forks")
async def api_get_forks(article_id: str):
    """Get all forks of an article."""
    from peerpedia_core.storage.db import Article

    session = get_db_session()
    try:
        forks = (
            session.query(Article)
            .filter(Article.forked_from == article_id)
            .order_by(Article.created_at.desc())
            .all()
        )
        return {"article_id": article_id, "forks": [f.to_dict() for f in forks], "total": len(forks)}
    finally:
        session.close()


@router.get("/articles/{article_id}/reviews")
async def api_get_reviews(article_id: str):
    """Get all reviews for an article."""
    session = get_db_session()
    try:
        article = get_article(session, article_id)
        if article is None:
            raise HTTPException(status_code=404, detail="Article not found")
        reviews = get_reviews_for_article(session, article_id)
        return {
            "article_id": article_id,
            "reviews": [r.to_dict() for r in reviews],
            "total": len(reviews),
        }
    finally:
        session.close()


@router.post("/articles/{article_id}/reviews")
async def api_submit_review(
    article_id: str,
    reviewer_id: str = Form(...),
    decision: str = Form(...),
    comments: str = Form(""),
    scientific_correctness: int = Form(0),
    clarity: int = Form(0),
    review_originality: int = Form(0),
    review_rigor: int = Form(0),
    review_completeness: int = Form(0),
    review_pedagogy: int = Form(0),
    review_impact: int = Form(0),
):
    """Submit a review for an article. Returns HTML for HTMX swap."""
    from fastapi.responses import HTMLResponse

    from peerpedia_core.workflow.review import assign_reviewer, submit_review

    assign_result = assign_reviewer(
        article_id=article_id,
        reviewer_id=reviewer_id,
        database_url=settings.database_url,
    )
    if not assign_result.success and "must be" not in assign_result.error:
        raise HTTPException(status_code=400, detail=assign_result.error)

    result = submit_review(
        article_id=article_id,
        reviewer_id=reviewer_id,
        decision=decision,
        comments=comments,
        scientific_correctness=scientific_correctness,
        clarity=clarity,
        review_originality=review_originality,
        review_rigor=review_rigor,
        review_completeness=review_completeness,
        review_pedagogy=review_pedagogy,
        review_impact=review_impact,
        database_url=settings.database_url,
    )
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)

    decision_labels = {"accept": "接受", "revise": "修改后重投", "reject": "拒绝"}
    label = decision_labels.get(decision, decision)
    return HTMLResponse(
        f'<div style="padding:12px;background:#d1fae5;border-radius:6px;margin-top:8px;">'
        f'<strong>✓ 审稿已提交</strong><br>'
        f'决定: {label} · +{result.points_earned} 积分</div>'
        f'<script>setTimeout(function(){{location.reload()}},800)</script>'
    )


@router.post("/articles/{article_id}/decide")
async def api_decide_article(article_id: str):
    """Make a decision on an article. Returns HTML for HTMX swap."""
    from fastapi.responses import HTMLResponse

    from peerpedia_core.workflow.review import make_decision

    result = make_decision(article_id=article_id, database_url=settings.database_url)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)

    status_labels = {
        "accepted": "接受",
        "rejected": "拒绝",
        "revisions_requested": "需修改",
    }
    label = status_labels.get(result.new_status, result.new_status)
    author_pts = f" · 作者 +{result.author_points} 积分" if result.author_points else ""
    return HTMLResponse(
        f'<div style="padding:12px;background:#dbeafe;border-radius:6px;margin-top:8px;">'
        f'<strong>✓ 决定已做出: {label}</strong>{author_pts}</div>'
        f'<script>setTimeout(function(){{location.reload()}},800)</script>'
    )


def _compile_error(message: str, status: int = 200):
    """Return an HTML error response for compile failures."""
    from fastapi.responses import HTMLResponse
    return HTMLResponse(
        content=f'<div class="compile-error"><p>⚠️ {message}</p></div>',
        status_code=status,
    )


def _resolve_compile_backend(repo, article_format: str, article_title: str = ""):
    """Resolve the compiler backend and find the best source file.

    Returns (backend, source_path) or raises HTTPException on failure.
    When multiple source files exist, picks the one whose frontmatter title
    best matches the article title stored in the DB.
    """
    from fastapi import HTTPException
    from peerpedia_core.storage.compiler import MarkdownBackend, TypstBackend

    ext = "*.typ" if article_format == "typst" else "*.md"
    source_files = list(repo.glob(ext))
    if not source_files:
        raise HTTPException(
            status_code=400,
            detail=f"源文件未找到 (格式: {article_format})",
        )

    if len(source_files) == 1:
        picked = source_files[0]
    else:
        # Prefer the file whose frontmatter title matches the DB title
        from peerpedia_core.storage.compiler import extract_frontmatter
        picked = source_files[0]  # fallback
        for f in source_files:
            try:
                fm = extract_frontmatter(f.read_text())
                if fm.get("title") == article_title:
                    picked = f
                    break
            except Exception:
                continue

    backend = TypstBackend() if article_format == "typst" else MarkdownBackend()
    return backend, picked


@router.get("/articles/{article_id}/compile")
async def api_compile_article(article_id: str, fmt: str = "html"):
    """Compile an article on demand. fmt: 'html' (default) or 'pdf'."""
    from pathlib import Path
    from fastapi.responses import FileResponse, HTMLResponse
    from fastapi import HTTPException

    session = get_db_session()
    try:
        article = get_article(session, article_id)
        if article is None:
            return _compile_error("文章未找到。", status=404)

        repo = Path(article.git_repo_path) if article.git_repo_path else None
        if repo is None or not repo.exists():
            return _compile_error(f"源文件目录不存在。路径: {article.git_repo_path}")

        try:
            backend, source_file = _resolve_compile_backend(
                repo, article.format, article_title=article.title,  # type: ignore[arg-type]
            )
        except HTTPException as e:
            return _compile_error(str(e.detail))

        result = backend.compile(source_file, repo)
        if not result.success:
            return _compile_error(f"编译失败: {result.error}")

        if fmt == "pdf" and result.output_path:
            return FileResponse(
                result.output_path, media_type="application/pdf",
                filename=f"{article.title}.pdf",
            )
        elif result.html_content:
            return HTMLResponse(content=inject_citation_links(result.html_content))
        elif result.output_path and article.format == "typst":
            # Typst compiles to PDF only; show a preview card with download link
            pdf_url = f"/api/v1/articles/{article_id}/compile?fmt=pdf"
            viewer_html = (
                '<div style="text-align:center;padding:40px 20px;'
                'background:#f8f9fa;border-radius:8px;border:2px dashed #ddd;">'
                '<p style="font-size:3em;margin:0 0 16px 0;">📄</p>'
                '<p style="font-size:1.1em;margin:0 0 8px 0;color:#333;">'
                'Typst 文章已编译为 PDF</p>'
                '<p style="font-size:0.9em;color:#888;margin:0 0 20px 0;">'
                '点击下方按钮查看或下载</p>'
                f'<a href="{pdf_url}" target="_blank" '
                'style="display:inline-block;padding:10px 24px;background:#2563eb;'
                'color:white;border-radius:6px;text-decoration:none;margin:4px;">'
                '在新标签页中查看</a>'
                f'<a href="{pdf_url}" download '
                'style="display:inline-block;padding:10px 24px;background:#16a34a;'
                'color:white;border-radius:6px;text-decoration:none;margin:4px;">'
                '下载 PDF</a>'
                '</div>'
            )
            return HTMLResponse(content=viewer_html)
        elif result.output_path:
            output = Path(result.output_path)
            return {"content": output.read_text(), "format": article.format}
        else:
            return _compile_error("编译未产生输出。")
    finally:
        session.close()


@router.get("/articles/{article_id}/citations")
async def api_get_citations(article_id: str):
    """Get citation graph info (cites + cited_by) for an article."""
    session = get_db_session()
    try:
        info = get_citation_info(session, article_id)
        return info
    finally:
        session.close()


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
    from fastapi.responses import HTMLResponse

    from peerpedia_core.storage.db import get_contribution_records
    from peerpedia_core.workflow.contribution import (
        compute_contribution_breakdown,
        compute_contribution_timeline,
    )

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
    from pathlib import Path

    from peerpedia_core.storage.git_backend import get_commit_history

    session = get_db_session()
    try:
        article = get_article(session, article_id)
        if article is None:
            raise HTTPException(status_code=404, detail="Article not found")

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
    from pathlib import Path

    from fastapi.responses import HTMLResponse

    from peerpedia_core.storage.git_backend import get_commit_history

    session = get_db_session()
    try:
        article = get_article(session, article_id)
        if article is None:
            return HTMLResponse('<p style="color:#888;">文章未找到。</p>')

        repo = Path(article.git_repo_path) if article.git_repo_path else None
        if repo is None or not repo.exists():
            return HTMLResponse('<p style="color:#888;">Git 仓库未找到。</p>')

        commits = get_commit_history(repo)

        if not commits:
            return HTMLResponse('<p style="color:#888;">暂无提交记录。</p>')

        html = '<div class="commit-list-html">'
        for i, c in enumerate(commits):
            short_hash = c["hash"][:8]
            msg = c["message"][:80]
            author = c["author"]
            ts = c["timestamp"][:10] if c["timestamp"] else ""
            active = "active" if i == 0 else ""
            files_count = len(c.get("stats", {}).get("files", []))
            html += (
                f'<div class="commit-item {active}" data-hash="{c["hash"]}"'
                f' onclick="loadDiff(\'{article_id}\', \'{c["hash"]}\')"'
                f' style="padding:8px;border-bottom:1px solid #eee;cursor:pointer;'
                f'font-size:0.85em;border-radius:4px;transition:background 0.15s;">'
                f'<code style="color:#2563eb;font-size:0.8em;">{short_hash}</code> '
                f'<strong>{author}</strong>'
                f'<div style="color:#666;font-size:0.85em;margin-top:2px;">{msg}</div>'
                f'<span style="color:#888;font-size:0.75em;">{ts}'
            )
            if files_count:
                html += f' · {files_count} file(s)'
            html += '</span></div>'
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
    from pathlib import Path

    from peerpedia_core.storage.git_backend import get_diff

    session = get_db_session()
    try:
        article = get_article(session, article_id)
        if article is None:
            raise HTTPException(status_code=404, detail="Article not found")

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
    from pathlib import Path

    from peerpedia_core.storage.git_backend import get_diff_between

    session = get_db_session()
    try:
        article = get_article(session, article_id)
        if article is None:
            raise HTTPException(status_code=404, detail="Article not found")

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
    from pathlib import Path

    from peerpedia_core.storage.git_backend import get_blame

    session = get_db_session()
    try:
        article = get_article(session, article_id)
        if article is None:
            raise HTTPException(status_code=404, detail="Article not found")

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


# ── Review Comments (line-level diff comments) ─────────────────────────────


@router.get("/articles/{article_id}/comments")
async def api_get_comments(
    article_id: str,
    commit_hash: str = "",
    resolved: bool = None,
):
    """Get review comments for an article, optionally filtered by commit."""
    from peerpedia_core.storage.db import get_comments_for_article

    session = get_db_session()
    try:
        article = get_article(session, article_id)
        if article is None:
            raise HTTPException(status_code=404, detail="Article not found")

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
    from peerpedia_core.storage.db import create_review_comment

    if comment_type not in ("comment", "suggestion"):
        raise HTTPException(status_code=400, detail="comment_type must be 'comment' or 'suggestion'")

    session = get_db_session()
    try:
        article = get_article(session, article_id)
        if article is None:
            raise HTTPException(status_code=404, detail="Article not found")

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
    from peerpedia_core.storage.db import resolve_review_comment

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
    from fastapi.responses import HTMLResponse

    from peerpedia_core.storage.db import get_comments_for_article

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


# ── Search ────────────────────────────────────────────────────────────────


@router.get("/search")
async def api_search(q: str = "", format: str = "json"):
    """Search articles by title, abstract, and keywords.

    Set ?format=html for HTMX swap into #article-list.
    """
    from fastapi.responses import HTMLResponse

    from peerpedia_core.storage.db import Article

    session = get_db_session()
    try:
        if not q.strip():
            articles = list_articles(session)
        else:
            pattern = f"%{q.strip()}%"
            articles = (
                session.query(Article)
                .filter(
                    Article.title.ilike(pattern)
                    | Article.abstract.ilike(pattern)
                    | Article.keywords.contains(q.strip())
                )
                .order_by(Article.created_at.desc())
                .limit(50)
                .all()
            )

        if format == "html":
            if not articles:
                return HTMLResponse(
                    '<p class="empty-state" style="padding:24px;">'
                    f'未找到与 "{q}" 相关的文章。</p>'
                )
            html = '<h2>文章</h2>'
            for a in articles:
                ad = a.to_dict()
                authors = ", ".join(ad.get("founding_authors", []))
                abstract = (ad.get("abstract") or "")[:200]
                status = ad.get("status", "")
                html += (
                    f'<article class="article-card">'
                    f'<h3><a href="/article/{ad["id"]}">{ad["title"]}</a></h3>'
                    f'<p class="meta">'
                    f'{authors} · {ad["format"]} · '
                    f'<span class="status {status}">{status}</span>'
                    f' · {str(ad.get("created_at", ""))[:10]}'
                    f'</p>'
                )
                if abstract:
                    html += f'<p class="abstract">{abstract}</p>'
                html += '</article>'
            return HTMLResponse(html)

        return {
            "q": q,
            "articles": [a.to_dict() for a in articles],
            "total": len(articles),
        }
    finally:
        session.close()
