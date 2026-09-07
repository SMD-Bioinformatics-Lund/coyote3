"""Authentication dependencies."""

from api.security.access import require_access, require_authenticated

__all__ = ["require_access", "require_authenticated"]
