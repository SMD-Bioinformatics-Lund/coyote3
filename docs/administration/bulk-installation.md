# Bulk installation of configuration resources

Use **Upload JSON / YAML** on the diagnosis definitions, assay groups, assays,
gene lists or assay configurations page to create several records from one file.
The **Show example** button beside it opens a floating window with a JSON example,
accepted keys and a downloadable example file. For assays, gene lists and assay
configurations, fields and choices come from the running server's create form.
For assay configurations, select DNA or RNA before downloading or uploading a file.

For small lists, choose **Paste JSON / YAML** to open the floating editor. Select
the content format, then paste or type your records. Syntax and structure warnings
update as you type; **Review records** stays disabled until these checks pass.
Use **Edit example** in the example window to start with the displayed JSON.
Review the parsed records, then select **Install records** to submit them through
the same permission-checked creation workflow as file uploads. You can return to
**Edit pasted records** before installing. Typing and reviewing do not write data.
Server validation still checks field types and references during installation.
Use file uploads for larger structures; both methods have the same size and row limits.

## Permissions

Bulk installation uses the same server-enforced permissions as individual creation.
Administrators and other users need the relevant permission through their assigned
role. Normal page access permissions still apply; uploading grants no extra access.

| Resource | Creation permission |
| --- | --- |
| Diagnoses | `assay.panel:edit` |
| Assay groups | `assay.panel:edit` |
| Assays | `assay.panel:create` |
| Gene lists | `gene_list.insilico:create` |
| Assay configurations | `assay.config:create` |

The server assigns creator, updater and timestamps to the authenticated operator.
Uploaded records are center-managed, not system-installed. Do not include MongoDB
IDs, ownership flags, authors, timestamps or revision fields.

## Upload and install

1. Open **Show example** and download the JSON example.
2. Replace its values with your center's configuration. Referenced resources must
   exist first. Install parent groups before children, groups before assays, then
   diagnosis associations and gene lists before dependent assay configurations.
   Diagnoses can be created before assays with `asp_ids: []` and linked later.
3. Supply a JSON array or YAML list of 1–100 records, at most 1 MiB. Use one resource
   type per file. Do not wrap records in `config` or `items`. YAML custom tags,
   aliases, duplicate keys and multiple documents are not supported.
4. Choose **Upload JSON / YAML**. The preview checks structure, accepted top-level
   keys, required fields and duplicate identifiers without writing records.
5. Review and select **Install records**. The server validates each record's types,
   references, permissions and resource-specific requirements.
6. Review the per-row results and optionally download them as JSON.

Records are submitted in file order as separate create operations. This is not an
all-or-nothing transaction: a failed row does not undo successful rows. Existing
records produce a conflict rather than being overwritten. Authentication,
permission, rate-limit, network or server failures stop subsequent submissions;
remaining rows are marked **Not attempted**. If a network or server error leaves an
outcome uncertain, check the resource list before preparing another upload.

Upload a new file containing only failed or unattempted records to correct failures.
The reviewed batch cannot be submitted twice from the same preview. Keep the page
open until installation finishes. Bulk creation does not publish a catalog,
activate an assay setup workflow or create missing dependent resources.

## Diagnosis example

`diagnosis_id` and `display_name` are required. `description` defaults to an empty
string, `is_active` to `true`, and `asp_ids` to an empty list. These are the only
accepted diagnosis creation keys. Assays in `asp_ids` must already exist.

```json
[
  {
    "diagnosis_id": "example-diagnosis",
    "display_name": "Example diagnosis",
    "description": "Replace with your diagnosis description",
    "is_active": true,
    "asp_ids": []
  },
  {
    "diagnosis_id": "another-diagnosis",
    "display_name": "Another diagnosis",
    "asp_ids": []
  }
]
```

Equivalent YAML:

```yaml
- diagnosis_id: example-diagnosis
  display_name: Example diagnosis
  description: Replace with your diagnosis description
  is_active: true
  asp_ids: []
- diagnosis_id: another-diagnosis
  display_name: Another diagnosis
  asp_ids: []
```

## Assay group example

`group_id` and `display_name` are required. The optional `description` defaults to
an empty string. `parent_group_id` is null for a top-level group or the identifier
of an existing parent. These are the only accepted group creation keys.

```json
[
  {
    "group_id": "example-group",
    "display_name": "Example group",
    "description": "Replace with your clinical group description",
    "parent_group_id": null
  }
]
```

For other resources, use the live example and expand **Field types, nested fields
and choices**. Blank values and empty nested objects show structure, not a
clinically validated configuration. Populate applicable fields before installation.
Assay configuration IDs are derived from assay, diagnosis and environment; do not
submit an `aspc_id`.
