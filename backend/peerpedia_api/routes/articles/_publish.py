"""Article publish and download routes: sink, publish, source, download."""
from pathlib import Path

from fastapi import Depends, HTTPException
from peerpedia_core.config.params import params
from peerpedia_core.storage.db.crud_article import (
    extend_sink,
    get_article,
    set_sink_start,
    update_article_status,
)
from peerpedia_core.storage.db.models import User
from sqlalchemy.orm import Session

from peerpedia_api import deps
from peerpedia_api.schemas.article import (
    ArticleDetail,
    ArticleSourceResponse,
    SinkExtensionRequest,
)

from ._crud import build_article_detail, repo_path
from ._router import router


@router.put("/{article_id}/sink-extension", response_model=ArticleDetail)
def api_extend_sink(
    article_id: str, body: SinkExtensionRequest,
    current_user: User = Depends(deps.require_user),
    db: Session = Depends(deps.get_db),
):
    try:
        a = extend_sink(db, article_id, body.extra_days, params.sink.max_days)
        return build_article_detail(db, a.id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{article_id}/publish", response_model=ArticleDetail)
def api_publish_article(
    article_id: str,
    current_user: User = Depends(deps.require_user),
    db: Session = Depends(deps.get_db),
):
    """Explicitly publish a draft article to the sedimentation pool."""
    a = get_article(db, article_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Article not found")
    a = set_sink_start(db, article_id, params.sink.new_article_default_days)
    a = update_article_status(db, article_id, "sedimentation")
    return build_article_detail(db, a.id)


# ── Source ─────────────────────────────────────────────────────────────

@router.get("/{article_id}/source", response_model=ArticleSourceResponse)
def api_get_source(article_id: str):
    rp = repo_path(article_id)
    for ext in [".md", ".typ"]:
        f = rp / f"article{ext}"
        if f.exists():
            fmt = "markdown" if ext == ".md" else "typst"
            return ArticleSourceResponse(content=f.read_text(), format=fmt)
    raise HTTPException(status_code=404, detail="Source file not found")


@router.get("/{article_id}/download/source")
def api_download_source(article_id: str):
    from fastapi.responses import PlainTextResponse
    rp = repo_path(article_id)
    for ext in [".md", ".typ"]:
        f = rp / f"article{ext}"
        if f.exists():
            return PlainTextResponse(
                content=f.read_text(),
                media_type="text/plain",
                headers={"Content-Disposition": f"attachment; filename=article{ext}"},
            )
    raise HTTPException(status_code=404, detail="Source file not found")


@router.get("/{article_id}/download/pdf")
def api_download_pdf(article_id: str):
    """Compile article to PDF and return as downloadable file."""
    import tempfile

    from fastapi.responses import FileResponse, PlainTextResponse

    rp = repo_path(article_id)
    for ext in [".typ", ".md"]:
        f = rp / f"article{ext}"
        if f.exists():
            if ext == ".typ":
                with tempfile.TemporaryDirectory() as tmp:
                    tmp_dir = Path(tmp)
                    out_dir = tmp_dir / "out"
                    out_dir.mkdir()
                    from peerpedia_core.storage.compiler import TypstBackend
                    result = TypstBackend().compile(f, out_dir, fmt="pdf")
                    if not result.success:
                        raise HTTPException(
                            status_code=500,
                            detail=result.error or "PDF compilation failed",
                        )
                    return FileResponse(
                        result.output_path,
                        media_type="application/pdf",
                        filename=f"{article_id}.pdf",
                    )
            else:
                with tempfile.TemporaryDirectory() as tmp:
                    tmp_dir = Path(tmp)
                    out_dir = tmp_dir / "out"
                    out_dir.mkdir()
                    from peerpedia_core.storage.compiler import MarkdownBackend
                    result = MarkdownBackend().compile(f, out_dir)
                    html = result.html_content or ""
                    if not html and result.output_path:
                        html = Path(result.output_path).read_text()
                    return PlainTextResponse(
                        content=html,
                        media_type="text/html",
                        headers={
                            "Content-Disposition":
                                f"attachment; filename={article_id}.html",
                        },
                    )
    raise HTTPException(status_code=404, detail="Source file not found")


@router.get("/{article_id}/download/repo")
def api_download_repo(article_id: str):
    """Export the entire article git repository as a tar.gz bundle."""
    import tarfile
    import tempfile

    from fastapi.responses import FileResponse

    rp = repo_path(article_id)
    if not (rp / ".git").is_dir():
        raise HTTPException(status_code=404, detail="Git repo not found")

    tmp = tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False)
    try:
        with tarfile.open(tmp.name, "w:gz") as tar:
            tar.add(str(rp), arcname=article_id)
    except Exception:
        Path(tmp.name).unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="Failed to create archive")

    return FileResponse(
        tmp.name,
        media_type="application/gzip",
        filename=f"{article_id}.tar.gz",
    )
