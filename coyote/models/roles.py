# coyote/models/roles.py

from typing import List, Dict


class RolesModel:
    """
    Manages static role metadata, default permissions, and hierarchy levels.
    """

    ROLES: Dict[str, Dict] = {
        "admin": {
            "level": 5,
            "label": "Administrator",
            "color": "red",
            "permissions": ["*"],
            "description": "Full access to everything.",
        },
        "developer": {
            "level": 4,
            "label": "Developer",
            "color": "purple",
            "permissions": [
                "view_assay_config",
                "edit_assay_config",
                "delete_sample",
                "create_assay",
                "create_sample",
                "manage_users",
                "run_jobs",
            ],
            "description": "Can configure and test systems.",
        },
        "group_manager": {
            "level": 3,
            "label": "Group Manager",
            "color": "blue",
            "permissions": [
                "view_assay_config",
                "edit_assay_config",
                "create_sample",
                "manage_group_users",
            ],
            "description": "Manages users and samples within a group.",
        },
        "user": {
            "level": 2,
            "label": "Standard User",
            "color": "green",
            "permissions": ["view_assay_config", "create_sample"],
            "description": "Can create and view samples.",
        },
        "viewer": {
            "level": 1,
            "label": "Viewer",
            "color": "gray",
            "permissions": ["view_assay_config"],
            "description": "Read-only access to assigned data.",
        },
        "external": {
            "level": 0,
            "label": "External",
            "color": "lightgray",
            "permissions": [],
            "description": "No default access.",
        },
    }

    def __init__(self):
        self.roles = self.ROLES

    def get_roles(self) -> Dict[str, Dict]:
        return self.roles

    def get_role_level(self, role: str) -> int:
        return self.roles.get(role, {}).get("level", -1)

    def get_role_label(self, role: str) -> str:
        return self.roles.get(role, {}).get("label", role)

    def get_role_color(self, role: str) -> str:
        return self.roles.get(role, {}).get("color", "black")

    def get_permissions(self, role: str) -> List[str]:
        return self.roles.get(role, {}).get("permissions", [])

    def has_min_role(self, user_role: str, required_role: str) -> bool:
        return self.get_role_level(user_role) >= self.get_role_level(required_role)

    def is_valid_role(self, role: str) -> bool:
        return role in self.roles
