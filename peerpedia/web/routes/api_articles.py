"""API routes for articles, reviews, commits, and diffs."""

import tempfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from peerpedia.config.settings import settings
from peerpedia.submit import submit_article
from peerpedia.web.db_session import get_db_session
from peerpedia.web.routes._helpers import get_article_or_404
from peerpedia_core.storage.db import (
    get_article,
    get_reviews_for_article,
    list_articles,
    update_article_founding_authors,
)
from peerpedia_core.workflow.versioning import bump_minor_version

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
        article = get_article_or_404(session, article_id)
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
    author: str = Form(""),
    article_id: str = Form(""),
):
    """Submit a new article (or update existing if article_id is set)."""
    if format not in ("typst", "markdown"):
        raise HTTPException(status_code=400, detail="Format must be 'typst' or 'markdown'")

    suffix = ".typ" if format == "typst" else ".md"
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=suffix, delete=False, encoding="utf-8"
    ) as tmp:
        content = await article_file.read()
        text = content.decode("utf-8")
        had_frontmatter = text.startswith("---")
        # Typst doesn't understand YAML frontmatter; strip before saving
        if format == "typst" and had_frontmatter:
            parts = text.split("---", 2)
            if len(parts) >= 3:
                text = parts[2].strip() + "\n"
        if not had_frontmatter and not text.startswith("---"):
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

        # ── Update existing article ──────────────────────────────────
        if article_id:
            from peerpedia_core.storage.git_backend import commit_article
            from peerpedia_core.workflow.versioning import bump_minor_version
            from peerpedia_core.storage.db import (
                get_engine, init_db, get_session, get_article,
            )

            engine = get_engine(settings.database_url)
            init_db(engine)
            session = get_session(engine)
            try:
                article = get_article(session, article_id)
                if article is None:
                    raise HTTPException(status_code=404, detail="Article not found")

                # Update source file in existing git repo
                repo = Path(article.git_repo_path) if article.git_repo_path else None
                if repo and repo.exists():
                    ext = "*.typ" if article.format == "typst" else "*.md"
                    existing = list(repo.glob(ext))
                    # Strip YAML frontmatter for Typst (Typst doesn't parse YAML)
                    content_to_write = text
                    if article.format == "typst" and content_to_write.startswith("---"):
                        parts = content_to_write.split("---", 2)
                        if len(parts) >= 3:
                            content_to_write = parts[2].strip() + "\n"
                    dest = existing[0] if existing else repo / f"article{suffix}"
                    dest.write_text(content_to_write)

                    # Git commit
                    author_name = author or article.founding_authors[0] if article.founding_authors else "peerpedia"
                    commit_article(
                        repo,
                        message=f"Update: {title}",
                        author_name=author_name,
                        author_email=f"{author_name}@peerpedia.local",
                    )

                # Bump version
                new_version = bump_minor_version(article.version or "v0.1")
                article.version = new_version
                article.title = title
                article.abstract = abstract
                article.updated_at = datetime.now(timezone.utc)
                session.commit()

                return {
                    "article_id": article_id,
                    "title": title,
                    "commit": "updated",
                    "version": new_version,
                    "status": article.status,
                }
            finally:
                session.close()

        # ── New article submission ───────────────────────────────────
        result = submit_article(
            source_path=tmp_path,
            database_url=settings.database_url,
            articles_dir=settings.articles_dir,
            self_originality=self_originality,
            self_rigor=self_rigor,
            self_completeness=self_completeness,
            self_pedagogy=self_pedagogy,
            self_impact=self_impact,
            author_name=author or "peerpedia",
            author_email=f"{author}@peerpedia.local" if author else "peerpedia@localhost",
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
        article = get_article_or_404(session, article_id)

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
                       author_name=forker_id, author_email=f"{forker_id}@peerpedia.local",
                       allow_empty=True)

        from peerpedia_core.storage.db import create_article
        fork = create_article(
            session, id=new_id,
            title=f"{article.title} （派生）",
            founding_authors=[forker_id],
            abstract=article.abstract or "",
            git_repo_path=str(new_repo),
            format=article.format,
            language=article.language,
            categories=article.categories or [],
            keywords=article.keywords or [],
        )
        fork.forked_from = article_id
        fork.status = article.status  # inherit published status so merge button appears
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


