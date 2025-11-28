import os
from datetime import UTC, datetime, timedelta

import pytest
from starlette.middleware.base import RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from src.middleware.oauth import OAuthMiddleware
from src.models.auth import AuthContext
from src.registry.tool_registry import register_all_tools
from src.utils.context import auth_context_var


def pytest_configure(config):
    """
    Sets dummy environment variables and registers tools required for tests.
    """
    from dotenv import load_dotenv
    load_dotenv()

    # Register tools for the test session
    register_all_tools()


# Store original dispatch before any patching for OAuth test modules to reference
_real_oauth_dispatch = OAuthMiddleware.dispatch


@pytest.fixture(scope="session")
def bypass_oauth_for_most_tests():
    """
    Session-scoped autouse fixture to bypass OAuth for all tests by default.
    OAuth-specific test modules can temporarily restore real OAuth using _real_oauth_dispatch.
    """
    original_dispatch = _real_oauth_dispatch

    async def mock_dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Bypass OAuth - set a valid auth context for test requests
        if request.url.path not in self.exclude_paths:
            request.state.auth_context = AuthContext(
                is_valid=True,
                token_hash="mock_hash",
                scopes=["read:transcripts"],
                expires_at=datetime.now(UTC) + timedelta(hours=1),
                client_id="mock_client",
            )
            auth_context_var.set(request.state.auth_context)

        response = await call_next(request)

        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; preload"
        )
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    # Apply the monkey patch
    OAuthMiddleware.dispatch = mock_dispatch

    yield

    # Restore original dispatch method
    OAuthMiddleware.dispatch = original_dispatch
