# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""FastAPI application entry point."""
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from peerpedia_api.routes.articles import router as articles_router
from peerpedia_api.routes.auth import router as auth_router
from peerpedia_api.routes.bookmarks import router as bookmarks_router
from peerpedia_api.routes.citations import router as citations_router
from peerpedia_api.routes.compile import router as compile_router
from peerpedia_api.routes.feed import router as feed_router
from peerpedia_api.routes.merge import router as merge_router
from peerpedia_api.routes.pool import router as pool_router
from peerpedia_api.routes.reviews import router as reviews_router
from peerpedia_api.routes.search import router as search_router
from peerpedia_api.routes.users import router as users_router

logger = logging.getLogger(__name__)

# ── File-based logging ───────────────────────────────────────────────────

_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
_LOG_DIR.mkdir(exist_ok=True)

_file_handler = logging.FileHandler(_LOG_DIR / "backend.log")
_file_handler.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
))
_file_handler.setLevel(logging.DEBUG)
logging.getLogger().addHandler(_file_handler)
logging.getLogger("peerpedia_api").setLevel(logging.DEBUG)
logging.getLogger("peerpedia_core").setLevel(logging.DEBUG)

logger.info("Backend starting — logs written to %s", _LOG_DIR / "backend.log")




async def _auto_publish_loop():
    """Background loop that periodically publishes ready articles."""
    while True:
        try:
            await asyncio.sleep(60)
            from peerpedia_core.workflow.sedimentation import publish_ready_articles

            from peerpedia_api import deps
            db_gen = deps.get_db()
            session = next(db_gen)
            try:
                count = publish_ready_articles(session)
                if count > 0:
                    logger.info("Auto-published %d article(s)", count)
            finally:
                db_gen.close()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Auto-publish loop error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start background tasks on startup, cancel on shutdown."""
    # Run DB init + migrations before serving requests
    import os

    from peerpedia_core.storage.db.engine import get_engine, init_db, migrate_db
    db_url = os.environ.get("PEERPEDIA_DB", "sqlite:///peerpedia.db")
    engine = get_engine(db_url)
    init_db(engine)
    migrate_db(engine)

    # Repair: rebuild article_authors for articles that have none
    try:
        from peerpedia_core.storage.db.crud_article import repair_orphan_article_authors
        from peerpedia_core.storage.db.engine import get_session
        s = get_session(engine)
        repaired = repair_orphan_article_authors(s)
        if repaired:
            logger.info("Startup repair: rebuilt authors for %d articles", repaired)
        s.close()
    except Exception:
        logger.exception("Startup repair failed — continuing")

    task = asyncio.create_task(_auto_publish_loop())
    logger.info("Auto-publish background task started")
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        logger.info("Auto-publish background task stopped")


app = FastAPI(title="PeerPedia API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",      # Vite dev server
        "http://localhost:5174",      # Vite dev server (alt port)
        "tauri://localhost",          # Tauri production webview
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def audit_request(request: Request, call_next):
    """Log every request and its status for debugging."""
    response = await call_next(request)
    logger.debug(
        "%s %s → %d", request.method, request.url.path, response.status_code,
    )
    return response


@app.get("/health")
async def health_check():
    """Liveness probe for the frontend network-status pinger."""
    return {"status": "ok"}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch unhandled exceptions and return a clean 500 response.

    HTTPException is re-raised so FastAPI's default handler can process it.
    """
    if isinstance(exc, HTTPException):
        raise exc
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )

app.include_router(auth_router, prefix="/api/v1")
app.include_router(articles_router, prefix="/api/v1")
app.include_router(reviews_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(pool_router, prefix="/api/v1")
app.include_router(bookmarks_router, prefix="/api/v1")
app.include_router(feed_router, prefix="/api/v1")
app.include_router(search_router, prefix="/api/v1")
app.include_router(compile_router, prefix="/api/v1")
app.include_router(citations_router, prefix="/api/v1")
app.include_router(merge_router, prefix="/api/v1")
