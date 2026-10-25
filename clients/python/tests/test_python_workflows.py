"""Python client coverage for clinical workflows and general UI endpoint access."""

import json

import httpx
import pytest
from coyote3_client import CoyoteClient
from coyote3_client.endpoints import ApiEndpoint


@pytest.fixture
def workflow_client():
    requests = []

    def respond(request):
        requests.append(request)
        if request.url.path.endswith("/auth/session"):
            return httpx.Response(200, json={"user": {"username": "synthetic"}})
        if request.url.path.endswith("/tiered"):
            return httpx.Response(
                200, json=[{"_id": "demo-variant", "classification": {"class": 2}}]
            )
        if request.url.path.endswith("/edit-context"):
            return httpx.Response(200, json={"sample": {"name": "DEMO_001"}, "comments": []})
        if request.url.path.endswith("/preview"):
            return httpx.Response(
                200,
                json={
                    "meta": {"preview_fingerprint": "a" * 64},
                    "report": {"html": "<p>Synthetic</p>", "context": {}},
                },
            )
        if request.url.path.endswith("/reports/dna"):
            return httpx.Response(201, json={"report": {"id": "demo-report", "file": "demo.html"}})
        if request.method == "GET" and request.url.path.endswith("/demo-finding"):
            kind = next(
                value
                for key, value in {
                    "small-variants": "variant",
                    "cnvs": "cnv",
                    "fusions": "fusion",
                    "translocations": "translocation",
                }.items()
                if key in request.url.path
            )
            return httpx.Response(200, json={"sample": {}, kind: {"_id": "demo-finding"}})
        if request.method == "GET" and request.url.path.split("/")[-1] in (
            "small-variants",
            "cnvs",
            "fusions",
            "translocations",
        ):
            segment = request.url.path.split("/")[-1]
            rows = [{"_id": "demo-finding"}]
            body = (
                {"display_sections_data": {"snvs": rows}}
                if segment == "small-variants"
                else {segment: rows}
            )
            return httpx.Response(
                200, json={**body, "meta": {"page": 2, "per_page": 50, "has_next": False}}
            )
        return httpx.Response(
            200, json={"status": "ok", "sample_id": "demo", "action": "synthetic"}
        )

    with CoyoteClient(
        "https://example.test/mounted", transport=httpx.MockTransport(respond)
    ) as client:
        client.login_with_token("synthetic-token")
        requests.clear()
        yield client, requests


@pytest.mark.parametrize(
    "collection,path,resource_type",
    [
        ("variants", "small-variants", "small_variant"),
        ("cnvs", "cnvs", "cnv"),
        ("fusions", "fusions", "fusion"),
        ("translocations", "translocations", "translocation"),
    ],
)
def test_nested_finding_workflows(workflow_client, collection, path, resource_type):
    client, requests = workflow_client
    findings = getattr(client.samples.ref("demo::sample"), collection)
    finding = findings.ref("demo-finding")
    assert requests == []
    findings.list(page=2, per_page=50, q="synthetic", intent="somatic")
    assert requests[-1].url.path == f"/mounted/api/v1/samples/demo::sample/{path}"
    assert requests[-1].url.params["page"] == "2"
    finding.read()
    assert requests[-1].url.path.endswith(f"/{path}/demo-finding")
    finding.set_flag("interesting")
    assert requests[-1].method == "PATCH"
    assert requests[-1].url.path.endswith(f"/{path}/demo-finding/flags/interesting")
    finding.set_flag("interesting", apply=False)
    assert requests[-1].method == "DELETE"
    findings.set_tier(["demo-finding"], 2, include_automatic_text=True)
    assert requests[-1].url.path.endswith("/classifications/tier")
    assert requests[-1].method == "PATCH"
    assert json.loads(requests[-1].content) == {
        "resource_type": resource_type,
        "resource_ids": ["demo-finding"],
        "tier": 2,
        "apply": True,
        "include_automatic_text": True,
    }
    findings.set_tier(["demo-finding"], 2, apply=False)
    assert json.loads(requests[-1].content)["apply"] is False
    assert all(request.headers["authorization"] == "Bearer synthetic-token" for request in requests)


def test_tiered_variants_uses_server_selection(workflow_client):
    client, requests = workflow_client
    result = client.samples.ref("demo").variants.tiered_variants(intent="germline", q="gene")
    assert result[0].id == "demo-variant"
    assert result[0].classification.class_value == 2
    assert len(requests) == 1
    assert requests[0].url.path == "/mounted/api/v1/samples/demo/small-variants/tiered"
    assert dict(requests[0].url.params) == {"intent": "germline", "q": "gene"}


@pytest.mark.parametrize("tier", [0, 5, True, 2.0, "2"])
def test_invalid_tier_cannot_silently_become_tier_three(workflow_client, tier):
    client, requests = workflow_client
    with pytest.raises(ValueError):
        client.samples.ref("demo").variants.set_tier(["demo-finding"], tier)
    assert requests == []


