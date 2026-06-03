"""Web — API endpoints (REST)."""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pathlib import Path
import tempfile

from peerpedia.config.settings import settings
from peerpedia_core.storage.db import (
    get_engine, get_session, init_db, list_articles, get_article,
    create_user as db_create_user,
    get_user,
    create_identity as db_create_identity,
    get_identities_for_user,
)
from peerpedia.submit import submit_article

from pydantic import BaseModel as PydanticBaseModel, Field


class UserCreateRequest(PydanticBaseModel):
    id: str
    name: str
    email: str
    affiliation: str | None = None
    expertise: list[str] = Field(default_factory=list)
    bio: str | None = None


class IdentityCreateRequest(PydanticBaseModel):
    type: str
    value: str
    verified: bool = False


router = APIRouter(prefix="/api/v1")


def _get_db_session():
    """Get a database session, ensuring tables exist."""
    engine = get_engine(settings.database_url)
    init_db(engine)
    return get_session(engine)


@router.get("/articles")
async def api_list_articles():
    """List all articles (most recent first)."""
    session = _get_db_session()
    try:
        articles = list_articles(session)
        return {
            "articles": [a.to_dict() for a in articles],
            "total": len(articles),
        }
    finally:
        session.close()


@router.get("/articles/{article_id}")
async def api_get_article(article_id: str):
    """Get article metadata by ID."""
    session = _get_db_session()
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
):
    """Submit a new article via file upload (multipart form)."""
    # Validate format
    if format not in ("typst", "markdown"):
        raise HTTPException(status_code=400, detail="Format must be 'typst' or 'markdown'")

    # Save uploaded file to temp location
    suffix = ".typ" if format == "typst" else ".md"
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=suffix, delete=False, encoding="utf-8"
    ) as tmp:
        content = await article_file.read()
        # If the file doesn't have frontmatter, prepend from form fields
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
        # Cleanup temp file
        if tmp_path.exists():
            tmp_path.unlink()


@router.get("/articles/{article_id}/reviews")
async def api_get_reviews(article_id: str):
    """Get all reviews for an article."""
    from peerpedia_core.storage.db import get_reviews_for_article
    session = _get_db_session()
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
):
    """Submit a review for an article."""
    from peerpedia_core.workflow.review import assign_reviewer, submit_review

    # Assign (no-op if already in_review)
    assign_result = assign_reviewer(
        article_id=article_id,
        reviewer_id=reviewer_id,
        database_url=settings.database_url,
    )
    if not assign_result.success and "must be" not in assign_result.error:
        raise HTTPException(status_code=400, detail=assign_result.error)

    # Submit review
    result = submit_review(
        article_id=article_id,
        reviewer_id=reviewer_id,
        decision=decision,
        comments=comments,
        scientific_correctness=scientific_correctness,
        clarity=clarity,
        database_url=settings.database_url,
    )

    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)

    return {
        "review_id": result.review_id,
        "points_earned": result.points_earned,
        "status": "submitted",
    }


@router.post("/articles/{article_id}/decide")
async def api_decide_article(article_id: str):
    """Make a decision on an article."""
    from peerpedia_core.workflow.review import make_decision

    result = make_decision(
        article_id=article_id,
        database_url=settings.database_url,
    )

    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)

    return {
        "article_id": article_id,
        "new_status": result.new_status,
        "author_points": result.author_points,
    }


@router.get("/articles/{article_id}/compile")
async def api_compile_article(article_id: str, fmt: str = "html"):
    """Compile an article on demand.

    Args:
        fmt: 'html' (default) or 'pdf'
    """
    from pathlib import Path
    from peerpedia_core.storage.compiler import TypstBackend, MarkdownBackend

    session = _get_db_session()
    try:
        article = get_article(session, article_id)
        if article is None:
            raise HTTPException(status_code=404, detail="Article not found")

        repo = Path(article.git_repo_path) if article.git_repo_path else None
        if repo is None or not repo.exists():
            raise HTTPException(status_code=404, detail="Article source not found")

        # Find source file
        source_files = []
        if article.format == "typst":
            source_files = list(repo.glob("*.typ"))
            backend = TypstBackend()
        else:
            source_files = list(repo.glob("*.md"))
            backend = MarkdownBackend()

        if not source_files:
            raise HTTPException(status_code=404, detail="Source file not found")

        source_file = source_files[0]

        # Compile
        result = backend.compile(source_file, repo)

        if not result.success:
            raise HTTPException(status_code=500, detail=f"Compilation failed: {result.error}")

        if fmt == "pdf" and result.output_path:
            from fastapi.responses import FileResponse
            return FileResponse(
                result.output_path,
                media_type="application/pdf",
                filename=f"{article.title}.pdf",
            )
        elif result.html_content:
            from fastapi.responses import HTMLResponse
            return HTMLResponse(content=result.html_content)
        elif result.output_path:
            # Read output as text
            output = Path(result.output_path)
            return {"content": output.read_text(), "format": article.format}
        else:
            raise HTTPException(status_code=500, detail="No output produced")
    finally:
        session.close()