@router.post("/articles/{article_id}/merge-proposal")
async def api_create_merge_proposal(
    article_id: str,
    target_article_id: str = Form(...),
    proposer_id: str = Form(...),
    description: str = Form(""),
):
    """Propose merging this fork back into the original article."""
    from fastapi.responses import HTMLResponse

    from peerpedia_core.storage.db import (
        create_merge_proposal, get_article,
    )

    session = get_db_session()
    try:
        fork = get_article_or_404(session, article_id)
        if fork.forked_from != target_article_id:
            raise HTTPException(status_code=400, detail="target_article_id must match forked_from")

        target = get_article_or_404(session, target_article_id)

        proposal = create_merge_proposal(
            session,
            fork_article_id=article_id,
            target_article_id=target_article_id,
            proposer_id=proposer_id,
            description=description,
        )
        session.commit()

        return HTMLResponse(
            f'<div style="padding:12px;background:#d1fae5;border-radius:6px;">'
            f'✓ 合并提议已提交，等待原作者审核。</div>'
            f'<script>setTimeout(function(){{location.reload()}},1200)</script>'
        )
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/merge-proposals/{proposal_id}/review")
async def api_review_merge_proposal(
    proposal_id: str,
    reviewer_id: str = Form(...),
    decision: str = Form(...),  # "approve" or "reject"
    comment: str = Form(""),
):
    """Review (approve/reject) a merge proposal."""
    import shutil
    from pathlib import Path

    from fastapi.responses import HTMLResponse

    from peerpedia.config.settings import settings as s
    from peerpedia_core.storage.db import (
        get_merge_proposal, update_merge_proposal_status,
        get_article, update_article_version, create_contribution_record,
    )
    from peerpedia_core.workflow.contribution import compute_change_type_weight
    from peerpedia_core.storage.git_backend import commit_article, init_article_repo

    session = get_db_session()
    try:
        proposal = get_merge_proposal(session, proposal_id)
        if proposal is None:
            raise HTTPException(status_code=404, detail="Proposal not found")
        if proposal.status != "pending":
            raise HTTPException(status_code=400, detail="Proposal already resolved")

        new_status = "approved" if decision == "approve" else "rejected"
        update_merge_proposal_status(
            session, proposal_id, new_status,
            reviewer_id=reviewer_id, review_comment=comment,
        )

        if decision == "approve":
            # Merge: copy fork files into original repo, commit, bump version
            fork = get_article(session, proposal.fork_article_id)
            target = get_article(session, proposal.target_article_id)
            fork_repo = Path(fork.git_repo_path) if fork and fork.git_repo_path else None
            target_repo = Path(target.git_repo_path) if target and target.git_repo_path else None

            if fork_repo and target_repo:
                # Copy files from fork to target
                for f in fork_repo.glob("*.md"):
                    shutil.copy2(f, target_repo / f.name)
                for f in fork_repo.glob("*.typ"):
                    shutil.copy2(f, target_repo / f.name)
                commit_article(
                    target_repo,
                    f"Merge: {proposal.description or 'Merge from fork'} by {proposal.proposer_id}",
                    author_name=reviewer_id,
                    author_email=f"{reviewer_id}@peerpedia.local",
                    allow_empty=True,
                )

            # Bump version
            new_version = bump_minor_version(target.version)
            update_article_version(session, proposal.target_article_id, new_version)

            # ── Merge credit (placeholder — simple formula) ──────────────────
            # Current: fork author gets full content weight, reviewer gets half.
            # Future: weight = f(diff_lines, change_type_complexity, reviewer_score,
            #                     original_author_contribution_pct, time_decay)
            # The compute_merge_credit() function will live in
            # peerpedia_core/workflow/contribution.py and be versioned via PIP.
            weight = compute_change_type_weight("content")
            create_contribution_record(
                session, article_id=proposal.target_article_id,
                user_id=proposal.proposer_id, commit_hash="merge",
                commit_message=f"Merge proposal: {proposal.description[:80]}",
                change_type="content", contribution_weight=weight,
            )
            create_contribution_record(
                session, article_id=proposal.target_article_id,
                user_id=reviewer_id, commit_hash="merge-review",
                commit_message=f"Reviewed merge from {proposal.proposer_id}",
                change_type="content", contribution_weight=weight // 2,
            )

            proposal.status = "merged"
            update_article_founding_authors(session, proposal.target_article_id, proposal.proposer_id)

        session.commit()

        return HTMLResponse(
            f'<div style="padding:12px;background:#d1fae5;border-radius:6px;">'
            f'✓ {decision} — 合并完成</div>'
            f'<script>setTimeout(function(){{location.reload()}},1200)</script>'
        )
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/articles/{article_id}/merge-proposals")
async def api_get_merge_proposals(article_id: str, format: str = "json", viewer: str = ""):
    """Get merge proposals targeting an article. Set ?format=html for HTMX fragment."""
    from fastapi.responses import HTMLResponse

    from peerpedia_core.storage.db import get_merge_proposals_for_article, get_article

    session = get_db_session()
    try:
        article = get_article(session, article_id)
        proposals = get_merge_proposals_for_article(session, article_id)
        is_author = viewer and article and viewer in (article.founding_authors or [])
        if format == "html":
            if not proposals:
                return HTMLResponse("")
            html = '<div style="margin-top:8px;"><strong>🔄 合并提议</strong>'
            for p in proposals:
                status_label = {"pending": "⏳ 待审核", "approved": "✅ 已批准", "rejected": "❌ 已拒绝", "merged": "🔀 已合并"}.get(p.status, p.status)
                html += (
                    f'<div style="padding:6px 8px;margin:4px 0;background:#fff;'
                    f'border:1px solid var(--border);border-radius:4px;">'
                    f'{status_label} · <strong>{p.proposer_id}</strong>'
                    f' · <a href="/article/{p.fork_article_id}">查看派生</a>'
                )
                if p.description:
                    html += f'<div style="color:#666;font-size:0.85em;">{p.description[:200]}</div>'
                # Show accept/reject buttons for pending proposals when viewer is the original author
                if p.status == "pending" and is_author:
                    html += (
                        f'<div style="margin-top:6px;display:flex;gap:6px;">'
                        f'<button onclick="reviewMerge(\'{p.id}\', \'approve\', \'{viewer}\')" '
                        f'style="padding:3px 12px;background:#16a34a;color:#fff;border:none;'
                        f'border-radius:3px;cursor:pointer;font-size:0.8em;">✅ 接受合并</button>'
                        f'<button onclick="reviewMerge(\'{p.id}\', \'reject\', \'{viewer}\')" '
                        f'style="padding:3px 12px;background:#e53e3e;color:#fff;border:none;'
                        f'border-radius:3px;cursor:pointer;font-size:0.8em;">❌ 拒绝</button>'
                        f'</div>'
                    )
                html += '</div>'
            html += '</div>'
            return HTMLResponse(html)
        return {"article_id": article_id, "proposals": [p.to_dict() for p in proposals], "total": len(proposals)}
    finally:
        session.close()


