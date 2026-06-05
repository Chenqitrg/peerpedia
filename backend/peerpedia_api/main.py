"""FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from peerpedia_api.routes.articles import router as articles_router
from peerpedia_api.routes.auth import router as auth_router
from peerpedia_api.routes.reviews import router as reviews_router
from peerpedia_api.routes.users import router as users_router
from peerpedia_api.routes.pool import router as pool_router
from peerpedia_api.routes.bookmarks import router as bookmarks_router
from peerpedia_api.routes.feed import router as feed_router
from peerpedia_api.routes.search import router as search_router
from peerpedia_api.routes.compile import router as compile_router
from peerpedia_api.routes.citations import router as citations_router
from peerpedia_api.routes.merge import router as merge_router

app = FastAPI(title="PeerPedia API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
