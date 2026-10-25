# Individual resource fields

Request one metadata key using `GET /api/v1/samples/{sample_id}/fields/{field}`
or the corresponding resource route below. Each response contains only the requested
value as JSON, preserving its type: string, number, boolean, array, or null.

For example:

| Request | Example JSON response |
| --- | --- |
| `GET /api/v1/samples/DEMO_001/fields/name` | `"DEMO_001"` |
| `GET /api/v1/samples/DEMO_001/fields/asp_id` | `"demo-hematology_gmsv1"` |
| `GET /api/v1/samples/DEMO_001/fields/environment` | `"testing"` |
| `GET /api/v1/samples/DEMO_001/fields/reported` | `false` |
| `GET /api/v1/resources/asp/demo-hematology_gmsv1/fields/supported_analyses` | `["SNV", "CNV"]` |

Keys follow the application resource contracts. The assay key is `asp_id`, modality
is `asp_category`, and sequencing family is `asp_family`.

## Routes and supported keys

| Route prefix (append `/fields/{field}`) | Permission | Allowed keys |
| --- | --- | --- |
| `/api/v1/samples/{sample_id}` | `sample:view` | `name`, `asp_id`, `asp_group`, `diagnosis_id`, `environment`, `asp_category`, `asp_family`, `ingest_status`, `reported`, `version`, `time_added` |
| `/api/v1/resources/asp/{asp_id}` | `assay.panel:view` | `asp_id`, `display_name`, `asp_group`, `asp_category`, `asp_family`, `platform`, `is_active`, `version`, `supported_analyses`, `expected_files`, `required_files` |
| `/api/v1/resources/aspc/{aspc_id}` | `assay.config:view` | `aspc_id`, `display_name`, `asp_id`, `asp_group`, `diagnosis_id`, `environment`, `asp_category`, `platform`, `reference_genome`, `is_active`, `version`, `analysis_types`, `report_sections` |
| `/api/v1/resources/assay-groups/{group_id}` | `assay.panel:view` | `group_id`, `display_name`, `parent_group_id`, `is_active`, `version` |
| `/api/v1/resources/diagnoses/{diagnosis_id}` | `assay.panel:view` | `diagnosis_id`, `display_name`, `description`, `is_active`, `version`, `asp_ids` |
| `/api/v1/resources/genelists/{isgl_id}` | `gene_list.insilico:view` | `isgl_id`, `displayname`, `name`, `list_type`, `diagnosis`, `asp_ids`, `asp_groups`, `gene_count`, `is_active`, `is_public`, `adhoc`, `version` |

All routes require [API authentication](authentication.md). Sample requests also enforce
the caller's assay, biological group, and environment access. An unsupported key returns
`422`; a missing resource returns `404`. An absent optional value returns JSON `null`.
Assay and configuration lookups select the active revision.

`report_sections` reads the configuration's `reporting.report_sections` list.
Diagnosis `asp_ids` returns its linked assay identifiers. Gene-list `gene_count`
returns the number of entries in `genes`. Sample `asp_group` uses the sample's group
when present and otherwise resolves it from its assay.

Clinical content, credentials, file paths, filters, and arbitrary nested collection
keys are excluded from the supported field lists. Available keys are also enumerated
in the OpenAPI path parameter definitions.

## Metadata snapshots

Replace `/fields/{field}` with `/metadata` on any resource prefix above to fetch
all its permitted metadata in one response. For example,
`GET /api/v1/samples/DEMO_001/metadata` returns the allowed sample keys as a JSON
object. Snapshots use the same view permissions, sample access checks, active
revision selection, computed-value rules and null behavior as the individual reads.
They exclude clinical content, arbitrary nested fields, gene content and file paths.

The [Python SDK](../sdk/python-client.md) uses these routes for explicit `get()` and
`refresh()` calls. Attribute reads use the resulting local snapshot.

[API integration guide](README.md)
