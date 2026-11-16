"""Active permission catalog for isolated authorization tests."""

from coyote.config.governance_catalog import load_governance_catalog


class PermissionCatalog:
    """Expose installed permissions without connecting to identity persistence."""

    def get_all_permissions(self, *, is_active=True):
        """Return bundled permissions matching the requested activation state."""
        return [
            document
            for document in load_governance_catalog("permissions")
            if document.get("is_active", True) == is_active
        ]
