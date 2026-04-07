"""Smoke tests for every endpoint exposed by the admin dashboard cards.

Walks the canonical ``_ADMIN_CARDS`` list and asserts each landing page loads
without raising for an authenticated admin user. Catches handler/signature
mismatches and missing-endpoint regressions (e.g. F2-1) before they reach prod.
"""

from __future__ import annotations

import pytest

# Endpoints listed explicitly (not imported from views_home) so collection
# does not require a Flask application context. Keep in sync with
# `coyote/blueprints/admin/views_home.py:_ADMIN_CARDS`.
ADMIN_ENDPOINTS = [
    "admin_bp.all_samples",
    "admin_bp.assay_configs",
    "admin_bp.audit",
    "admin_bp.create_assay_panel",
    "admin_bp.create_dna_assay_config",
    "admin_bp.create_genelist",
    "admin_bp.create_permission",
    "admin_bp.create_rna_assay_config",
    "admin_bp.create_role",
    "admin_bp.create_user",
    "admin_bp.ingest_workspace",
    "admin_bp.list_permissions",
    "admin_bp.list_roles",
    "admin_bp.manage_assay_panels",
    "admin_bp.manage_genelists",
    "admin_bp.manage_users",
]


def test_admin_endpoint_list_matches_card_definitions(admin_client) -> None:
    """Guard against drift between this smoke list and ``_ADMIN_CARDS``."""
    from coyote.blueprints.admin.views_home import _ADMIN_CARDS

    declared = sorted({card["endpoint"] for card in _ADMIN_CARDS})
    assert declared == sorted(ADMIN_ENDPOINTS), (declared, sorted(ADMIN_ENDPOINTS))


@pytest.mark.parametrize("endpoint", ADMIN_ENDPOINTS)
def test_admin_card_endpoint_loads_for_admin(admin_client, endpoint: str) -> None:
    """Every admin dashboard card endpoint must load (2xx) for an admin user."""
    from flask import url_for

    with admin_client.application.test_request_context():
        url = url_for(endpoint)

    response = admin_client.get(url)
    assert response.status_code == 200, (endpoint, url, response.status_code)
