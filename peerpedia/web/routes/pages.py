"""Web — Route handlers for HTML pages."""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from peerpedia.web.db_session import get_db_session
from peerpedia_core.storage.db import (
    Article,
    get_article,
    list_articles,
)

router = APIRouter()

templates_dir = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))
from datetime import datetime, timezone
templates.env.globals['v'] = datetime.now(timezone.utc).strftime('%Y%m%d%H%M')

STATUS_ZH = {
    "draft": "草稿",
    "submitted": "已提交",
    "in_review": "审稿中",
    "revisions_requested": "需修改",
    "accepted": "已接受",
    "published": "已发表",
    "rejected": "已拒绝",
    "edit_proposed": "编辑提案中",
}
templates.env.globals["status_zh"] = STATUS_ZH


def get_viewer(request: Request) -> str:
    """Get current viewer from cookie, query param, or empty string."""
    viewer = request.cookies.get("viewer", "")
    if viewer:
        return viewer
    # Fallback: check query params (both 'viewer' and 'user' used historically)
    viewer = request.query_params.get("viewer", "")
    if viewer:
        return viewer
    return request.query_params.get("user", "")


def get_all_users():
    """Get list of all registered users for the nav picker."""
    session = get_db_session()
    try:
        from peerpedia_core.storage.db import User
        return [(u.id, u.name) for u in session.query(User).order_by(User.id).all()]
    except Exception:
        return []
    finally:
        session.close()


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page — article listing from database."""
    session = get_db_session()
    try:
        tab = request.query_params.get("tab", "all")
        viewer = get_viewer(request)
        articles = list_articles(session)
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "request": request,
                "title": "PeerPedia",
                "articles": [a.to_dict() for a in articles],
                "tab": tab,
                "viewer": viewer,
                "all_users": get_all_users(),
            },
        )
    finally:
        session.close()


@router.get("/article/{article_id}", response_class=HTMLResponse)
async def view_article(request: Request, article_id: str):
    """View a single article with rendered content."""
    session = get_db_session()
    try:
        article = get_article(session, article_id)
        viewer = get_viewer(request)
        if article is None:
            return templates.TemplateResponse(
                request=request,
                name="article.html",
                context={"request": request, "title": "Not Found", "article": None,
                         "viewer": viewer, "all_users": get_all_users()},
                status_code=404,
            )

        article_dict = article.to_dict()

        article_dict["content"] = None  # Compiled on demand via HTMX

        # Compute community review averages for 5 dimensions
        from peerpedia_core.storage.db import get_reviews_for_article
        reviews = get_reviews_for_article(session, article_id)
        community_review = None
        if reviews:
            from peerpedia_core.workflow.review_dimensions import REVIEW_DIMENSIONS
            dims = REVIEW_DIMENSIONS
            scores = {d: [] for d in dims}
            for r in reviews:
                for d in dims:
                    val = getattr(r, f"review_{d}", 0)
                    if val > 0:
                        scores[d].append(val)
            averages = {}
            for d in dims:
                if scores[d]:
                    averages[d] = round(sum(scores[d]) / len(scores[d]), 1)
            if averages:
                community_review = {"scores": averages, "count": len(reviews)}

        # Viewer's existing review for pre-filling the comment form
        my_review = None
        if viewer:
            for r in reviews:
                if r.reviewer_id == viewer:
                    my_review = r.to_dict()
                    break

        return templates.TemplateResponse(
            request=request,
            name="article.html",
            context={
                "request": request,
                "title": article_dict["title"],
                "article": article_dict,
                "viewer": viewer,
                "all_users": get_all_users(),
                "community_review": community_review,
                "reviews": [r.to_dict() for r in reviews],
                "my_review": my_review,
            },
        )
    finally:
        session.close()


@router.get("/submit", response_class=HTMLResponse)
async def submit_page(request: Request):
    """Redirect to the online editor (submit + edit are now unified)."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/edit", status_code=302)


@router.get("/edit", response_class=HTMLResponse)
async def edit_page(request: Request):
    """Online editor — new article."""
    viewer = get_viewer(request)
    return templates.TemplateResponse(
        request=request,
        name="edit.html",
        context={
            "request": request,
            "title": "编辑文章",
            "viewer": viewer,
            "all_users": get_all_users(),
            "article": None,
        },
    )


