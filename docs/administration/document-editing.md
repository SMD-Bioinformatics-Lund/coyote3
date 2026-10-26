# Editing a document with other users

An existing document has one active editing session at a time. Opening its editor
acquires a lease for the signed-in user and that form. Another user, or another tab
under the same login, sees who is editing and can read the document without saving
over the active editor's work.

## Which editors use leases

| Editor | Lock identity |
| --- | --- |
| Users, roles and permission policies | The account, role or permission identifier |
| Assays, assay configurations and gene lists | The stable resource identifier, across retained versions |
| Diagnosis definitions | The shared diagnosis identifier |
| Assay setup | The saved setup draft |
| Query rules and reporting rules | The selected rule version |
| Assay catalog | The selected catalog version |
| Application controls | The application's controls document |
| Admin sample editor | The sample's original identifier |
| Sample filters | The sample's filter settings; classic analysis panels share one session |

New documents have no persisted editing target until their first save. Existing
identifier uniqueness checks still decide whether creation succeeds. An editing
lease does not reserve a proposed assay identifier before that save.

Adding a comment, creating an annotation, generating a report snapshot and reading
knowledgebase evidence are independent operations. They do not hold a sample-wide
editing lease. Existing permissions, finding ownership checks and report snapshot
rules continue to apply.

## Saving, leaving and losing a session

The form renews its lease every 30 seconds. The server gives each successful
acquisition or renewal 90 seconds of validity. Closing the editor releases its
session; if the browser closes unexpectedly or cannot reach the API, expiry makes
the document available again. Expiry checks use server time and do not depend on
MongoDB's background TTL cleanup.

The API returns lease expiry timestamps with an explicit UTC offset. Browser
timezone settings do not change the expiry instant.

Saving alone keeps the editing session open. Leave the editor or select another
document when finished. Another tab under the same login remains a separate editor;
seeing your own username means a different session holds the lease. If that session
has disconnected, reload after its 90-second expiry to open a fresh editor.

The server checks current permission and ownership when saving. An expired lease
cannot be renewed or used to save. The form becomes read-only and offers **Reload
document**. Copy any unsaved text before reloading, then compare it with the current
saved document. The application does not automatically reacquire a lost lease and
submit an old form.

Delete, status-change and draft lifecycle actions also respect active editor leases.
An immediate action without an open form takes a temporary lease for that operation.
Assay activation also checks the shared gene lists whose associations it updates.
System-installed records remain protected, and administrators cannot override
another editing session through the normal save endpoint.

Leases complement existing revision checks and transactional writes. Review and
publication still require the workflow's assigned permissions, expected revision
and independent reviewer where applicable. A lease does not replace those checks
or make operations across separate MongoDB clients transactional.

## API and SDK integrations

For a registered editor kind, call:

```text
POST /api/v1/editing/{kind}/{identity}/acquire
{"editor_id": "a new UUID for this editing session"}
```

Use the same UUID with `/renew` and `/release`. Acquisition returns `owned`,
`owner`, `expires_at`, `renew_after_seconds`, and the canonical resource identity.
An unsuccessful acquisition returns `owned: false`; it does not grant editing
rights. The session UUID is not an authentication credential: normal authentication,
CSRF protection and resource permissions remain required.

Send `X-Edit-Session: <UUID>` with saves and lifecycle actions from the active
editor. Missing or lost ownership returns HTTP 409. Load the latest document after
acquisition, retain its revision precondition, and release the lease after saving
or cancelling. Do not share a session UUID between independent editors.

The registered kinds are `users`, `roles`, `permissions`, `asp`, `aspc`, `genelists`,
`diagnoses`, `assay-setups`, `query-rules`, `clinical-rules`, `assay-catalog`,
`controls`, `samples` and `sample-filters`. Controls use identity `default`.
Sample-filter leases require `sample:edit:own` and the current user's sample scope;
the admin sample editor requires `sample:edit:global`.

Trusted in-process integrations use `application.editing.session(...)` for the same
lifecycle. Bind the UUID through `open_application(..., editor_id=str(editor_id))`
before calling the resource's existing update operation. HTTP clients send the
header instead. Renewal rechecks authorization; a revoked account or permission
does not retain editing access.

For the remote Python client, pass `edit_session` on the generic endpoint call:

```python
from uuid import uuid4

editor_id = str(uuid4())
lease_endpoint = client.api.editing["genelists"]["synthetic-list"]
lease = lease_endpoint.acquire.post(json={"editor_id": editor_id})
if not lease["owned"]:
    raise RuntimeError(f"Document is being edited by {lease['owner']}")
try:
    current = client.api.resources.genelists["synthetic-list"].context.get()
    client.api.resources.genelists["synthetic-list"].put(
        json={"config": {"description": "Reviewed scope"},
              "expected_version": current["genelist"]["version"]},
        edit_session=editor_id,
    )
finally:
    lease_endpoint.release.post(json={"editor_id": editor_id})
```

This example assumes an authenticated client and a registered synthetic list.
Longer workflows must call `lease_endpoint.renew.post(...)` before expiry. The
async client accepts the same `edit_session` argument on awaited requests.

## Deployment

Leases are operational records in the primary MongoDB database's `edit_leases`
collection. API workers share them; no process-local lock or Redis cache decides
ownership. The `_id` uniqueness constraint arbitrates competing acquisitions.
The `edit_lease_expiry` TTL index removes expired records.

Provision this index through the normal
[MongoDB index maintenance workflow](../operations/maintenance-and-verification.md).
Existing clinical documents need no lease-field backfill. Deploy the API and
frontend together because editor saves now require the session header.
