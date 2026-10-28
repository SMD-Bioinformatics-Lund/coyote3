# Record attribution and system-installed resources

Persisted collection contracts include `created_by` and `updated_by`. Embedded
values, such as a transcript inside a finding, inherit their owning document's
attribution rather than carrying separate actors.

| Field | Meaning |
| --- | --- |
| `created_by` | Original creator, retained when the document is revised. |
| `updated_by` | Actor responsible for the latest content update. |
| `system_installed` | Configuration supplied by the application installer; read-only through user-facing mutation workflows. |
| `system_managed` | Protected application-owned identity or baseline definition. |

Application services take actors from authenticated execution context or the trusted
workflow's actor argument. Collection ingestion does not accept caller-supplied
creator, updater, or installation flags as authority. New records receive the
creating actor in both attribution fields. Edits retain the stored creator.

Initial bundled configuration uses `system` as its creator and updater, even when
an administrator starts installation. Administration tables display the system icon
for those records. The requesting user's permissions authorize installation and
their username remains in the installation audit; it does not become the bundled
document's creator. Bundled repairs and demo sample ingestion also use `system`
for document attribution. Administration tables suppress edit actions
for installed records; application services also reject
direct mutation requests. Create a center-owned resource where customization is
supported. Copying a resource does not transfer its protected installation status.

Automated knowledgebase imports record `system` as their service actor. This alone
does not make a record an immutable installed definition: reference refreshes and
normal demo-sample workflows remain available. Sample overview shows the stored
creator and updater. Governed reporting rules retain `updated_by` as the content
editor for independent review checks; review, publication and retirement actors
are recorded separately in their lifecycle metadata.

The Admin Samples table and its CSV export omit creator/updater columns. **Time Added**
remains visible, and sample attribution is available in the sample overview. Removing
a table column does not remove attribution or audit data from stored records.

## Existing records

Missing historical actors are null and appear as **Unknown**. The current user is
never substituted for a missing creator. Installing this code does not rewrite
existing database records.

The maintenance command below plans attribution changes for one explicitly selected
collection. It uses existing installation flags, sample ingest attribution, comment
or report authors, and retained first-revision diagnosis attribution. It cannot reconstruct
missing history. Immutable revision evidence is excluded.

```bash
# Load the correct URI through your normal secret-management process.
# Set TARGET_DB to the intended database name.
PYTHONPATH=.:src .venv/bin/python scripts/maintenance/backfill_record_attribution.py \
  --database "$TARGET_DB" --collection diagnoses
```

Review the counts, back up the target database, then repeat with `--apply` to write.
Use `--mongo-uri-env KNOWLEDGEBASE_MONGO_URI` for a separately configured reference
service and `--storage-collection NAME` if its physical collection name differs
from the logical contract name. Writes check that attribution evidence has not
changed since inspection. No command in this guide runs automatically on deployment.
