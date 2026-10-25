"""Active permission catalog for isolated authorization tests."""

import json
from pathlib import Path


class PermissionCatalog:
    """Expose installed permissions without connecting to identity persistence."""

    def get_all_permissions(self, *, is_active=True):
        """Return bundled permissions matching the requested activation state."""
        path = (
            Path(__file__).resolve().parents[3]
            / "api/bootstrap/catalogs/rbac/permissions.seed.ndjson"
        )
        return [
            document
            for line in path.read_text().splitlines()
            if line.strip() and (document := json.loads(line)).get("is_active", True) == is_active
        ]
