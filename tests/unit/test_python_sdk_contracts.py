"""SDK snapshot, pagination, response validation and framework independence contracts."""

import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import get_args

import httpx
import pytest
from coyote3_client import (
    AuthenticationError,
    ConflictError,
    CoyoteAPIError,
    CoyoteClient,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    RequestValidationError,
    ResourceNotLoadedError,
    ResponseValidationError,
)
from coyote3_client.metadata import (
    AssayMetadata,
    ConfigurationMetadata,
    DiagnosisMetadata,
    GeneListMetadata,
    GroupMetadata,
    SampleMetadata,
)
from coyote3_client.models import FindingData, Page

from coyote3.contracts import resource_metadata as server_metadata
from coyote3.contracts.resource_fields import (
    AssayField,
    ConfigurationField,
    DiagnosisField,
    GeneListField,
    GroupField,
    SampleField,
)


@pytest.mark.parametrize(
    "model",
    [
        SampleMetadata,
        AssayMetadata,
        ConfigurationMetadata,
        GeneListMetadata,
        GroupMetadata,
        DiagnosisMetadata,
    ],
)
def test_sdk_metadata_matches_the_server_wire_contract(model):
    """Keep independently owned metadata models compatible through their JSON schemas."""
    assert model.model_json_schema() == getattr(server_metadata, model.__name__).model_json_schema()


@pytest.fixture
def sdk():
    requests = []
    state = {"status": 200, "payload": {"name": "DEMO_001", "version": 1}}

    def respond(request):
        requests.append(request)
        if request.url.path.endswith("/auth/session"):
            return httpx.Response(200, json={"user": {"username": "synthetic"}})
        return httpx.Response(state["status"], json=state["payload"])

    with CoyoteClient(
        "https://example.test/mounted", transport=httpx.MockTransport(respond)
    ) as client:
        client.login_with_token("synthetic-token")
        requests.clear()
        yield client, state, requests


def test_metadata_snapshot_is_explicit_typed_and_locally_readable(sdk):
    client, state, requests = sdk
    state["payload"] = {"name": "DEMO_001", "reported": False, "time_added": "2026-01-02T03:04:05Z"}
    sample = client.samples.get("demo")
    assert isinstance(sample.data, SampleMetadata)
    assert isinstance(sample.time_added, datetime)
    assert sample.reported is False
    assert sample.asp_id is None
    assert requests[-1].url.path == "/mounted/api/v1/samples/demo/metadata"
    for _ in range(3):
        assert sample.name == "DEMO_001"
        assert sample.data.name == "DEMO_001"
    assert len(requests) == 1
    state["payload"] = {"name": "DEMO_UPDATED"}
    assert sample.name == "DEMO_001"
    assert sample.refresh() is sample
    assert sample.name == "DEMO_UPDATED"
    assert len(requests) == 2


def test_ref_has_no_network_side_effects(sdk):
    client, _, requests = sdk
    sample = client.samples.ref("demo")
    assert "asp_id" in dir(sample)
    assert sample.variants is not None
    with pytest.raises(ResourceNotLoadedError):
        _ = sample.asp_id
    assert requests == []
    sample.refresh()
    assert len(requests) == 1


def test_failed_refresh_and_identity_change_invalidate_snapshots(sdk):
    client, state, _ = sdk
    sample = client.samples.get("demo")
    state["status"] = 403
    with pytest.raises(PermissionDeniedError):
        sample.refresh()
    with pytest.raises(ResourceNotLoadedError):
        _ = sample.data
    state["status"] = 200
    sample.refresh()
    client.login_with_token("another-synthetic-token")
    with pytest.raises(ResourceNotLoadedError):
        _ = sample.name
    sample.refresh()
    client.close()
    with pytest.raises(ResourceNotLoadedError):
        _ = sample.data


@pytest.mark.parametrize("payload", [{"reported": "false"}, {"filters": {}}, [], {"version": True}])
def test_invalid_metadata_response_fails_without_coercion(sdk, payload):
    client, state, _ = sdk
    state["payload"] = payload
    with pytest.raises(ResponseValidationError):
        client.samples.get("demo")


@pytest.mark.parametrize(
    "fields,model",
    [
        (SampleField, SampleMetadata),
        (AssayField, AssayMetadata),
        (ConfigurationField, ConfigurationMetadata),
        (GroupField, GroupMetadata),
        (DiagnosisField, DiagnosisMetadata),
        (GeneListField, GeneListMetadata),
    ],
)
def test_metadata_snapshots_match_the_permitted_field_contract(fields, model):
    assert set(model.model_fields) == set(get_args(fields))


