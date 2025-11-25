from contextvars import ContextVar

from src.models.auth import AuthContext

# Context variable to hold the authentication context for a request.
# This allows passing the auth context from the middleware to the application logic
# without altering function signatures, which is especially useful for compatibility
# with frameworks like FastMCP that abstract away the request object.
auth_context_var: ContextVar[AuthContext | None] = ContextVar("auth_context", default=None)
