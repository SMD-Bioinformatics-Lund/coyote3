# coyote/services/permissions.py

from coyote.models.roles import RolesModel


class PermissionService:
    """
    Builds a permission context for a user based on their role and any overrides.
    """

    def __init__(self, user, roles_model: RolesModel):
        self.user = user
        self.roles_model = roles_model

        self.role = getattr(user, "role", "external") or "external"
        self.role_permissions = set(roles_model.get_permissions(self.role))
        self.extra_permissions = set(getattr(user, "extra_permissions", []) or [])
        self.restricted_permissions = set(getattr(user, "restricted_permissions", []) or [])

        self.effective_permissions = (
            self.role_permissions | self.extra_permissions
        ) - self.restricted_permissions

    def can(self, permission: str) -> bool:
        return "*" in self.effective_permissions or permission in self.effective_permissions

    def has_min_role(self, required_role: str) -> bool:
        return self.roles_model.has_min_role(self.role, required_role)

    def all_permissions(self):
        return list(self.effective_permissions)