def test_finding_get_fetches_typed_detail_and_mutation_invalidates_it(sdk):
    client, state, requests = sdk
    state["payload"] = {
        "sample": {},
        "variant": {"_id": "demo-variant", "fp": "", "classification": {"class": 2}},
    }
    finding = client.samples.ref("demo").variants.get("demo-variant")
    assert finding.data.id == "demo-variant"
    assert finding.data.fp == ""
    assert finding.data.classification.class_value == 2
    assert len(requests) == 1
    assert finding.read().variant.id == "demo-variant"
    assert len(requests) == 2
    state["payload"] = {"sample_id": "demo", "action": "mark_interesting"}
    result = finding.set_flag("interesting")
    assert result.action == "mark_interesting"
    with pytest.raises(ResourceNotLoadedError):
        _ = finding.data


def test_finding_list_retains_original_envelope_and_typed_rows(sdk):
    client, state, _ = sdk
    state["payload"] = {
        "display_sections_data": {
            "snvs": [{"_id": "demo-variant", "extra_annotation": {"source": "synthetic"}}]
        },
        "meta": {"page": 1, "per_page": 50, "has_next": False, "count": 1},
        "filters": {"example": None},
    }
    page = client.samples.ref("demo").variants.list()
    assert isinstance(page, Page)
    assert isinstance(page.items[0], FindingData)
    assert page.items[0].id == "demo-variant"
    assert page.payload == state["payload"]
    assert page.model_dump(by_alias=True)["items"][0]["_id"] == "demo-variant"


@pytest.mark.parametrize(
    "options",
    [
        {"resource_ids": "demo"},
        {"resource_ids": []},
        {"resource_ids": [None]},
        {"resource_ids": [""]},
        {"apply": "false"},
        {"include_automatic_text": 1},
    ],
)
def test_invalid_clinical_write_options_cannot_change_meaning(sdk, options):
    client, _, requests = sdk
    args = {"resource_ids": ["demo"], "tier": 2, **options}
    with pytest.raises(ValueError):
        client.samples.ref("demo").variants.set_tier(**args)
    assert requests == []


def test_report_download_rejects_unexpected_content_and_preserves_actual_artifacts(sdk):
    client, _, requests = sdk
    with pytest.raises(ResponseValidationError):
        client.samples.ref("demo").reports.download("demo-report")
    assert len(requests) == 1
    with pytest.raises(ValueError):
        client.samples.ref("demo").reports.download("demo-report", file_type="unsupported")
    assert len(requests) == 1


def test_flag_switch_rejects_nonboolean_values(sdk):
    client, _, requests = sdk
    with pytest.raises(ValueError):
        client.samples.ref("demo").variants.ref("demo-finding").set_flag(
            "interesting", apply="false"
        )
    assert requests == []


@pytest.mark.parametrize("collection", ["findings", "assays", "live", "done", "groups"])
def test_pagination_preserves_filters_and_stream_selection(collection):
    requests = []

    def respond(request):
        if request.url.path.endswith("/auth/session"):
            return httpx.Response(200, json={"user": {"username": "synthetic"}})
        requests.append(request)
        page = int(request.url.params.get("page", 1))
        meta = {"page": page, "per_page": 1, "has_next": page < 3, "total": 3}
        row = {"_id": f"demo-{page}", "name": f"DEMO_{page}", "asp_id": f"assay-{page}"}
        if collection == "findings":
            payload = {"display_sections_data": {"snvs": [row]}, "meta": meta}
        elif collection == "assays":
            payload = {"panels": [row], "pagination": meta}
        elif collection == "groups":
            payload = {"groups": [{"group_id": "demo"}]}
        else:
            assert request.url.params[f"{collection}_page"] == str(page)
            assert request.url.params[f"{collection}_per_page"] == "1"
            payload = {
                f"{collection}_samples": [row],
                f"{collection}_page": page,
                f"{collection}_per_page": 1,
                f"{collection}_total": 3,
                f"has_next_{collection}": page < 3,
            }
        return httpx.Response(200, json=payload)

    with CoyoteClient("https://example.test", transport=httpx.MockTransport(respond)) as client:
        client.login_with_token("synthetic-token")
        if collection == "findings":
            iterator = client.samples.ref("demo").variants.iter(
                q="gene", intent="germline", per_page=1
            )
        elif collection == "assays":
            iterator = client.asp.iter(q="gene", per_page=1)
        elif collection == "groups":
            iterator = client.assay_groups.iter()
        else:
            iterator = client.samples.iter(status=collection, search_str="gene", per_page=1)
        assert requests == []
        first = next(iterator)
        assert len(requests) == 1
        rest = list(iterator)
        assert len(rest) == (0 if collection == "groups" else 2)
        assert len(requests) == (1 if collection == "groups" else 3)
        if collection != "groups":
            assert all(
                request.url.params["q" if collection in ("findings", "assays") else "search_str"]
                == "gene"
                for request in requests
            )
        if collection == "findings":
            assert first.id == "demo-1"
            assert all(request.url.params["intent"] == "germline" for request in requests)