def test_sample_context_comments_and_report_save(workflow_client):
    client, requests = workflow_client
    sample = client.samples.ref("demo")
    sample.context()
    assert requests[-1].url.path.endswith("/samples/demo/edit-context")
    sample.comments.post(json={"form_data": {"sample_comment": "Synthetic review"}})
    assert requests[-1].url.path.endswith("/samples/demo/comments")
    assert json.loads(requests[-1].content)["form_data"]["sample_comment"] == "Synthetic review"
    sample.comments["demo-comment"].hidden.patch()
    assert requests[-1].url.path.endswith("/comments/demo-comment/hidden")
    preview = sample.reports.preview("dna", include_snapshot=True)
    assert requests[-1].url.path.endswith("/reports/dna/preview")
    fingerprint = preview.meta.preview_fingerprint
    sample.reports.save("dna", preview_fingerprint=fingerprint)
    assert requests[-1].url.path.endswith("/reports/dna")
    assert json.loads(requests[-1].content) == {"preview_fingerprint": fingerprint}
    assert len(requests) == 5  # Save does not refresh the preview or retry a mutation.


@pytest.mark.parametrize(
    "path,method",
    [
        (("admin", "clinical-rules", "demo", "publish"), "POST"),
        (("resources", "aspc", "demo::test"), "PUT"),
        (("users", "demo", "status"), "PATCH"),
        (("roles", "demo"), "DELETE"),
        (("dashboard", "metrics", "summary"), "GET"),
        (("common", "search", "tiered_variants"), "GET"),
        (("notifications",), "GET"),
    ],
)
def test_other_ui_endpoints_are_not_limited_to_metadata(workflow_client, path, method):
    client, requests = workflow_client
    endpoint = client.api
    for segment in path:
        endpoint = endpoint[segment]
    assert isinstance(endpoint, ApiEndpoint)
    assert requests == []
    getattr(endpoint, method.lower())(json={"synthetic": True}, params={"page": 2})
    assert requests[-1].method == method
    assert requests[-1].url.path == "/mounted/api/v1/" + "/".join(path)
    assert json.loads(requests[-1].content) == {"synthetic": True}
    assert requests[-1].url.params["page"] == "2"


def test_upload_and_exact_segment_spelling(workflow_client):
    client, requests = workflow_client
    client.api.internal.ingest.sample_bundle.upload["async"].post(
        files={"manifest": ("demo.yaml", b"name: DEMO_001\n", "application/yaml")}
    )
    assert requests[-1].url.path == "/mounted/api/v1/internal/ingest/sample-bundle/upload/async"
    assert requests[-1].headers["content-type"].startswith("multipart/form-data;")
    assert b"name: DEMO_001" in requests[-1].content
    client.api.resources.asp["create_context"].get()
    assert requests[-1].url.path.endswith("/resources/asp/create_context")


@pytest.mark.parametrize(
    "media_type,content,expected",
    [
        ("application/pdf", b"%PDF-synthetic", b"%PDF-synthetic"),
        ("text/html; charset=utf-8", b"<p>Synthetic</p>", "<p>Synthetic</p>"),
        ("application/problem+json", b'{"error":"example"}', {"error": "example"}),
        ("application/octet-stream", b"\x00\xff", b"\x00\xff"),
        ("application/json", b"null", None),
        ("application/json", b"", None),
    ],
)
def test_response_content_types(media_type, content, expected):
    def respond(request):
        if request.url.path.endswith("/auth/session"):
            return httpx.Response(200, json={"user": {"username": "synthetic"}})
        return httpx.Response(200, content=content, headers={"content-type": media_type})

    with CoyoteClient("https://example.test", transport=httpx.MockTransport(respond)) as client:
        client.login_with_token("synthetic-token")
        assert client.api.samples["demo"].reports["report"].pdf.get() == expected
        if media_type == "application/pdf" or media_type.startswith("text/html"):
            file_type = "pdf" if media_type == "application/pdf" else "html"
            assert (
                client.samples.ref("demo").reports.download("report", file_type=file_type)
                == expected
            )


def test_event_stream_closes_response_and_keeps_authentication(workflow_client):
    client, requests = workflow_client
    with client.api.internal.ingest.events.stream(params={"task_id": "demo-task"}) as response:
        assert response.status_code == 200
        assert list(response.iter_bytes())
        assert requests[-1].headers["authorization"] == "Bearer synthetic-token"
    assert response.is_closed
    client.logout()
    with pytest.raises(RuntimeError):
        with client.api.notifications.stream():
            pytest.fail("Unauthenticated stream must not open")


@pytest.mark.parametrize("segment", ["..", ".", "", "../users", "https://other.test", "a\\b"])
def test_endpoint_navigation_rejects_path_injection(workflow_client, segment):
    client, requests = workflow_client
    with pytest.raises(ValueError):
        client.api[segment]
    assert requests == []


def test_error_from_report_save_is_never_retried():
    requests = []

    def respond(request):
        requests.append(request)
        if request.url.path.endswith("/auth/session"):
            return httpx.Response(200, json={"user": {"username": "synthetic"}})
        return httpx.Response(409, json={"error": "Preview inputs changed"})

    with CoyoteClient("https://example.test", transport=httpx.MockTransport(respond)) as client:
        client.login_with_token("synthetic-token")
        with pytest.raises(httpx.HTTPStatusError) as error:
            client.samples.ref("demo").reports.save("dna", preview_fingerprint="a" * 64)
        assert error.value.response.status_code == 409
        assert len(requests) == 2
