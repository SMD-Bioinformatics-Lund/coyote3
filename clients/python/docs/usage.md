# Use the Python HTTP client {#python-sdk}

This guide covers HTTP access to a running Coyote API. In-process clinical
workflows belong to the separate application SDK and are not part of this client.

`CoyoteClient` and `AsyncCoyoteClient` provide typed HTTP access from Python.
Install the project or a retained wheel using [getting started](getting-started.md).
It depends on HTTPX and Pydantic and does not install the core application or server.

## Client boundary

The client has its own project metadata, version and wheel. It imports no server contracts,
configuration, clinical services or persistence code. Constructing either client
makes no network request. Authentication and operations use the actual HTTP API.

| Location | Responsibility |
| --- | --- |
| `src/coyote_pyclient/resources.py` | Sessions, transport, resource snapshots and metadata collections. |
| `src/coyote_pyclient/clinical.py` | Sample analyses, finding review and reporting objects. |
| `src/coyote_pyclient/models.py` | Typed client responses and page models. |
| `src/coyote_pyclient/errors.py` | SDK errors and response validation. |
| `src/coyote_pyclient/pagination.py` | On-demand page continuation. |
| `src/coyote_pyclient/endpoints.py` | General endpoint objects, uploads, downloads and streams. |
| `src/coyote_pyclient/metadata.py` | Client-owned permitted metadata snapshots. |

The web UI and Python SDK both use the HTTP API. Clinical rules, authorization,
ownership checks and persistence run on the server.

The server's OpenAPI specification is authoritative; contract tests exercise the
typed client's actual method/path pairs against it. General `client.api` paths
remain explicit HTTP access and do not imply that an endpoint exists.

## Asynchronous use

```python
from coyote_pyclient import AsyncCoyoteClient

async with AsyncCoyoteClient("https://coyote.example/coyote4_dev") as client:
    await client.login(username="reviewer", password="your-password", provider="local")
    sample = await client.samples.get("SYNTHETIC_SAMPLE")
    variants = await sample.variants.tiered_variants()
    trial = await sample.reports.preview_bundle("dna")
    async for page in client.samples.pages(status="done", per_page=50):
        print(page.items)
```

Async methods use a native HTTPX `AsyncClient`. Typed metadata, analysis pages,
report operations and server errors share the synchronous client's contracts.
Use `await client.api...get/post/put/patch/delete(...)` for other endpoints.
`async with client.api...stream()` supports downloads and event feeds. Connections
close on context exit or cancellation. The default timeout is 30 seconds;
pass `timeout=` to change it. Neither client automatically retries mutations.
Do not switch identities concurrently with active requests on the same client.

## Password login and attribute reads

Set `base_url` to the installation's public origin, including any mount prefix.
Set `cookie_name` to its configured `API_SESSION_COOKIE_NAME`; the default is
`coyote4_api_session`. Select an explicitly enabled authentication provider.

```python
from getpass import getpass

from coyote_pyclient import CoyoteClient

with CoyoteClient(
    "https://coyote.example/coyote4_dev",
    cookie_name="coyote4_dev_api_session",
) as client:
    client.login(
        username=input("Username: "),
        password=getpass("Password: "),
        provider="local",
    )
    try:
        sample = client.samples.get("DEMO_001")
        print(sample.asp_id)
        print(sample.environment)
        print(sample.reported)
        if sample.asp_id is not None:
            assay = client.asp.get(sample.asp_id)
            print(assay.data.supported_analyses)
    finally:
        client.logout()
```

`get()` makes one request to the resource's `/metadata` endpoint, checking existence,
permissions and scope, and returns a validated local snapshot. Reading `sample.asp_id`
or `sample.data.asp_id` makes no network request. `sample.refresh()` explicitly
fetches current metadata and returns the same resource object. Use `.data` for the
typed metadata model on any collection; samples also have typed direct properties.

