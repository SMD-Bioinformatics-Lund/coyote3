"""Protected internal reference and metric route behavior."""

from types import SimpleNamespace

from api_test_support import application_sdk as sdk_fixtures
from coyote_api.interfaces.http.v1.operations import internal
from coyote_api.security import access


def test_get_role_levels_internal_returns_id_to_level_map(monkeypatch):
    calls = {"token": 0}

    monkeypatch.setattr(
        access, "_require_internal_token", lambda _request: calls.__setitem__("token", 1)
    )
    roles_repository = SimpleNamespace(
        get_all_roles=lambda: [{"role_id": "admin", "level": 99}, {"role_id": "viewer"}]
    )

    payload = internal.get_role_levels_internal(
        request=object(),
        service=sdk_fixtures.internal_reference_operations(
            roles=roles_repository, request=object()
        ),
    )

    assert calls["token"] == 1
    assert payload["status"] == "ok"
    assert payload["role_levels"] == {"admin": 99, "viewer": 0}


def test_get_isgl_meta_internal_reads_adhoc_and_display_name(monkeypatch):
    calls = {"token": 0}

    monkeypatch.setattr(
        access, "_require_internal_token", lambda _request: calls.__setitem__("token", 1)
    )
    gene_list_repository = SimpleNamespace(
        is_isgl_adhoc=lambda _isgl_id: True,
        get_isgl_display_name=lambda _isgl_id: "Focus Panel",
    )

    payload = internal.get_isgl_meta_internal(
        "isgl123",
        request=object(),
        service=sdk_fixtures.internal_reference_operations(
            gene_lists=gene_list_repository, request=object()
        ),
    )

    assert calls["token"] == 1
    assert payload == {
        "status": "ok",
        "isgl_id": "isgl123",
        "is_adhoc": True,
        "display_name": "Focus Panel",
    }


def test_get_prometheus_metrics_internal_requires_internal_token(monkeypatch):
    calls = {"checked": 0}
    monkeypatch.setattr(
        internal, "_require_internal_token", lambda _request: calls.__setitem__("checked", 1)
    )
    monkeypatch.setattr(
        internal,
        "render_prometheus_metrics",
        lambda: "# HELP coyote4_api_requests_total test\n",
    )

    response = internal.get_prometheus_metrics_internal(request=object())

    assert calls["checked"] == 1
    assert response.status_code == 200
    assert "coyote4_api_requests_total" in response.body.decode("utf-8")
