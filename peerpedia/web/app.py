"""PeerPedia Web Application — FastAPI reference server.

This is the reference web client for the PeerPedia protocol.
It serves a local web UI for browsing, submitting, and reviewing articles.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI(
    title="知诸网 (PeerPedia)",
    description="Decentralized academic publishing — reference client",
    version="0.1.0",
)

# Static files (CSS, JS)
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Import and register route modules
from peerpedia.web.routes import api, pages  # noqa: E402, F401

app.include_router(pages.router)
app.include_router(api.router)