@pytest.mark.parametrize("kind", ["assays", "findings"])
def test_early_stop_and_session_change_do_not_fetch_next_page(sdk, kind):
    client, state, requests = sdk
    rows = [{"_id": "demo", "asp_id": "demo"}]
    meta = {"page": 1, "per_page": 1, "has_next": True}
    state["payload"] = (
        {"panels": rows, "pagination": meta}
        if kind == "assays"
        else {"display_sections_data": {"snvs": rows}, "meta": meta}
    )
    collection = client.asp if kind == "assays" else client.samples.ref("demo").variants
    pages = collection.pages()
    next(pages)
    assert len(requests) == 1
    client.login_with_token("new-synthetic-session")
    count = len(requests)
    with pytest.raises(ResourceNotLoadedError):
        next(pages)
    assert len(requests) == count


@pytest.mark.parametrize("rows,page", [([], 1), ([{"asp_id": "demo"}], 2)])
def test_malformed_pagination_cannot_loop_forever(sdk, rows, page):
    client, state, requests = sdk
    state["payload"] = {
        "panels": rows,
        "pagination": {"page": page, "per_page": 30, "has_next": True},
    }
    with pytest.raises(ResponseValidationError):
        list(client.asp.pages())
    assert len(requests) == 1


@pytest.mark.parametrize(
    "status,error_type",
    [
        (401, AuthenticationError),
        (403, PermissionDeniedError),
        (404, NotFoundError),
        (409, ConflictError),
        (422, RequestValidationError),
        (429, RateLimitError),
        (500, CoyoteAPIError),
        (302, CoyoteAPIError),
    ],
)
def test_typed_errors_keep_diagnostics_for_requests_and_streams(status, error_type):
    requests = []

    def respond(request):
        requests.append(request)
        if request.url.path.endswith("/auth/session"):
            return httpx.Response(200, json={"user": {"username": "synthetic"}})
        return httpx.Response(
            status,
            json={"error": "Synthetic detail", "code": "synthetic_error"},
            headers={"X-Request-ID": "demo-reference", "Retry-After": "10"},
        )

    with CoyoteClient("https://example.test", transport=httpx.MockTransport(respond)) as client:
        client.login_with_token("synthetic-token")
        for streamed in (False, True):
            with pytest.raises(error_type) as caught:
                if streamed:
                    with client.api.users.stream():
                        pytest.fail("Unsuccessful stream must not open")
                else:
                    client.api.users.get()
            error = caught.value
            assert isinstance(error, httpx.HTTPStatusError)
            assert error.status_code == status
            assert error.code == "synthetic_error"
            assert error.message == "Synthetic detail"
            assert error.request_id == "demo-reference"
            assert error.retry_after == "10"
            assert "Synthetic detail" not in str(error)
            assert "synthetic-token" not in repr(error)
        assert len(requests) == 3


def test_malformed_json_and_invalid_session_are_response_errors():
    def respond(request):
        if request.url.path.endswith("/auth/session"):
            return httpx.Response(200, json={"user": {"username": "synthetic"}})
        return httpx.Response(200, content="invalid", headers={"content-type": "application/json"})

    with CoyoteClient("https://example.test", transport=httpx.MockTransport(respond)) as client:
        client.login_with_token("synthetic-token")
        with pytest.raises(ResponseValidationError):
            client.api.users.get()


def test_sdk_import_does_not_require_server_frameworks_or_configuration():
    script = """
import importlib.abc
import sys
class BlockServerImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        blocked = ("fastapi", "starlette", "pymongo", "api.app", "coyote3.config", "api.infra", "coyote3.contracts", "coyote3.application", "coyote3.domain")
        if any(fullname == name or fullname.startswith(name + ".") for name in blocked):
            raise AssertionError("SDK imported server dependency: " + fullname)
sys.meta_path.insert(0, BlockServerImports())
from coyote3_client import CoyoteClient
client = CoyoteClient("https://example.test")
client.close()
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
