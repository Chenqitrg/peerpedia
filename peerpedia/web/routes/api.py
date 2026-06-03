"""Web — API endpoint facade.

Combines sub-routers from api_articles, api_users, api_collab, and api_citations
into a single router with the /api/v1 prefix.
"""

from fastapi import APIRouter

from peerpedia.web.routes.api_articles import router as articles_router
from peerpedia.web.routes.api_citations import router as citations_router
from peerpedia.web.routes.api_collab import router as collab_router
from peerpedia.web.routes.api_lan import router as lan_router
from peerpedia.web.routes.api_comments import router as comments_router
from peerpedia.web.routes.api_users import router as users_router

router = APIRouter(prefix="/api/v1")

router.include_router(articles_router)
router.include_router(comments_router)
router.include_router(users_router)
router.include_router(collab_router)
router.include_router(citations_router)
router.include_router(lan_router)
