# UI Permission Testing

Use the shared UI role fixtures in `tests/ui/conftest.py` when you need to verify what a Flask route does for a given signed-in role.

## Available Fixtures

- `anonymous_client`
  Returns a plain Flask test client with no authenticated session.
- `viewer_client`
  Returns a signed-in client with `role="viewer"` and `access_level=1`.
- `user_client`
  Returns a signed-in client with `role="user"` and `access_level=9`.
- `manager_client`
  Returns a signed-in client with `role="manager"` and `access_level=99`.
- `admin_client`
  Returns a signed-in client with `role="admin"` and `access_level=99999`.

These fixtures use the same session payload key and API session cookie flow that the real login blueprint uses. They do not patch template globals or bypass Flask-Login.

## What The Fixtures Stub

The UI clients boot the real Flask app and stub the web API client with snapshot-shaped payloads from `tests/fixtures/api/mock_collections.py`.

That keeps the tests aligned with the actual document shapes used by the backend:

- sample documents come from `sample_doc()`
- small variants come from `variant_doc()`
- CNVs come from `cnv_doc()`
- assay configs come from `assay_config_doc()`
- ISGL data comes from `isgl_doc()`

## Writing A Route Access Matrix

Use a parametrized test over `(client_fixture, path, expected_status)` pairs.

```python
@pytest.mark.parametrize(
    ("client_fixture", "path", "expected_status"),
    [
        ("anonymous_client", "/dashboard/", 302),
        ("viewer_client", "/dashboard/", 200),
        ("admin_client", "/admin/ingest", 200),
        ("viewer_client", "/admin/ingest", 403),
    ],
)
def test_ui_role_access_matrix(request, client_fixture, path, expected_status):
    client = request.getfixturevalue(client_fixture)
    response = client.get(path)
    assert response.status_code == expected_status
```

## What To Assert

Prefer assertions that describe real route behavior:

- `302`
  Use for anonymous users redirected to the login page by `@login_required`.
- `403`
  Use for authenticated users blocked by route-level authorization checks.
- `200`
  Use when the route is allowed and renders successfully.

## Important Scope Note

These tests verify server-side route behavior, not just template visibility.

That distinction matters because some pages still hide actions in Jinja based on `has_access(...)`, while the route itself may only require authentication. The matrix should reflect the current enforced behavior of the route, even if that reveals a future hardening gap.