@router.get("/edit/{article_id}", response_class=HTMLResponse)
async def edit_article_page(request: Request, article_id: str):
    """Online editor — edit existing article, loading its source."""
    session = get_db_session()
    viewer = get_viewer(request)
    try:
        article = get_article(session, article_id)
        if article is None:
            return templates.TemplateResponse(
                request=request,
                name="edit.html",
                context={
                    "request": request,
                    "title": "文章未找到",
                    "viewer": viewer,
                    "all_users": get_all_users(),
                    "article": None,
                    "error": "文章未找到。",
                },
                status_code=404,
            )

        article_dict = article.to_dict()

        # Read source file content for the editor
        source_content = ""
        from pathlib import Path
        repo = Path(article.git_repo_path) if article.git_repo_path else None
        if repo and repo.exists():
            ext = "*.typ" if article.format == "typst" else "*.md"
            source_files = list(repo.glob(ext))
            if source_files:
                source_content = source_files[0].read_text()

        article_dict["source_content"] = source_content
        return templates.TemplateResponse(
            request=request,
            name="edit.html",
            context={
                "request": request,
                "title": f"编辑: {article.title}",
                "viewer": viewer,
                "all_users": get_all_users(),
                "article": article_dict,
            },
        )
    finally:
        session.close()


@router.get("/review/{article_id}", response_class=HTMLResponse)
async def review_article_page(request: Request, article_id: str):
    """Review form for a specific article."""
    session = get_db_session()
    viewer = get_viewer(request)
    try:
        article = get_article(session, article_id)
        if article is None:
            return templates.TemplateResponse(
                request=request,
                name="review.html",
                context={"request": request, "title": "Not Found", "article": None, "reviews": [],
                         "viewer": viewer, "all_users": get_all_users()},
                status_code=404,
            )

        from peerpedia_core.storage.db import get_reviews_for_article, update_article_status
        reviews = get_reviews_for_article(session, article_id)

        # Compute sink progress
        sink_pct = 0
        days_left = 7
        if reviews:
            from peerpedia_core.workflow.review_dimensions import REVIEW_DIMENSIONS
            dims = REVIEW_DIMENSIONS
            scores = []
            for r in reviews:
                vals = [getattr(r, f"review_{d}", 0) for d in dims]
                if any(v > 0 for v in vals):
                    scores.append(sum(vals) / len(vals))
            if scores:
                avg = sum(scores) / len(scores)
                # Higher avg → faster sink → higher sink_pct
                # avg=5 → sink_pct=95, days_left≈0 (auto-publish)
                # avg=1 → sink_pct≈19, days_left≈6
                base_days = 7
                sink_pct = min(95, int(avg / 5.0 * 95))
                days_left = max(0, base_days - int(avg / 5.0 * base_days))
        else:
            # No reviews yet — full 7 days
            from datetime import datetime, timezone
            if article.created_at:
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                age_days = (now - article.created_at).days
                days_left = max(0, 7 - age_days)
                sink_pct = min(95, int((age_days / 7) * 100))

        # Auto-publish if sedimented
        if days_left <= 0 and article.status == "submitted":
            update_article_status(session, article.id, "published")
            session.commit()
            article = get_article(session, article_id)  # refresh

        # Viewer's existing review for pre-filling the form
        my_review = None
        if viewer:
            for r in reviews:
                if r.reviewer_id == viewer:
                    my_review = r.to_dict()
                    break

        return templates.TemplateResponse(
            request=request,
            name="review.html",
            context={
                "request": request,
                "title": f"Review: {article.title}",
                "article": article.to_dict(),
                "reviews": [r.to_dict() for r in reviews],
                "viewer": viewer,
                "all_users": get_all_users(),
                "sink_pct": sink_pct,
                "days_left": days_left,
                "my_review": my_review,
            },
        )
    finally:
        session.close()


@router.get("/review", response_class=HTMLResponse)
async def review_queue(request: Request):
    """Review queue — list articles pending review."""
    session = get_db_session()
    viewer = get_viewer(request)
    try:
        # Pool: submitted + in_review (legacy)
        pool = list_articles(session, status="submitted")
        pool += list_articles(session, status="in_review")
        return templates.TemplateResponse(
            request=request,
            name="review.html",
            context={
                "request": request,
                "title": "沉淀池",
                "articles": [a.to_dict() for a in pool],
                "viewer": viewer,
                "all_users": get_all_users(),
            },
        )
    finally:
        session.close()


