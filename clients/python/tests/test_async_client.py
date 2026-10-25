"""Native async authentication, typed workflows, cancellation and transport errors."""

import asyncio

import httpx
import pytest
from coyote3_client import (
    AsyncCoyoteClient,
    AuthenticationError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    RequestValidationError,
    ResourceNotLoadedError,
    ResponseValidationError,
)


@pytest.fixture
def wire():
    requests = []
    state = {"status": 200, "payload": {"name": "SYNTHETIC", "reported": False}}

    async def respond(request):
        await asyncio.sleep(0)
        requests.append(request)
        if request.url.path.endswith("/auth/sessions"):
            return httpx.Response(
                201,
                json={"user": {"username": "synthetic"}},
                headers={"set-cookie": "test_session=synthetic-token; HttpOnly; Secure"},
            )
        if request.url.path.endswith("/auth/session"):
            return httpx.Response(200, json={"user": {"username": "synthetic"}})
        if request.url.path.endswith("/tiered"):
            return httpx.Response(
                200, json=[{"_id": "synthetic-variant", "classification": {"class": 2}}]
            )
        if request.url.path.endswith("/try-new"):
            return httpx.Response(
                200,
                json={
                    "html": "<html>Clinical content</html>",
                    "pdf_base64": "JVBERi0=",
                    "filename": "coyote3_dna_report_trial",
                    "snapshot_count": 1,
                },
            )
        return httpx.Response(state["status"], json=state["payload"])

    return requests, state, httpx.MockTransport(respond)


@pytest.mark.asyncio
async def test_async_password_login_typed_sample_and_concurrent_clinical_reads(wire):
    requests, _, transport = wire
    async with AsyncCoyoteClient(
        "https://example.test/mounted", cookie_name="test_session", transport=transport
    ) as client:
        user = await client.login(
            username="synthetic", password="temporary-example", provider="local"
        )
        assert user.username == "synthetic"
        assert client.session_token == "synthetic-token"
        sample = await client.samples.get("SYNTHETIC")
        assert sample.name == "SYNTHETIC" and sample.reported is False
        variants, trial = await asyncio.gather(
            sample.variants.tiered_variants(), sample.reports.try_new("dna")
        )
        assert variants[0].classification.class_value == 2
        assert trial.snapshot_count == 1
        assert all(r.headers.get("authorization") == "Bearer synthetic-token" for r in requests[1:])
        assert all("cookie" not in r.headers for r in requests[1:])
        assert requests[0].url.path == "/mounted/api/v1/auth/sessions"
        assert requests[0].extensions["timeout"]["read"] == 30.0
        await client.logout()
        assert client.session_token is None
        with pytest.raises(ResourceNotLoadedError):
            _ = sample.data
        with pytest.raises(RuntimeError, match="Log in"):
            await client.api.users.get()
    assert client._http.is_closed


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,error",
    [
        (401, AuthenticationError),
        (403, PermissionDeniedError),
        (404, NotFoundError),
        (409, ConflictError),
        (422, RequestValidationError),
        (429, RateLimitError),
    ],
)
async def test_async_server_errors_preserve_http_status_and_do_not_retry(wire, status, error):
    requests, state, transport = wire
    async with AsyncCoyoteClient("https://example.test", transport=transport) as client:
        await client.login_with_token("synthetic-token")
        state.update(status=status, payload={"error": "Synthetic rejection"})
        with pytest.raises(error) as raised:
            await client.samples.get("SYNTHETIC")
        assert raised.value.response.status_code == status
        assert len(requests) == 2


@pytest.mark.asyncio
async def test_async_pagination_preserves_done_stream_and_invalidates_on_identity_change(wire):
    requests, state, transport = wire
    state["payload"] = {
        "done_samples": [{"name": "SYNTHETIC"}],
        "done_page": 2,
        "done_per_page": 10,
        "done_total": 21,
        "has_next_done": True,
    }
    async with AsyncCoyoteClient("https://example.test", transport=transport) as client:
        await client.login_with_token("synthetic-token")
        pages = client.samples.pages(status="done", start_page=2, per_page=10)
        assert len(requests) == 1
        page = await anext(pages)
        assert page.items[0].name == "SYNTHETIC"
        assert requests[-1].url.params["done_page"] == "2"
        assert requests[-1].url.params["done_per_page"] == "10"
        await client.login_with_token("another-token")
        with pytest.raises(ResourceNotLoadedError):
            await anext(pages)


@pytest.mark.asyncio
async def test_async_stream_closes_when_consumer_is_cancelled(wire):
    _, _, transport = wire
    async with AsyncCoyoteClient("https://example.test", transport=transport) as client:
        await client.login_with_token("synthetic-token")
        with pytest.raises(asyncio.CancelledError):
            async with client.api.reports["synthetic-report"].pdf.stream() as response:
                raise asyncio.CancelledError()
        assert response.is_closed


@pytest.mark.asyncio
async def test_async_transport_timeout_is_exposed_without_retry():
    async def respond(request):
        raise httpx.ReadTimeout("Synthetic timeout", request=request)

    async with AsyncCoyoteClient(
        "https://example.test", transport=httpx.MockTransport(respond)
    ) as client:
        with pytest.raises(httpx.ReadTimeout):
            await client.login_with_token("synthetic-token")
        assert client.user is None


@pytest.mark.asyncio
async def test_async_rejects_malformed_responses_and_ambiguous_pagination(wire):
    _, state, transport = wire
    async with AsyncCoyoteClient("https://example.test", transport=transport) as client:
        await client.login_with_token("synthetic-token")
        state["payload"] = {"unexpected": True}
        with pytest.raises(ResponseValidationError):
            await client.samples.get("SYNTHETIC")
        with pytest.raises(ValueError, match="selected sample stream"):
            await client.samples.list(done_page=2)
