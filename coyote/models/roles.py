# coyote/models/roles.py

from typing import List, Dict


class RolesModel:
    """
    Manages static role metadata, default permissions, and hierarchy levels.
    """

    PERMISSIONS_APPROVED_LIST: List[str] = [
        "view_sample_global",
        "edit_sample_global",
        "delete_sample_global",
        "view_assay_config",
        "create_assay_config",
        "edit_assay_config",
        "delete_assay_config",
        "view_schemas",
        "create_schema",
        "edit_schemas",
        "delete_schemas",
        "manage_users",
        "view_users",
        "create_users",
        "edit_users",
        "delete_users",
        "view_audit_logs",
        "edit_user_groups",
        "edit_self_groups",
        "edit_user_role",
        "edit_self_role",
        "edit_user_info",
        "edit_self_info",
        "add_gene_panel",
        "edit_gene_panel",
        "delete_gene_panel",
        "view_gene_panel",
        "view_sample",
        "apply_dna_filters",
        "apply_dna_gene_filters",
        "modify_dna_variants",
        "blacklist_dna_variants",
        "unblacklist_dna_variants",
        "modify_dna_sample_comments",
        "hide_dna_sample_comments",
        "unhide_dna_sample_comments",
        "write_dna_sample_comments",
        "preview_dna_sample_report",
        "download_dna_sample_report",
        "tier_dna_variant",
        "remove_dna_variant_tier",
        "remove_dna_variant_history_tier",
        "remove_dna_variant_historic_tier_comment",
        "remove_dna_variant_tier_comment",
        "write_dna_variant_tier_comment",
        "view_igv",
    ]

    PERMISSIONS_DENYED_LIST: List[str] = [
        "view_sample",
        "edit_sample",
        "delete_sample",
        "view_assay_config",
        "create_assay_config",
        "edit_assay_config",
        "delete_assay_config",
        "view_schemas",
        "create_schema",
        "edit_schemas",
        "delete_schemas",
        "manage_users",
        "view_users",
        "create_users",
        "readonly",
    ]

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
                "create_assay_config",
                "view_assay_config",
                "edit_assay_config",
                "delete_assay_config",
                "create_schema",
                "view_schemas",
                "edit_schemas",
                "delete_schemas",
                "delete_sample",
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
