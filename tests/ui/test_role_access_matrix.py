"""Role-based UI route access matrix tests."""

from __future__ import annotations

import pytest


@pytest.mark.parametrize(
    ("client_fixture", "path", "expected_status"),
    [
        ("anonymous_client", "/dashboard/", 302),
        ("viewer_client", "/dashboard/", 200),
        ("user_client", "/dashboard/", 200),
        ("manager_client", "/dashboard/", 200),
        ("admin_client", "/dashboard/", 200),
        ("anonymous_client", "/samples", 302),
        ("viewer_client", "/samples", 200),
        ("user_client", "/samples", 200),
        ("manager_client", "/samples", 200),
        ("admin_client", "/samples", 200),
        ("anonymous_client", "/samples/edit/s1", 302),
        ("viewer_client", "/samples/edit/s1", 200),
        ("user_client", "/samples/edit/s1", 200),
        ("manager_client", "/samples/edit/s1", 200),
        ("admin_client", "/samples/edit/s1", 200),
        ("viewer_client", "/dna/s1/var/v1", 200),
        ("user_client", "/dna/s1/var/v1", 200),
        ("manager_client", "/dna/s1/var/v1", 200),
        ("admin_client", "/dna/s1/var/v1", 200),
        ("viewer_client", "/dna/s1/cnv/cnv1", 200),
        ("user_client", "/dna/s1/cnv/cnv1", 200),
        ("manager_client", "/dna/s1/cnv/cnv1", 200),
        ("admin_client", "/dna/s1/cnv/cnv1", 200),
        ("viewer_client", "/cov/s1", 200),
        ("user_client", "/cov/s1", 200),
        ("manager_client", "/cov/s1", 200),
        ("admin_client", "/cov/s1", 200),
        ("anonymous_client", "/admin/ingest", 302),
        ("viewer_client", "/admin/ingest", 403),
        ("user_client", "/admin/ingest", 403),
        ("manager_client", "/admin/ingest", 403),
        ("admin_client", "/admin/ingest", 200),
        ("anonymous_client", "/dna/sample/SAMPLE_001/reports/preview", 302),
        ("viewer_client", "/dna/sample/SAMPLE_001/reports/preview", 200),
        ("user_client", "/dna/sample/SAMPLE_001/reports/preview", 200),
        ("manager_client", "/dna/sample/SAMPLE_001/reports/preview", 200),
        ("admin_client", "/dna/sample/SAMPLE_001/reports/preview", 200),
    ],
)
def test_ui_role_access_matrix(request, client_fixture: str, path: str, expected_status: int):
    """Assert the current route-access behavior for representative UI pages."""
    client = request.getfixturevalue(client_fixture)
    response = client.get(path)
    assert response.status_code == expected_status, (client_fixture, path, response.status_code)
