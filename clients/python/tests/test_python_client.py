"""Resource client authentication, metadata access and transport behavior."""

from uuid import uuid4

import httpx
import pytest
from coyote3_client import CoyoteClient


def test_temporary_report_returns_typed_downloads_without_a_save_request():
    """Trial rendering uses one read and retains HTML and PDF from the same response."""
    requests = []

    def respond(request):
        requests.append(request)
        if request.url.path.endswith("/auth/session"):
            return httpx.Response(200, json={"user": {"username": "synthetic"}})
        return httpx.Response(
            200,
            json={
                "html": "<html><style>body{color:black}</style></html>",
                "pdf_base64": "JVBERi0xLjQ=",
                "filename": "coyote3_dna_report_trial",
                "snapshot_count": 3,
            },
        )

    with CoyoteClient("https://example.test", transport=httpx.MockTransport(respond)) as client:
        client.login_with_token("synthetic-token")
        requests.clear()
        trial = client.samples.ref("SYNTHETIC_TRIAL").reports.try_new("dna")
    assert trial.snapshot_count == 3
    assert trial.pdf_base64 == "JVBERi0xLjQ="
    assert "<style>" in trial.html
    assert len(requests) == 1
    assert requests[0].method == "GET"
    assert requests[0].url.path == "/api/v1/samples/SYNTHETIC_TRIAL/reports/dna/try-new"


@pytest.fixture
def requests_and_client():
    """Provide a client backed by a recorded synthetic API transport."""
    requests = []

    def respond(request):
        requests.append(request)
        if request.url.path.endswith("/auth/sessions"):
            return httpx.Response(
                201,
                json={"user": {"username": "synthetic"}},
                headers={"set-cookie": "demo_session=synthetic-token; HttpOnly; Secure"},
            )
        if request.url.path.endswith("/auth/session"):
            return httpx.Response(200, json={"user": {"username": "synthetic"}})
        if request.url.path.endswith("/auth/sessions/current"):
            return httpx.Response(200, json={"status": "ok"})
        return httpx.Response(
            200,
            json={
                "live_samples": [],
                "live_total": 0,
                "live_page": 2,
                "live_per_page": 10,
                "has_next_live": False,
            },
        )

    with CoyoteClient(
        "https://example.test/mounted/",
        cookie_name="demo_session",
        transport=httpx.MockTransport(respond),
    ) as client:
        yield requests, client


def test_editor_session_preserves_authentication_and_rejects_invalid_uuid(requests_and_client):
    """Expose editing ownership without permitting authentication header replacement."""
    requests, client = requests_and_client
    client.login_with_token("synthetic-token")
    editor = uuid4()
    client.api.resources.genelists["synthetic"].put(json={"config": {}}, edit_session=editor)
    assert requests[-1].headers["X-Edit-Session"] == str(editor)
    assert requests[-1].headers["Authorization"] == "Bearer synthetic-token"
    count = len(requests)
    with pytest.raises(ValueError):
        client.api.resources.genelists["synthetic"].put(json={}, edit_session="invalid")
    assert len(requests) == count


def test_password_login_and_list(requests_and_client):
    requests, client = requests_and_client
    assert client.session_token is None
    user = client.login(username="synthetic", password="example-password", provider="local")
    assert user == client.user
    assert user.username == "synthetic"
    assert client.session_token == "synthetic-token"
    assert requests[0].url.path == "/mounted/api/v1/auth/sessions"
    assert requests[0].read() == (
        b'{"username":"synthetic","password":"example-password","provider":"local"}'
    )
    page = client.samples.list(page=2, per_page=10)
    assert page.items == []
    assert page.pagination.page == 2
    assert requests[-1].url.path == "/mounted/api/v1/samples"
    assert dict(requests[-1].url.params) == {
        "page": "2",
        "per_page": "10",
        "live_page": "2",
        "live_per_page": "10",
    }
    assert requests[-1].headers["authorization"] == "Bearer synthetic-token"
    assert "cookie" not in requests[-1].headers


