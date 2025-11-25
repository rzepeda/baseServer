import hashlib
import time
from datetime import UTC, datetime, timedelta

import httpx
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from src.config import get_config
from src.models.auth import AuthContext, OAuthConfig
from src.utils.context import auth_context_var
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Constants
OAUTH_VALIDATION_TIMEOUT_MS = 500


class OAuthError(Exception):
    """Custom exception for OAuth related errors."""

    def __init__(self, error: str, description: str, status_code: int):
        self.error = error
        self.description = description
        self.status_code = status_code
        super().__init__(f"{error}: {description}")


async def validate_token_with_provider(
    token: str, token_hash: str, oauth_config: OAuthConfig, client: httpx.AsyncClient
) -> AuthContext:
    """Validates the token with the OAuth provider. Standalone for testability."""
    start_time = time.monotonic()
    headers = {"Authorization": f"Bearer {token}"}

    try:
        response = await client.post(
            str(oauth_config.validation_endpoint),
            headers=headers,
            timeout=OAUTH_VALIDATION_TIMEOUT_MS / 1000.0,
        )
        response.raise_for_status()
        validation_data = response.json()
    except httpx.TimeoutException as e:
        logger.error("oauth_provider_timeout", exc_info=e, token_hash=token_hash[:8])
        raise OAuthError("server_error", "OAuth provider connection timed out", 504) from e
    except httpx.HTTPStatusError as e:
        error_msg = f"OAuth provider returned {e.response.status_code}."
        logger.warning(
            "oauth_provider_validation_failed",
            token_hash=token_hash[:8],
            status_code=e.response.status_code,
            response_body=e.response.text,
        )
        try:
            provider_error = e.response.json()
            error = provider_error.get("error", "invalid_token")
            description = provider_error.get("error_description", error_msg)
        except ValueError:
            error = "invalid_token"
            description = error_msg

        status_code = e.response.status_code
        if status_code not in {401, 403}:
            status_code = 500
            error = "server_error"
            description = "OAuth provider error"
        raise OAuthError(error, description, status_code) from e
    except Exception as e:
        logger.error("oauth_provider_request_error", exc_info=e, token_hash=token_hash[:8])
        raise OAuthError("server_error", "Failed to connect to OAuth provider", 500) from e

    is_active = validation_data.get("active", True)
    if not is_active:
        raise OAuthError("invalid_token", "Token is inactive", 401)

    scopes = validation_data.get("scope", "").split()
    client_id = validation_data.get("client_id")
    expires_at_timestamp = validation_data.get("exp")

    expires_at = None
    if expires_at_timestamp:
        try:
            expires_at = datetime.fromtimestamp(expires_at_timestamp, tz=UTC)
        except Exception:
            logger.warning(
                "oauth_invalid_exp_timestamp", exp=expires_at_timestamp, token_hash=token_hash[:8]
            )

    auth_context = AuthContext(
        is_valid=True,
        token_hash=token_hash,
        scopes=scopes,
        expires_at=expires_at,
        client_id=client_id,
    )

    validation_duration_ms = (time.monotonic() - start_time) * 1000
    logger.info(
        "oauth_token_validated",
        token_hash=token_hash[:8],
        client_id=client_id,
        scopes=scopes,
        duration_ms=round(validation_duration_ms, 2),
    )

    if validation_duration_ms > OAUTH_VALIDATION_TIMEOUT_MS:
        logger.warning(
            "oauth_validation_performance_alert",
            token_hash=token_hash[:8],
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


class TokenCache:
    """Simple in-memory cache for OAuth tokens with TTL."""

    def __init__(self, ttl_seconds: int) -> None:
        self.ttl_seconds = ttl_seconds
        self._cache: dict[str, tuple[AuthContext, datetime]] = {}

    def get(self, token_hash: str) -> AuthContext | None:
        """Retrieves a cached AuthContext if valid and not expired."""
        entry = self._cache.get(token_hash)
        if entry:
            auth_context, expiration_time = entry
            if expiration_time > datetime.now(UTC):
                logger.debug(
                    "token_cache_hit", token_hash=token_hash[:8], expires_at=expiration_time
                )
                return auth_context
            else:
                logger.debug(
                    "token_cache_expired", token_hash=token_hash[:8], expires_at=expiration_time
                )
                self.delete(token_hash)
        logger.debug("token_cache_miss", token_hash=token_hash[:8])
        return None

    def set(self, token_hash: str, auth_context: AuthContext):
        """Caches an AuthContext with a calculated expiration time."""
        if self.ttl_seconds <= 0:
            return
        expiration_time = datetime.now(UTC) + timedelta(seconds=self.ttl_seconds)
        self._cache[token_hash] = (auth_context, expiration_time)
        logger.debug(
            "token_cache_set",
            token_hash=token_hash[:8],
            expires_at=expiration_time,
            ttl=self.ttl_seconds,
        )

    def delete(self, token_hash: str):
        """Deletes an entry from the cache."""
        if token_hash in self._cache:
            del self._cache[token_hash]
            logger.debug("token_cache_deleted", token_hash=token_hash[:8])


class OAuthMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for OAuth 2.0 bearer token validation.
    Protects endpoints by validating tokens with an OAuth provider.
    """

    def __init__(self, app: ASGIApp, exclude_paths: list[str] | None = None) -> None:
        super().__init__(app)
        self.exclude_paths = set(exclude_paths or [])
        self.config = get_config()
        self.oauth_config = self.config.oauth_config
        self.token_cache = TokenCache(self.config.oauth_token_cache_ttl)

        if not self.config.oauth_token_cache_ttl:
            logger.warning("oauth_cache_disabled", reason="OAUTH_TOKEN_CACHE_TTL is 0")

        logger.info(
            "oauth_middleware_initialized",
            provider_url=self.oauth_config.provider_url,
            validation_endpoint=self.oauth_config.validation_endpoint,
            scopes=self.oauth_config.scopes,
            exclude_paths=list(self.exclude_paths),
        )

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """
        Processes the request, handles OAuth validation, and passes to the next middleware/route.
        """
        if request.url.path in self.exclude_paths:
            return await call_next(request)

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

        # Try fetching from cache first
        auth_context = self.token_cache.get(token_hash)

        if not auth_context:
            try:
                async with httpx.AsyncClient() as client:
                    auth_context = await validate_token_with_provider(
                        bearer_token, token_hash, self.oauth_config, client
                    )
                self.token_cache.set(token_hash, auth_context)
            except OAuthError as e:
                return _build_oauth_error_response_json(e.error, e.description, e.status_code)
            except Exception as e:
                logger.error(
                    "oauth_validation_unhandled_error", exc_info=e, token_hash=token_hash[:8]
                )
                return _build_oauth_error_response_json(
                    "server_error", "An unexpected error occurred during token validation", 500
                )

        # Attach auth context and proceed
        request.state.auth_context = auth_context
        auth_context_var.set(auth_context)
        response = await call_next(request)

        # Add security headers to all responses
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; preload"
        )
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        return response
