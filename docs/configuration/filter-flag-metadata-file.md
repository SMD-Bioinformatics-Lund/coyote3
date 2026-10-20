# Filter flag metadata file

This YAML file turns VCF `FILTER` values into readable badge labels and
tooltips. Its global and SNV caller-specific `exact` and `terms` keys also supply
SNV flag-filter choices in sample review, assay configurations, finding query rules,
and clinical report rules. Changing the metadata alone does not exclude any finding
or change tiering logic.

The bundled file is `api/config/center/filter_flag_metadata.yaml`. When
`COYOTE3_CENTER_CONFIG_DIR` is set, the application reads `filter_flag_metadata.yaml`
from that directory instead. Selectable flag keys come from this file rather than
a frontend constant.

## Format and fields

YAML groups keys using indentation. Use spaces, not tabs. Mapping names such as
`terms` contain flags and their display properties; they are not query conditions.
The file is required in an external center directory. Its groups are optional;
an empty mapping `{}` is valid. Unknown properties and invalid severity names
are rejected at startup.

| YAML path | Required | Default if omitted | Allowed value and effect |
| --- | --- | --- | --- |
| `exact` | No | Empty mapping | Exact flag names; compared case-insensitively after normalization. |
| `terms` | No | Empty mapping | Detailed flag definitions; takes precedence over `exact`. |
| `prefixes` | No | Empty mapping | First matching flag prefix applies after `terms` and `exact`. Order matters. |
| `callers` | No | Empty mapping | Optional analysis/caller-specific groups; see the linked caller reference. |
| `callers.<analysis>.<caller>` | Only for a scoped override | No override | Same `terms`, `exact`, `prefixes` structure; analysis and caller must be registered. |
| `*.label` | No | No label override; existing display formatting applies | Short visible text. |
| `*.severity` | No | Existing flag-prefix severity fallback | `pass`, `fail`, `warn`, `info`, or `neutral`; presentation only. |
| `*.description` | No | No custom description | Tooltip explanation in plain language. |
| `*.hidden` | No | `false` | `true` suppresses the matched badge; it does not remove a finding. |

A definition with no label, severity or description does not necessarily make
an otherwise unrecognized flag visible. Define meaningful display metadata for
custom terms. Global fallback handling still recognizes common PASS/FAIL/WARN
patterns. Empty optional fields do not generate pipeline evidence.

## Example

```yaml
callers: {}
terms:
  EXAMPLE_REVIEW:
    label: Review
    severity: info
    description: Replace with the approved explanation for this pipeline flag.
    hidden: false
```

`EXAMPLE_REVIEW` is synthetic. Replace it with an actual validated pipeline flag;
adding it here neither emits that flag during ingest nor changes query thresholds,
classification or report wording. Deploy changes as part of a reviewed center
configuration release and recreate the consuming application processes.

## SNV flag filtering and rule conditions

Somatic and germline SNV profiles each support one `exclude_flags` list, empty by
default. It is stored alongside the other SNV values at
`filters.somatic.snv.exclude_flags` or `filters.germline.snv.exclude_flags` in both
ASPCs and sample snapshots. Each intent has its own selection. The field appears
with the other SNV filters in assay-configuration forms, the sample's SNV filter
sidebar, and the configured-filter overview for each enabled intent.

Any selected flag removes a finding carrying that exact stored VCF `FILTER` value,
including findings admitted by a query-rule exception. Matching is case-sensitive
and does not use display labels, severity, substring matching, or regular expressions.
An empty exclusion list removes no findings. Missing or empty `FILTER` values are
retained by this filter.

Choices include hidden flag definitions such as `WARN_NOVAR`; hiding a badge does not
prevent explicitly filtering its raw value. `prefixes` entries describe families of
badges and are not literal selectable flags. Define concrete flags under `terms` or
`exact` to make them selectable. Selection is optional; existing filter snapshots need
no rewrite and keep their previous behavior until flag selections are saved.

The finding query editor exposes these choices for the SNV `FILTER` field with
`in` (any selected flag), `nin` (none), or `all` (every selected flag), and supports
references to the active sample's `exclude_flags`. Clinical report
rules expose `finding.filter_flags` for each SNV and `item.filter_flags` inside a
findings collection condition. Use `contains` for one exact flag or `overlaps` for
any selected flag, and wrap the condition in an exclusion when appropriate. These
facts retain raw flags in the prepared report context, including hidden flags.

For caller-specific definitions, see [Caller registries and flag descriptions](../administration/clinical-vocabulary.md#caller-registries-and-flag-descriptions).
Within a scope, matching order is: full `terms` match, full `exact` match, first matching
`prefixes` entry, then the application's general fallback for common `PASS`,
`FAIL`, and `WARN` patterns. Add a `terms` entry whenever a generic prefix
cannot give reviewers a sufficiently specific explanation.
