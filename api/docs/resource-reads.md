# Resource metadata reads

Integrations can retrieve safe metadata without reproducing UI requests or gaining
database access. Send an authenticated `POST` request to
`/api/v1/resources/read/{resource}/query`. This endpoint only reads data; it does
not modify resources or execute clinical query rules. Existing UI endpoints remain
available.

## Resources and access

| Resource | Logical identifier | Required permission |
| --- | --- | --- |
| `asp` | `asp_id` | `assay.panel:view` and `assay.panel:list` |
| `aspc` | `aspc_id` | `assay.config:view` and `assay.config:list` |
| `samples` | `name` | `sample:view` |
| `isgl` | `isgl_id` | `gene_list.insilico:view` and `gene_list.insilico:list` |
| `assay-groups` | `group_id` | `assay.panel:view` |
| `diagnoses` | `diagnosis_id` | `assay.panel:view` |

Sample and configuration results are restricted to the user's exact
assay/environment assignments. Assays are restricted to granted assays. Explicit
assay-group restrictions use the registered assay. Counts, existence checks,
distinct values and IDs use the same restrictions as record pages. Gene lists,
groups and diagnoses remain shared reference catalogs under their existing
resource permissions.

Only fields declared by the corresponding `coyote.contracts.resource_metadata`
model are available. These include identifiers, availability, versions, assay
context and supported analysis types. Patient details, clinical findings, genes,
credentials and arbitrary document fields are excluded. Reading related records
requires the permission for each related resource, including when that resource
is used only as a filter.

## Basic and combined filters

Get the IDs of active assays:

```json
{"operation": "ids", "filters": {"is_active": true}}
```

To find assay IDs with active configurations in an environment, query `aspc`.
Environments belong to configurations and samples, not the assay record itself:

```json
{"operation": "distinct", "field": "asp_id", "filters": {"is_active": true, "environment": "production"}}
```

Find unreported samples in one assay and environment, returning selected fields:

```json
{
  "filters": {
    "asp_id": "example-assay",
    "environment": "production",
    "reported": false
  },
  "fields": ["name", "asp_id", "environment", "reported"],
  "sort": "name",
  "page": 1,
  "per_page": 50
}
```

Each filter uses scalar equality or a comparison object with `eq`, `in`, `gte`
and/or `lte`. Fields and comparisons combine with AND. For example:

```json
{
  "operation": "count",
  "filters": {
    "asp_id": {"in": ["assay-a", "assay-b"]},
    "time_added": {"gte": "2026-01-01T00:00:00Z", "lte": "2026-02-01T00:00:00Z"}
  }
}
```

Booleans must be JSON booleans; `1` and `"true"` are rejected for boolean fields.
Ranges apply only to integer and timestamp fields. String fields use exact,
case-sensitive comparison. Equality or membership on a list field matches an
element. Explicit null equality requires a present null field; it does not match
an absent field. Missing metadata is represented as null in returned projections.

## Related sample records

Filter samples using metadata from their active assay and exact stored
configuration revision. Include either related record when its metadata is needed:

```json
{
  "filters": {"environment": "production"},
  "related_filters": {
    "assay": {"platform": "illumina"},
    "configuration": {"is_active": false, "report_sections": "snvs"}
  },
  "fields": ["name", "asp_id"],
  "include": ["assay", "configuration"]
}
```

`related_filters` supports all operations on `samples`; `include` supports sample
record lists. Each included record appears under `related.assay` or
`related.configuration`. A missing or unauthorized relationship returns null and
cannot satisfy a related filter. The configuration's assay and environment must
match the sample. Historical revisions remain historical; the endpoint does not
replace a sample's stored revision with the latest configuration. Samples without
a stored configuration revision return null for that relationship.

Related comparisons use the same permitted fields and operators as direct reads.
There are no user-defined joins, nested relationships or raw collection queries.
A related filter may select at most 1,000 candidate catalog records; a broader
filter returns 422 and must be narrowed.

## Operations and pagination

- `list` (default): projected metadata records. Includes all matching revisions;
  use `is_active` or `version` when the desired revision matters.
- `ids`: distinct logical identifier strings, even when multiple revisions match.
- `count`: number of matching records in `count`, including zero.
- `exists`: whether any record matches, in `exists`, including false.
- `distinct`: unique scalar values for the required `field`. Array fields are
  flattened; absent fields and empty arrays contribute no values. An explicitly
  null value is retained once.

The response always has `items`, `total`, `page`, `per_page`, `has_next`, `count`
and `exists`. Only the requested aggregate is populated. Existence checks avoid
counting the full result and leave `total` at zero. Value-page totals count unique
values; record totals count records. Empty pages have `has_next: false`.

Pages start at 1; `per_page` defaults to 50 and has a maximum of 200. `page` has a
maximum of 10,000. List pages sort by the requested scalar field with identifier,
version and storage-identity tie breakers. IDs and distinct values sort by value.
`descending` reverses ordering. Separate requests reflect current data and are not
a transactional snapshot; resource changes can shift page boundaries.

The request permits at most 20 filter fields, 100 values per `in` comparison and
512 characters per filter string. Field projections contain 1–30 unique allowed
names. Unknown resources, fields, options, operators and query-string parameters
are rejected with 422. Mongo reads have a five-second execution limit per query.
