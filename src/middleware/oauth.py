"""OAuth2 middleware for verifying access tokens."""
# from collections.abc import Callable

# from authlib.oauth2.rfc7519 import JWTBearerTokenValidator
# from authlib.oauth2.rfc7519.errors import InvalidTokenError
# from authlib.integrations.starlette_client import OAuthError
# from authlib.jose import JsonWebKey, JWKSet
# from fastapi import HTTPException, Request, status
# from starlette.responses import Response

# from src.config import get_config
# from src.models.auth import AuthContext
# from src.utils.logging import get_logger

# logger = get_logger(__name__)

# # Initialize configuration
# config = get_config()

# # Setup JWKS client for fetching public keys
# jwks_client = JWKSet(
#     fetcher=lambda url: JsonWebKey.fetch_jwk_set(url),
#     uri=config.oauth_issuer_url + "/.well-known/jwks.json" # Assuming standard OIDC discovery
# )

# # Setup JWT Bearer Token Validator
# validator = JWTBearerTokenValidator(
#     jwks=jwks_client,
#     issuer=config.oauth_issuer_url,
#     audience=config.oauth_audience,
# )


# async def oauth_middleware(request: Request, call_next: Callable) -> Response:
#     """
#     Middleware for OAuth2 Bearer token validation.
#     Validates tokens for most endpoints, bypassing for specified paths.
#     """
#     allowed_paths = ["/health", "/tools/invoke", "/tools/list"]
#     if request.url.path in allowed_paths:
#         logger.debug(
#             "oauth_middleware.bypassing_auth", path=request.url.path
#         )
#         return await call_next(request)

#     authorization_header = request.headers.get("Authorization")

#     if not authorization_header or not authorization_header.startswith("Bearer "):
#         logger.info("oauth_middleware.missing_or_invalid_auth_header")
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token required"
#         )

#     token = authorization_header.split(" ")[1]

#     try:
#         claims = validator.validate_jwt(token)
#         user_id = claims.get("sub")
#         scopes = claims.get("scope", "").split()
#         client_id = claims.get("azp")  # Authorized party, common in OIDC

#         if not user_id:
#             logger.warning("oauth_middleware.missing_user_id_in_token", claims=claims)
#             raise HTTPException(
#                 status_code=status.HTTP_401_UNAUTHORIZED,
#                 detail="Invalid token: user ID (sub) not found",
#             )

#         auth_context = AuthContext(
#             user_id=user_id, token=token, scopes=scopes, client_id=client_id
#         )
#         request.state.auth_context = auth_context
#         logger.info("oauth_middleware.token_validated", user_id=user_id)

#     except InvalidTokenError as e:
#         logger.info("oauth_middleware.invalid_token", error=str(e))
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {e}"
#         ) from e
#     except OAuthError as e:
#         logger.error("oauth_middleware.oauth_error", error=str(e))
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED, detail=f"OAuth error: {e}"
#         ) from e
#     except Exception as e:
#         logger.error("oauth_middleware.unexpected_error", error=str(e))
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail="Internal server error during authentication",
#         ) from e

#     return await call_next(request)

async def oauth_middleware(request, call_next):
    """Placeholder for OAuth2 middleware when disabled."""
    return await call_next(request)