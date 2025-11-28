"""OAuth Discovery Endpoint Handler.

Proxies OAuth/OIDC discovery metadata from Keycloak to enable
Authorization Code flow for Claude.ai client integration.
"""

from typing import Any

import httpx
from fastapi import APIRouter, HTTPException

from src.config import get_config
from src.utils.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)

# Cache the metadata to avoid fetching it on every request
_cached_metadata: dict[str, Any] | None = None


@router.get("/.well-known/oauth-protected-resource", include_in_schema=False)
async def get_oauth_protected_resource_metadata() -> dict[str, Any]:
    """
    OAuth 2.0 Protected Resource Metadata endpoint for MCP.

    Returns metadata about this protected resource to help clients
    discover the authorization server information.

    Returns:
        dict: Protected resource metadata pointing to the auth server
    """
    config = get_config()

    # Return metadata pointing to the authorization server
    return {
        "resource": "mcp",
        "authorization_servers": [
            f"{config.keycloak_url.rstrip('/')}/realms/{config.keycloak_realm}"
        ]
    }


@router.get("/.well-known/oauth-authorization-server", include_in_schema=False)
async def get_oauth_discovery_document() -> dict[str, Any]:
    """
    OAuth 2.0 Authorization Server Metadata Discovery Endpoint.

    Proxies the OIDC discovery document from the configured Keycloak provider,
    ensuring that authorization_endpoint and other metadata are available for
    the Claude.ai client to initiate the Authorization Code flow.

    Returns:
        dict: OAuth/OIDC discovery metadata from Keycloak

    Raises:
        HTTPException: 503 if Keycloak is unreachable, 500 for unexpected errors
    """
    global _cached_metadata
    config = get_config()

    if _cached_metadata:
        logger.info("oauth_discovery_cache_hit")
        return _cached_metadata

    logger.info("oauth_discovery_cache_miss")
    metadata_url = f"{config.keycloak_url.rstrip('/')}/realms/{config.keycloak_realm}/.well-known/openid-configuration"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            logger.info("oauth_discovery_fetching_metadata", url=metadata_url)
            response = await client.get(metadata_url)
            response.raise_for_status()
            metadata = response.json()

            # Per the MCP spec, add PKCE support if not present
            if "code_challenge_methods_supported" not in metadata:
                metadata["code_challenge_methods_supported"] = ["S256", "plain"]
                logger.info("oauth_discovery_added_pkce_support")

            logger.info("oauth_discovery_fetch_success", issuer=metadata.get("issuer"))
            _cached_metadata = metadata
            return _cached_metadata
    except (httpx.RequestError, httpx.HTTPError) as e:
        logger.error(
            "oauth_discovery_provider_request_failed",
            error=str(e),
            url=metadata_url,
        )
        raise HTTPException(
            status_code=503,
            detail="Could not connect to the authentication provider.",
        )
    except Exception as e:
        logger.error(
            "oauth_discovery_unexpected_error",
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while fetching the authentication configuration.",
        )