# ── Collaboration ──────────────────────────────────────────────────────────────

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


# ── Edit Proposals ─────────────────────────────────────────────────────────────

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


@router.get("/articles/{article_id}/proposals")
async def api_list_proposals(article_id: str, status: str = None):
    """List edit proposals for an article."""
    from peerpedia_core.storage.db import get_edit_proposals_for_article

    session = _get_db_session()
    try:
        article = get_article(session, article_id)
        if article is None:
            raise HTTPException(status_code=404, detail="Article not found")
        proposals = get_edit_proposals_for_article(session, article_id, status=status)
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

    return {
        "proposal_id": proposal_id,
        "new_status": result.new_status,
    }


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


# ── Contribution Timeline ──────────────────────────────────────────────────────

@router.get("/articles/{article_id}/contributions")
async def api_get_contribution_timeline(article_id: str):
    """Get contribution timeline and breakdown for an article."""
    from peerpedia_core.storage.db import get_contribution_records
    from peerpedia_core.workflow.contribution import (
        compute_contribution_breakdown,
        compute_contribution_timeline,
    )

    session = _get_db_session()
    try:
        article = get_article(session, article_id)
        if article is None:
            raise HTTPException(status_code=404, detail="Article not found")

        records = get_contribution_records(session, article_id)
        timeline = compute_contribution_timeline([r.to_dict() for r in records])
        breakdown = compute_contribution_breakdown([r.to_dict() for r in records])

        return {
            "article_id": article_id,
            "timeline": timeline,
            "breakdown": breakdown,
            "total_records": len(records),
        }
    finally:
        session.close()


# ── User & Identity ──────────────────────────────────────────────────────────────


@router.get("/users/{user_id}")
async def api_get_user(user_id: str):
    """Get user profile with identities."""
    session = _get_db_session()
    try:
        user = get_user(session, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")

        identities = get_identities_for_user(session, user_id)
        result = user.to_dict()
        result["identities"] = [i.to_dict() for i in identities]
        return result
    finally:
        session.close()


@router.post("/users")
async def api_create_user(req: UserCreateRequest):
    """Create (register) a new user."""
    session = _get_db_session()
    try:
        existing = get_user(session, req.id)
        if existing is not None:
            raise HTTPException(status_code=409, detail=f"User '{req.id}' already exists")

        user = db_create_user(
            session,
            id=req.id,
            name=req.name,
            email=req.email,
            affiliation=req.affiliation,
            expertise=req.expertise,
            bio=req.bio,
        )
        session.commit()
        return user.to_dict()
    finally:
        session.close()


@router.post("/users/{user_id}/identities")
async def api_create_identity(user_id: str, req: IdentityCreateRequest):
    """Bind a verified identity to a user."""
    session = _get_db_session()
    try:
        user = get_user(session, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")

        # Determine trust_weight from identity type
        weight_map = {
            "orcid": 100,
            "inst_email": 80,
            "arxiv": 60,
            "scholar": 50,
            "github": 30,
        }
        trust_weight_scaled = weight_map.get(req.type, 10)

        identity = db_create_identity(
            session,
            user_id=user_id,
            type=req.type,
            value=req.value,
            verified=req.verified,
            trust_weight=trust_weight_scaled,
        )
        session.commit()
        return identity.to_dict()
    finally:
        session.close()


@router.get("/users/{user_id}/reputation")
async def api_get_user_reputation(user_id: str):
    """Get the reputation vector for a user."""
    from peerpedia_core.reputation import ReputationV1

    session = _get_db_session()
    try:
        algo = ReputationV1()
        vec = algo.compute(user_id, session=session)
        return vec.model_dump()
    finally:
        session.close()


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "version": "0.1.0"}
