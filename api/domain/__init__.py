"""API domain package.

This package is restricted to domain models and model-level types.
Business validators and workflow logic belong to `api/core/*`.
"""

from api.domain.models.user import UserModel

__all__ = ["UserModel"]
