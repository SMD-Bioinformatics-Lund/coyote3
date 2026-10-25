"""HTTP lease validation and authorization without runtime database connections."""

from inspect import signature
from types import SimpleNamespace
from uuid import uuid4

import mongomock
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from api.app.deps.application import get_application
from api.infra.mongo.repositories.edit_leases import MongoEditLeaseRepository
from api.interfaces.http.v1.operations.editing import edit_session, router
from coyote3.application.editing import DocumentEditing
from coyote3.application.operations.editing import DocumentEditors, EditableResource
from coyote3.application.operations.runtime import ApplicationRuntime
from coyote3.domain.exceptions import AppError


def test_http_lease_checks_current_user_permissions_and_uuid():
    service = DocumentEditing(
        MongoEditLeaseRepository(
            SimpleNamespace(coyote_db=mongomock.MongoClient(tz_aware=True).test)
        )
    )
    users = {
        name: SimpleNamespace(username=name, permissions={"edit"}, is_superuser=False)
        for name in ("alice", "bob")
    }
    app = FastAPI()
    app.include_router(router)

    def application(request: Request):
        actor = users.get(request.headers.get("X-Test-User"))
        policy = SimpleNamespace(
            permission_allowed=lambda _actor, permission, **_: permission in actor.permissions
        )
        runtime = ApplicationRuntime(
            authenticate=lambda: actor,
            policy_factory=lambda _: policy,
            sample_loader=lambda _: None,
            assay_loader=lambda _: None,
            audit_access=lambda _: None,
            document_editing=service,
        )
        return SimpleNamespace(
            editing=DocumentEditors(
                runtime,
                {
                    "draft": EditableResource("edit", lambda _: {"id": "shared"}, "id"),
                },
            )
        )

    app.dependency_overrides[get_application] = application

    def authenticated_user(request: Request):
        actor = users.get(request.headers.get("X-Test-User"))
        if actor is None:
            raise HTTPException(status_code=401)
        return actor

    auth_dependency = signature(edit_session).parameters["user"].default.dependency
    app.dependency_overrides[auth_dependency] = authenticated_user

    @app.exception_handler(AppError)
    async def failure(_request, error):
        return JSONResponse(status_code=error.status_code, content={"message": error.message})

    with TestClient(app) as client:
        endpoint = "/api/v1/editing/draft/shared"
        first, second = str(uuid4()), str(uuid4())
        assert client.post(f"{endpoint}/acquire", json={"editor_id": first}).status_code == 401
        alice = {"X-Test-User": "alice"}
        bob = {"X-Test-User": "bob"}
        assert (
            client.post(f"{endpoint}/acquire", headers=alice, json={"editor_id": "bad"}).status_code
            == 422
        )
        acquired = client.post(f"{endpoint}/acquire", headers=alice, json={"editor_id": first})
        assert acquired.status_code == 200
        assert acquired.json()["owned"] is True
        denied = client.post(f"{endpoint}/acquire", headers=bob, json={"editor_id": second})
        assert denied.json()["owned"] is False
        assert denied.json()["owner"] == "alice"
        assert "editor_id" not in denied.json()
        assert (
            client.post(f"{endpoint}/renew", headers=bob, json={"editor_id": first}).status_code
            == 409
        )
        users["alice"].permissions.clear()
        assert (
            client.post(f"{endpoint}/renew", headers=alice, json={"editor_id": first}).status_code
            == 403
        )
