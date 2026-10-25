"""Client workflow URLs must exist in the authoritative FastAPI OpenAPI specification."""

import re

import httpx
import pytest
from coyote3_client import AsyncCoyoteClient, CoyoteClient

from api.app.main import create_api_app


@pytest.fixture
def contract_transport():
    """Reject client requests whose actual HTTP method/path is absent from OpenAPI."""
    paths = create_api_app().openapi()["paths"]
    calls = []

    def respond(request):
        path = request.url.path.removeprefix("/mounted")
        matched = [
            operations
            for template, operations in paths.items()
            if re.fullmatch(re.sub(r"\{[^}]+\}", "[^/]+", template), path)
        ]
        assert matched, f"Client invented an endpoint: {path}"
        assert request.method.lower() in matched[0], (request.method, path)
        calls.append((request.method, path))
        payload = {"name": "SYNTHETIC", "reported": False}
        if path.endswith("/auth/session"):
            payload = {"user": {"username": "synthetic"}}
        elif path.endswith("/tiered"):
            payload = [{"_id": "synthetic-variant"}]
        elif path.endswith("/try-new"):
            payload = {
                "html": "<p>Synthetic</p>",
                "pdf_base64": "JVBERi0=",
                "filename": "trial",
                "snapshot_count": 1,
            }
        elif path.endswith("/preview"):
            payload = {
                "meta": {"preview_fingerprint": "a" * 64},
                "report": {"html": "<p>Synthetic</p>", "context": {}},
            }
        elif path.endswith("/reports/dna") and request.method == "POST":
            payload = {"report": {"id": "synthetic-report", "file": "synthetic.html"}}
        elif path.endswith("/small-variants"):
            payload = {
                "display_sections_data": {"snvs": [{"_id": "synthetic-variant"}]},
                "meta": {"page": 1, "per_page": 50, "has_next": False},
            }
        return httpx.Response(200, json=payload)

    return httpx.MockTransport(respond), calls


def test_synchronous_typed_workflows_match_actual_server_operations(contract_transport):
    transport, calls = contract_transport
    with CoyoteClient("https://example.test/mounted", transport=transport) as client:
        client.login_with_token("synthetic-token")
        sample = client.samples.get("SYNTHETIC")
        sample.variants.list()
        sample.variants.tiered_variants()
        preview = sample.reports.preview("dna")
        sample.reports.save("dna", preview_fingerprint=preview.meta.preview_fingerprint)
        sample.reports.try_new("dna")
    assert len(calls) == 7


@pytest.mark.asyncio
async def test_asynchronous_typed_workflows_use_the_same_openapi_operations(contract_transport):
    transport, calls = contract_transport
    async with AsyncCoyoteClient("https://example.test/mounted", transport=transport) as client:
        await client.login_with_token("synthetic-token")
        sample = await client.samples.get("SYNTHETIC")
        await sample.variants.list()
        await sample.variants.tiered_variants()
        preview = await sample.reports.preview("dna")
        await sample.reports.save("dna", preview_fingerprint=preview.meta.preview_fingerprint)
        await sample.reports.try_new("dna")
    assert len(calls) == 7