@router.get("/articles/{article_id}/forks")
async def api_get_forks(article_id: str, format: str = "json"):
    """Get all forks of an article. Set ?format=html for HTMX fragment."""
    from fastapi.responses import HTMLResponse

    from peerpedia_core.storage.db import Article

    session = get_db_session()
    try:
        forks = (
            session.query(Article)
            .filter(Article.forked_from == article_id)
            .order_by(Article.created_at.desc())
            .all()
        )

        if format == "html":
            if not forks:
                return HTMLResponse(
                    '<p style="color:#888;font-size:0.85em;padding:4px 0;">暂无派生。</p>'
                )
            html = '<ul style="margin:4px 0;padding-left:18px;font-size:0.85em;">'
            for f in forks:
                authors = ", ".join(f.founding_authors or [])
                html += (
                    f'<li style="margin:3px 0;">'
                    f'<a href="/article/{f.id}">{f.title}</a>'
                    f'<span style="color:#888;margin-left:6px;">{authors} · {f.status}</span>'
                    f'</li>'
                )
            html += '</ul>'
            return HTMLResponse(html)

        return {"article_id": article_id, "forks": [f.to_dict() for f in forks], "total": len(forks)}
    finally:
        session.close()


@router.get("/articles/{article_id}/reviews")
async def api_get_reviews(article_id: str):
    """Get all reviews for an article."""
    session = get_db_session()
    try:
        article = get_article_or_404(session, article_id)
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
    review_version: str = Form("v0.1"),
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
        review_version=review_version,
        database_url=settings.database_url,
    )
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)

    reviewer_id_anon = reviewer_id[:4].upper()
    return HTMLResponse(
        f'<div style="padding:12px;background:#d1fae5;border-radius:6px;margin-top:8px;">'
        f'<strong>✓ 评分已发表</strong> · 身份: 匿名者_{reviewer_id_anon}</div>'
        f'<script>setTimeout(function(){{location.reload()}},800)</script>'
    )

