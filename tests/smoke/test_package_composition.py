"""Fast application-level checks across installed package boundaries."""

import httpx
import pytest
from bson import ObjectId
from coyote.contracts.resource_integrity import resource_content_hash
from coyote.domain.record_identity import RecordIdentity
from coyote_api.app import middleware
from coyote_api.app.main import app
from coyote_mongo.records import application_record, storage_record
from coyote_mongo.resource_integrity import resource_content_hash as persisted_hash


@pytest.mark.asyncio
async def test_client_reaches_the_host_health_route_without_starting_services(monkeypatch):
    """Exercise the real mounted API through the client with an in-process transport."""
    monkeypatch.setattr(middleware, "ensure_runtime_initialized", lambda **kwargs: None)
    monkeypatch.setattr(middleware, "resolve_request_user", lambda request: None)
    monkeypatch.setattr(middleware.runtime_app, "config", {"API_RATE_LIMIT_ENABLED": False})
    host = httpx.ASGITransport(app=app)

    async def dispatch(request):
        if request.url.path == "/api/v1/auth/session":
            return httpx.Response(200, json={"user": {"username": "synthetic"}})
        return await host.handle_async_request(request)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(dispatch), base_url="http://synthetic.test"
    ) as client:
        assert (await client.get("/api/v1/health")).json() == {"status": "ok"}


def test_adapter_records_retain_core_identity_and_persisted_integrity():
    """Projection and the host-bound core codec preserve the stored release content."""
    stored = {"_id": ObjectId(), "genes": ["SYNTHETIC_A", "SYNTHETIC_B"]}
    portable = application_record(stored)
    assert isinstance(portable["_id"], RecordIdentity)
    assert resource_content_hash(portable) == persisted_hash(stored)
    assert storage_record(portable) == stored
