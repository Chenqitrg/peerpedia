"""FastAPI application entry point."""
import asyncio
import logging
import os
from contextlib import asynccontextmanager

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
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch unhandled exceptions and return a clean 500 response.

    HTTPException is re-raised so FastAPI's default handler can process it.
    """
    if isinstance(exc, HTTPException):
        raise exc
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
