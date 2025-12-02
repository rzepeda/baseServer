import hashlib
import time
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any, cast  # Added cast

import httpx
from authlib.jose import JoseError, JsonWebKey, jwt
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from src.config import get_config
from src.models.auth import AuthContext
from src.utils.context import auth_context_var
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Constants
OAUTH_VALIDATION_TIMEOUT_MS = 1000  # Increased timeout for network requests
JWKS_CACHE_TTL = 3600  # Cache JWKS for 1 hour


class OAuthError(Exception):
    """Custom exception for OAuth related errors."""

    def __init__(self, error: str, description: str, status_code: int):
        self.error = error
        self.description = description
        self.status_code = status_code
        super().__init__(f"{error}: {description}")


@lru_cache(maxsize=128)
async def _get_cached_jwks(jwks_uri: str) -> dict[str, Any]:
    """
    Fetch and cache JWKS from the provider.
    
    Uses lru_cache to avoid repeated fetches to the JWKS endpoint.
    The cache is based on the jwks_uri.
    """
    logger.info("oauth_jwks_fetching", jwks_uri=jwks_uri)
    try:
        response = httpx.get(jwks_uri, timeout=5.0)
        response.raise_for_status()
        jwks_data = response.json()
        logger.info(
            "oauth_jwks_fetch_success", jwks_uri=jwks_uri, key_count=len(jwks_data.get("keys", []))
        )
        return cast(dict[str, Any], jwks_data)
    except httpx.RequestError as e:
        logger.error("oauth_jwks_fetch_failed", jwks_uri=jwks_uri, error=str(e))
        raise OAuthError("server_error", f"Failed to fetch JWKS: {e}", 503) from e



async def validate_token_with_authlib(
    token: str, token_hash: str, issuer: str, jwks_uri: str
) -> AuthContext:
    """Validates the token using authlib with JWKS."""
    start_time = time.monotonic()

    try:
        # Fetch JWKS (cached)
        jwks_data = _get_cached_jwks(jwks_uri)

        # Decode and validate the JWT with claims validation
        # authlib will automatically select the correct key from the JWKS
        claims = jwt.decode(
            token,
            JsonWebKey.import_key_set(jwks_data),
            claims_options={
                "iss": {"essential": True, "value": issuer},
                "exp": {"essential": True},
                "iat": {"essential": True},
                "nbf": {"essential": False},
            },
        )

        # Claims are automatically validated during decode with claims_options
        # Additional manual validation if needed
        claims.validate()

    except JoseError as e:
        logger.warning("oauth_jwt_validation_failed", token_hash=token_hash[:8], error=str(e))
        raise OAuthError("invalid_token", f"Token validation failed: {e}", 401) from e
    except Exception as e:
        logger.error("oauth_jwt_unexpected_error", exc_info=e, token_hash=token_hash[:8])
        raise OAuthError(
            "server_error", "An unexpected error occurred during token validation", 500
        ) from e

    expires_at = datetime.fromtimestamp(claims["exp"], tz=UTC)

    auth_context = AuthContext(
        is_valid=True,
        token_hash=token_hash,
        scopes=claims.get("scope", "").split(),
        expires_at=expires_at,
        client_id=claims.get("cid") or claims.get("client_id"),
        user_id=claims.get("sub"),
    )

    validation_duration_ms = (time.monotonic() - start_time) * 1000
    logger.info(
        "oauth_token_validated",
        token_hash=token_hash[:8],
        client_id=auth_context.client_id,
        user_id=auth_context.user_id,
        duration_ms=round(validation_duration_ms, 2),
    )

    if validation_duration_ms > OAUTH_VALIDATION_TIMEOUT_MS:
        logger.warning(
            "oauth_validation_performance_alert",
            duration_ms=round(validation_duration_ms, 2),
            threshold_ms=OAUTH_VALIDATION_TIMEOUT_MS,
        )

    return auth_context


def _build_oauth_error_response_json(
    error: str, description: str, status_code: int = 401
) -> JSONResponse:
    """Builds an OAuth 2.0 compliant error JSONResponse."""
    content = {"error": error, "error_description": description}
    headers = {"WWW-Authenticate": f'Bearer error="{error}", error_description="{description}"'}
    return JSONResponse(content=content, status_code=status_code, headers=headers)


class OAuthMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for OAuth 2.0 bearer token validation using JWKS.
    """

    def __init__(self, app: ASGIApp, exclude_paths: list[str] | None = None) -> None:
        super().__init__(app)
        self.exclude_paths = set(exclude_paths or [])
        self.config = get_config()


        if not self.config.keycloak_url or not self.config.keycloak_realm:
            raise ValueError("KEYCLOAK_URL and KEYCLOAK_REALM must be configured.")

        self.issuer = f"{self.config.keycloak_url.rstrip('/')}/realms/{self.config.keycloak_realm}"
        # This is a temporary measure. In a real scenario, this would be discovered.
        self.jwks_uri = f"{self.issuer}/protocol/openid-connect/certs"

        logger.info(
            "oauth_middleware_initialized",
            issuer=self.issuer,
            jwks_uri=self.jwks_uri,
            exclude_paths=list(self.exclude_paths),
        )

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """
        Processes the request, handles OAuth validation, and passes to the next middleware/route.
        """
        # Skip auth entirely for excluded paths
        if request.url.path in self.exclude_paths:
            return await call_next(request)

        # Check if request path starts with /mcp (mounted MCP app) - needs special handling
        is_mcp_path = request.url.path.startswith("/mcp")

        authorization_header = request.headers.get("authorization")
        if not authorization_header:
            return _build_oauth_error_response_json(
                "invalid_request", "Authorization header is missing", 401
            )

        if not authorization_header.startswith("Bearer "):
            return _build_oauth_error_response_json(
                "invalid_request", "Authorization header must be in 'Bearer <token>' format", 401
            )

        bearer_token = authorization_header[7:]
        token_hash = hashlib.sha256(bearer_token.encode()).hexdigest()

        try:
            auth_context = await validate_token_with_authlib(
                bearer_token, token_hash, self.issuer, self.jwks_uri
            )
        except OAuthError as e:
            return _build_oauth_error_response_json(e.error, e.description, e.status_code)

        # Attach auth context and proceed
        request.state.auth_context = auth_context
        auth_context_var.set(auth_context)
        response = await call_next(request)

        # Skip header modification for MCP paths (SSE streams from mounted app)
        # Headers cannot be modified after SSE streaming starts
        if not is_mcp_path:
            # Add security headers to regular HTTP responses
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        return response