@router.get("/user/{user_id}", response_class=HTMLResponse)
async def user_profile(request: Request, user_id: str):
    """User profile page — personal arXiv and activity footprint."""
    session = get_db_session()
    viewer = get_viewer(request)
    try:
        # Articles authored by this user
        authored = (
            session.query(Article)
            .filter(Article.founding_authors.contains(user_id))
            .order_by(Article.created_at.desc())
            .all()
        )

        # Articles mirrored by this user
        mirrored = (
            session.query(Article)
            .filter(Article.mirror_by == user_id)
            .order_by(Article.created_at.desc())
            .all()
        )

        # Reviews by this user
        from peerpedia_core.storage.db import Review
        reviews = (
            session.query(Review)
            .filter(Review.reviewer_id == user_id)
            .order_by(Review.created_at.desc())
            .all()
        )

        # Build activity timeline
        activities = []
        for a in authored:
            activities.append({
                "type": "submit",
                "label": "提交了文章",
                "title": a.title,
                "article_id": a.id,
                "time": a.created_at.isoformat() if a.created_at else "",
            })
        for m in mirrored:
            activities.append({
                "type": "mirror",
                "label": f"搬运了 arXiv:{m.source_arxiv_id or '?'}",
                "title": m.title,
                "article_id": m.id,
                "time": m.created_at.isoformat() if m.created_at else "",
            })
        for r in reviews:
            activities.append({
                "type": "review",
                "label": "审稿了",
                "title": r.article_id,
                "article_id": r.article_id,
                "decision": r.decision,
                "points": r.points_earned,
                "time": r.created_at.isoformat() if r.created_at else "",
            })

        # Sort by time descending
        activities.sort(key=lambda x: x["time"], reverse=True)

        # Compute reputation vector for radar chart
        from peerpedia_core.reputation import ReputationV1
        try:
            algo = ReputationV1()
            reputation = algo.compute(user_id, session=session).model_dump()
        except Exception:
            reputation = {}

        # Follow state
        from peerpedia_core.storage.db import (
            get_follower_count,
            get_following_count,
            is_following,
        )
        is_self = bool(viewer) and viewer == user_id
        is_following_user = not is_self and bool(viewer) and is_following(session, viewer, user_id)
        following_count = get_following_count(session, user_id)
        follower_count = get_follower_count(session, user_id)

        return templates.TemplateResponse(
            request=request,
            name="user.html",
            context={
                "request": request,
                "title": f"用户: {user_id}",
                "user_id": user_id,
                "authored": [a.to_dict() for a in authored],
                "mirrored": [m.to_dict() for m in mirrored],
                "reviews": [
                    {
                        "article_id": r.article_id,
                        "decision": r.decision,
                        "points_earned": r.points_earned,
                        "scientific_correctness": r.scientific_correctness,
                        "clarity": r.clarity,
                        "created_at": r.created_at.isoformat() if r.created_at else "",
                    }
                    for r in reviews
                ],
                "activities": activities[:30],
                "total_articles": len(authored),
                "total_mirrors": len(mirrored),
                "total_reviews": len(reviews),
                "total_points": sum(r.points_earned for r in reviews),
                "reputation": reputation,
                "is_self": is_self,
                "is_following": is_following_user,
                "current_user": viewer,
                "following_count": following_count,
                "follower_count": follower_count,
                "all_users": get_all_users(),
            },
        )
    finally:
        session.close()


# ── LAN status page ────────────────────────────────────────────────────────────

@router.get("/lan-status", response_class=HTMLResponse)
async def lan_status_page(request: Request):
    """Show online LAN nodes and their article counts."""
    from peerpedia_core.storage.db import get_engine, get_session, init_db, get_online_nodes
    from peerpedia.web.db_session import settings

    viewer = get_viewer(request)
    nodes = []
    try:
        engine = get_engine(settings.database_url)
        init_db(engine)
        session = get_session(engine)
        try:
            raw_nodes = get_online_nodes(session, timeout_seconds=3600)
            for n in raw_nodes:
                nodes.append({
                    "node_id": n.node_id,
                    "host": n.host,
                    "port": n.port,
                    "articles_count": n.articles_count,
                    "is_self": bool(n.is_self),
                    "last_seen": n.last_seen.isoformat() if n.last_seen else "",
                })
        finally:
            session.close()
    except Exception:
        pass

    return templates.TemplateResponse(
        request=request, name="lan_status.html",
        context={"request": request, "title": "局域网状态",
                 "nodes": nodes, "node_count": len(nodes),
                 "viewer": viewer, "all_users": get_all_users()},
    )