`ref()` creates a reference without a request, useful for workflow calls such as
`client.samples.ref("DEMO_001").variants.list()`. Reading metadata on an unfetched
reference raises `ResourceNotLoadedError`; call `refresh()` first. `dir(sample)`
lists supported attributes without a request. Metadata models reject assignment;
changing local data does not update the server. Authentication changes, close and
failed refreshes invalidate resource snapshots. A snapshot is not a guarantee of
current server state or continuing access; every new request checks current access.

| Client collection | Resource identifier |
| --- | --- |
| `client.samples` | Sample identifier |
| `client.asp` | Assay `asp_id` |
| `client.aspc` | Configuration `aspc_id` |
| `client.assay_groups` | Biological `group_id` |
| `client.diagnoses` | `diagnosis_id` |
| `client.genelists` | Gene-list `isgl_id` |

Supported metadata attributes are defined by the [client metadata models](reference.md#metadata).
Unsupported metadata attributes raise `AttributeError` locally. Optional
null values become `None`; booleans, integers, strings, and lists retain their JSON
types. ISO timestamps in metadata become Python `datetime` values. Metadata snapshots
contain only the permitted field allowlist, excluding clinical content and file paths.

## Sample analyses and review workflows

The remote client implementation is in `src/coyote_pyclient/`; it is
installed independently of the local application operations.

Samples expose `variants` (SNVs and small indels), `cnvs`, `fusions`, and
`translocations`. Each collection supports `list()`, `get(finding_id)`, `ref(finding_id)`,
`pages()`, `iter()` and `set_tier()`. Server permissions and enabled analysis types
govern availability.

```python
sample = client.samples.get("DEMO_001")
page = sample.variants.list(intent="somatic", page=1, per_page=50)
tiered = sample.variants.tiered_variants(intent="somatic")
cnv_page = sample.cnvs.list(page=1)
fusion_page = client.samples.get("DEMO_RNA_001").fusions.list(page=1)
finding = sample.variants.get("demo-finding-id")
print(finding.data.id)
finding.refresh()
detail = finding.read()
```

`list()` returns a typed `Page` with `.items`, `.pagination`, and the original UI
envelope in `.payload`. Finding rows are `FindingData` models: `_id` is exposed as
`.id`, and a present classification is available as `.classification.class_value`.
Review flags retain the server contract's string-or-boolean values. Additive fields
and annotations remain available on the model and in `model_dump(by_alias=True)`.

`get()` fetches complete typed finding detail and exposes its row through `.data`.
`ref()` skips the fetch for callers that only need to invoke an operation. `refresh()`
updates the local detail; `read()` explicitly fetches and returns the typed detail
context. Applying a flag through that finding object invalidates its cached detail;
other operations do not refresh previously fetched objects. Call `refresh()` when
current data is required. `sample.context()` returns typed UI sample context,
including `.sample` and `.comments`.

`tiered_variants()` calls `GET /api/v1/samples/{sample_id}/small-variants/tiered`.
It returns the complete selected tiered list, without pagination, using the existing
server selection applied to current sample filters, analysis intent, search and
classification scope. The selection excludes false-positive, irrelevant and
blacklisted findings under the established selection rules, including the existing
handling of blacklist overrides. It is a sample small-variant selection; the
cross-sample reported-finding search remains a separate operation.

To retrieve a temporary HTML/PDF pair without saving a report on the server:

```python
import base64
from pathlib import Path

trial = sample.reports.preview_bundle("dna")  # Use "rna" for an RNA sample.
Path(f"{trial.filename}.html").write_text(trial.html, encoding="utf-8")
Path(f"{trial.filename}.pdf").write_bytes(base64.b64decode(trial.pdf_base64))
```

These writes occur on the computer running the script. The server renders HTML
and PDF in memory and retains normal access auditing, without creating report
records or server report files.

Report previews and saves use `smd-reports` exclusively. Review the preview before
saving with its fingerprint:

```python
preview = sample.reports.preview("dna", include_snapshot=True)
# Review preview.report.html before issuing the report.
sample.reports.save(
    "dna", preview_fingerprint=preview.meta.preview_fingerprint
)
```

Report requests do not accept a format selector. A stale preview fingerprint returns
HTTP 409 instead of issuing an unreviewed report.

Review mutations are explicit:

```python
finding = sample.variants.get("demo-finding-id")
finding.set_flag("interesting")
finding.set_flag("false-positive", apply=False)
sample.variants.set_tier(["demo-finding-id"], 2)
sample.variants.set_tier(["demo-finding-id"], 2, apply=False)
sample.comments.post(json={"form_data": {"sample_comment": "Synthetic review note"}})
sample.comments["demo-comment-id"].hidden.patch()
```

`apply=False` deactivates matching annotations and retains their history. To deactivate
all annotations for the finding across its biological group's assays and diagnoses,
pass `deactivation_scope="group"` with `apply=False`; this requires
`tier:remove:global`. Classification responses expose `is_active`,
`historical_sample_match` and `legacy_fallback` so callers can distinguish recorded
sample history from an uncertain legacy match.

Flag names and bulk tier operations retain their finding-specific server validation,
ownership checks, publication rules and permissions. Invalid integer tiers are
rejected locally instead of relying on server defaults. Finding comments, annotation
forms, transcript selection and other operations are available through `finding.api`
and `sample.api` with the existing API payloads.

## Reports

```python
preview = sample.reports.preview("dna", include_snapshot=True)
# Review preview.report.html before saving.
saved = sample.reports.save(
    "dna", preview_fingerprint=preview.meta.preview_fingerprint
)
pdf_bytes = sample.reports.download(saved.report.id)
```

Preview does not save a report. Saving submits the reviewed fingerprint and preserves
the server's `409` response if the inputs have changed. The client does not refresh
the fingerprint or retry a failed save automatically. PDF downloads return bytes;
`file_type="html"` returns HTML text.

## General API endpoint objects

`client.api` exposes all API paths through endpoint objects, including administration,
knowledgebase search, configuration editing, governance and ingestion. `resource.api`
starts at an individual resource's path. Each endpoint offers `get`, `post`, `put`,
`patch`, `delete`, `request` and `stream`; method calls use HTTPX argument names such
as `params`, `json`, `data` and `files`.

```python
metrics = client.api.dashboard.metrics["top-tiered-genes"].get()
users = client.api.users.get(params={"page": 1, "per_page": 30})
matches = client.api.common.search["tiered_variants"].get(params={"search_str": "FLT3"})
configuration = client.aspc.get("demo::base::testing").api.context.get()
```

Attribute navigation converts underscores to hyphens: `sample.api.edit_context`
means `edit-context`. Use brackets for exact segment spelling, identifiers and
segments that collide with methods or Python keywords, for example
`client.api.resources.asp["create_context"]` or `endpoint["async"]`. Bracket
segments are URL-encoded. Empty segments, path separators and dot traversal are
rejected. Navigation alone sends no request. This interface does not infer whether a
route exists; the server validates the requested route and method.

Operations receive the same payloads as their HTTP counterparts. For example,
multipart uploads use `endpoint.post(files={...}, data={...})`. Responses decode as
JSON, text or bytes according to content type; empty responses become `None`.
For large downloads or event streams, use a context manager:

```python
with open("demo-report.pdf", "wb") as output:
    with sample.reports.api["demo-report-id"].pdf.stream() as response:
        for chunk in response.iter_bytes():
            output.write(chunk)
```

All operations use the current user's bearer session. This interface does not grant
permissions or replace separate infrastructure credentials for service-only routes.
Server validation, clinical rules and audit behavior remain authoritative. The
running server's OpenAPI specification at `<base_url>/api/v1/openapi.json`
describes the available paths, methods and request contracts.

## Lists and existing sessions

`list()` fetches exactly one typed page. `pages()` and `iter()` fetch subsequent
pages only as iteration advances, using the server's continuation metadata:

```python
page = client.samples.list(page=1, per_page=30)
live_rows = page.items
has_more = page.pagination.has_next
raw_envelope = page.payload
assay_page = client.asp.list(q="demo", page=1, per_page=30)

for variant in sample.variants.iter(intent="somatic", q="FLT3", per_page=50):
    print(variant.id)

for completed_sample in client.samples.iter(status="done", per_page=30):
    print(completed_sample.name)
```

Sample catalog `status="live"` (default) and `status="done"` select independent
streams. The SDK maps `page` and `per_page` to that stream's pagination parameters;
conflicting `live_page`, `done_page`, `live_per_page` and `done_per_page` options are
rejected. Use `client.api.samples.get(params={...})` for the raw two-stream API.
Groups and diagnoses have one unpaginated server response, exposed as a single page.

Filters and sorting remain unchanged across pages. Use `start_page` with iteration
instead of `page`. Early stopping avoids fetching later pages. Invalid or stalled
pagination raises `ResponseValidationError`; an authentication change during iteration
stops continuation. Offset pagination retains the server's behavior when data changes
concurrently; the SDK does not promise a consistent snapshot across pages.

Metadata list rows are projected onto the permitted typed metadata fields. Computed
values absent from a list row remain null; use `get()` for the complete permitted
metadata snapshot. List rows do not become bound resource references automatically.

To reuse a session instead of supplying a password:

```python
client.login_with_token(getpass("Session token: "))
print(client.user)
```

Password login captures only the configured session cookie and sends its value as
a bearer token for subsequent requests. No CSRF header is required for this
transport. A missing configured cookie raises `ValueError`; unrelated cookies
are not used as session tokens. The client does not follow redirects, and TLS
certificate verification remains enabled.

## Errors and session lifecycle

Unsuccessful responses raise `CoyoteAPIError`, a subclass of
`httpx.HTTPStatusError`, with more specific subclasses for common outcomes:

| HTTP status | SDK error |
| --- | --- |
| 401 | `AuthenticationError` |
| 403 | `PermissionDeniedError` |
| 404 | `NotFoundError` |
| 409 | `ConflictError` |
| 422 | `RequestValidationError` |
| 429 | `RateLimitError` |
| Other unsuccessful status | `CoyoteAPIError` |

Import these errors from `coyote_pyclient`. They expose `.status_code`, `.code`,
`.message`, `.request_id`, `.retry_after`, and the original `.response`.
`.response.json()` retains structured server details. Server bodies and session
credentials are excluded from the default error string. SDK errors apply to
`CoyoteClient`, `AsyncCoyoteClient`, and their resource/endpoint methods. All login
operations use these clients; authentication is owned by each client instance.

Invalid successful responses and malformed JSON raise `ResponseValidationError`.
Transport failures retain HTTPX transport exceptions. The SDK does not automatically
retry requests, including mutations and report saves. Resource requests before login
or after logout raise `RuntimeError`. Failed reauthentication clears the previous local
session. Missing session cookies raise `ValueError`.

`logout()` revokes the current server session and clears local credentials even
when revocation fails. `close()` and context exit close the HTTP transport and clear
local credentials; they do not revoke the server session. Call `logout()` explicitly
when the session should end. Treat session tokens as secrets; keep them out of
source files, logs and shared examples. See [client configuration](configuration.md).

## SDK verification

Run the focused client checks without a running server:

```bash
python -m pytest -q
python -m pytest -q --cov --cov-config=pyproject.toml
```

Run these commands from the client project after installing `.[test]`.
The application maintains separate integration tests for API routes, permissions
and the client/server contract. See [development](development.md) for isolated
installation, coverage and build instructions.
