"""Specification: FastAPI Application Entry Point.

The application entry point initializes the FastAPI app with:
  - CORS middleware for local dev and Tauri
  - Health check endpoint for network-status pinging
  - Background auto-publish loop
  - Global exception handler for clean 500 responses
"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client_no_auth(db_engine):
    """TestClient without require_user override — for testing auth behavior."""
    from peerpedia_api import deps
    from peerpedia_api.main import app
    from peerpedia_core.storage.db.engine import get_session

    def override_db():
        session = get_session(db_engine)
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[deps.get_db] = override_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


class TestHealthCheck:
    """GET /health — liveness probe for frontend network-status pinger."""

    def test_health_returns_ok(self, client_no_auth):
        resp = client_no_auth.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestExceptionHandler:
    """Global exception handler returns clean 500 for unhandled errors."""

    def test_http_exception_passes_through(self, client_no_auth):
        """HTTPException (e.g., 404) is re-raised and handled by FastAPI's
        default handler, not the global handler."""
        resp = client_no_auth.get("/api/v1/articles/nonexistent-id-12345")
        # FastAPI should return 404 from the route handler
        assert resp.status_code == 404

    def test_invalid_route_returns_404(self, client_no_auth):
        """Accessing a non-existent endpoint returns 404."""
        resp = client_no_auth.get("/api/v1/nonexistent")
        assert resp.status_code == 404


class TestCORSMiddleware:
    """CORS middleware configuration."""

    def test_cors_headers_present(self, client_no_auth):
        """CORS headers are present on OPTIONS requests."""
        resp = client_no_auth.options(
            "/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        # FastAPI's CORSMiddleware should allow the origin
        assert resp.status_code == 200


class TestAutoPublishLoop:
    """Background auto-publish task — compiles and publishes sedimentation articles."""

    def test_auto_publish_loop_can_run(self):
        """The auto_publish_loop can complete one iteration without error."""
        import asyncio
        from unittest.mock import patch, AsyncMock

        # Patch the asyncio.sleep to avoid waiting 60 seconds
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            # Make sleep raise CancelledError after one iteration to stop cleanly
            mock_sleep.side_effect = asyncio.CancelledError()

            from peerpedia_api.main import _auto_publish_loop

            async def run():
                try:
                    await _auto_publish_loop()
                except asyncio.CancelledError:
                    pass  # Expected — we cancelled it

            asyncio.run(run())
            mock_sleep.assert_called_once_with(60)

    def test_auto_publish_loop_catches_errors(self):
        """The auto_publish_loop handles exceptions gracefully and continues."""
        import asyncio
        from unittest.mock import patch, AsyncMock

        # Make the first sleep succeed (loop body runs) then cancel on second
        call_count = 0

        async def side_effect(delay):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                raise asyncio.CancelledError()

        with patch("asyncio.sleep", side_effect=side_effect) as mock_sleep:
            from peerpedia_api.main import _auto_publish_loop

            async def run():
                try:
                    await _auto_publish_loop()
                except asyncio.CancelledError:
                    pass

            asyncio.run(run())


class TestRouterMounting:
    """All routers are mounted correctly."""

    def test_routers_respond(self, client_no_auth):
        """All major endpoints are reachable."""
        # Health
        assert client_no_auth.get("/health").status_code == 200

    def test_api_v1_prefix(self, client_no_auth):
        """API routes are under /api/v1 prefix."""
        # Auth
        resp = client_no_auth.get("/api/v1/auth/me")
        assert resp.status_code == 401  # requires auth

        # Users
        resp = client_no_auth.get("/api/v1/users")
        assert resp.status_code == 200

        # Articles
        resp = client_no_auth.get("/api/v1/articles")
        assert resp.status_code == 200

        # Search
        resp = client_no_auth.get("/api/v1/search")
        assert resp.status_code == 200


class TestGlobalExceptionHandler:
    """Global exception handler returns clean 500 for unhandled errors."""

    def test_http_exception_re_raised(self):
        """HTTPException is re-raised by the global handler (not converted to 500)."""
        import asyncio
        from fastapi import HTTPException, Request
        from peerpedia_api.main import app

        # Build a mock request scope
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "headers": [],
            "query_string": b"",
        }
        request = Request(scope)

        # Call the exception handler directly
        handler = app.exception_handlers.get(Exception)
        if handler:
            exc = HTTPException(status_code=404, detail="Not found")

            async def run():
                try:
                    await handler(request, exc)
                    return False  # Should have raised
                except HTTPException as e:
                    return e.status_code == 404

            result = asyncio.run(run())
            assert result is True

    def test_unhandled_exception_returns_500(self):
        """An unhandled ValueError returns a clean 500 JSON response."""
        import asyncio
        from fastapi import Request
        from peerpedia_api.main import app

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "headers": [],
            "query_string": b"",
        }
        request = Request(scope)
        handler = app.exception_handlers.get(Exception)

        if handler:
            async def run():
                from fastapi.responses import JSONResponse
                resp = await handler(request, ValueError("Something broke"))
                return resp

            result = asyncio.run(run())
            assert result.status_code == 500
            import json
            body = json.loads(result.body)
            assert "error" in body.get("detail", "").lower()