@pytest.mark.parametrize(
    "collection,path,field,value",
    [
        ("samples", "samples", "asp_id", "demo-assay"),
        ("samples", "samples", "reported", False),
        ("samples", "samples", "time_added", None),
        ("asp", "resources/asp", "supported_analyses", ["SNV", "CNV"]),
        ("aspc", "resources/aspc", "reference_genome", "GRCh38"),
        ("assay_groups", "resources/assay-groups", "is_active", True),
        ("diagnoses", "resources/diagnoses", "description", "Synthetic diagnosis"),
        ("genelists", "resources/genelists", "gene_count", 0),
    ],
)
def test_resource_attributes(collection, path, field, value):
    requests = []

    def respond(request):
        requests.append(request)
        if request.url.path.endswith("/auth/session"):
            return httpx.Response(200, json={"user": {"username": "synthetic"}})
        return httpx.Response(200, json={field: value})

    with CoyoteClient("https://example.test", transport=httpx.MockTransport(respond)) as client:
        client.login_with_token("synthetic-token")
        resource = getattr(client, collection).get("demo::test id")
        assert len(requests) == 2  # get() explicitly fetches metadata.
        assert field in dir(resource)
        assert getattr(resource, field) == value
        assert type(getattr(resource, field)) is type(value)
        assert len(requests) == 2  # Attribute reads use the local snapshot.
        assert requests[-1].url.raw_path == (
            f"/api/v1/{path}/demo%3A%3Atest%20id/metadata".encode()
        )
        for forbidden in ("files", "filters", "password", "unknown"):
            with pytest.raises(AttributeError):
                getattr(resource, forbidden)
        with pytest.raises(AttributeError):
            setattr(resource, field, "replacement")
        assert len(requests) == 2
        resource.refresh()
        assert len(requests) == 3


def test_login_required_logout_and_close(requests_and_client):
    requests, client = requests_and_client
    with pytest.raises(RuntimeError, match="Log in"):
        client.samples.get("demo").name
    assert requests == []
    client.login_with_token("synthetic-token")
    assert requests[-1].headers["authorization"] == "Bearer synthetic-token"
    client.logout()
    assert requests[-1].method == "DELETE"
    assert requests[-1].url.path == "/mounted/api/v1/auth/sessions/current"
    assert client.user is None
    assert client.session_token is None
    with pytest.raises(RuntimeError):
        client.samples.list()
    count = len(requests)
    client.logout()
    client.close()
    assert len(requests) == count


@pytest.mark.parametrize("status", [401, 403, 404, 422, 429, 500])
def test_server_errors_are_preserved(status):
    def respond(request):
        if request.url.path.endswith("/auth/session"):
            return httpx.Response(200, json={"user": {"username": "synthetic"}})
        return httpx.Response(status, json={"error": "Synthetic failure"})

    with CoyoteClient("https://example.test", transport=httpx.MockTransport(respond)) as client:
        client.login_with_token("synthetic-token")
        with pytest.raises(httpx.HTTPStatusError) as error:
            client.samples.get("demo").name
        assert error.value.response.status_code == status
        assert error.value.response.json()["error"] == "Synthetic failure"
        with pytest.raises(httpx.HTTPStatusError):
            client.logout()
        assert client.user is None
        with pytest.raises(RuntimeError):
            client.samples.list()


def test_failed_reauthentication_clears_previous_session(requests_and_client):
    _, client = requests_and_client
    client.login_with_token("synthetic-token")
    with pytest.raises(ValueError, match="required"):
        client.login_with_token("")
    assert client.user is None
    with pytest.raises(RuntimeError):
        client.samples.list()


@pytest.mark.parametrize("status", [201, 401, 302])
def test_login_never_uses_an_unrelated_cookie_or_follows_redirects(status):
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(
            status,
            json={"user": {}},
            headers={
                "set-cookie": "unrelated=not-a-session",
                "location": "https://other.test/",
            },
        )

    with CoyoteClient("https://example.test", transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(ValueError if status == 201 else httpx.HTTPStatusError):
            client.login(username="synthetic", password="example", provider="ldap")
        assert len(requests) == 1
        assert client.user is None
        assert not client._http.cookies
        with pytest.raises(RuntimeError):
            client.samples.list()


@pytest.mark.parametrize("identifier", ["", ".", ".."])
def test_invalid_identifiers(requests_and_client, identifier):
    requests, client = requests_and_client
    with pytest.raises(ValueError):
        client.samples.get(identifier)
    assert requests == []


@pytest.mark.parametrize(
    "url", ["file:///tmp/api", "/relative", "https://u:p@example.test", "https://example.test/?q=1"]
)
def test_invalid_base_url(url):
    with pytest.raises(ValueError):
        CoyoteClient(url)
