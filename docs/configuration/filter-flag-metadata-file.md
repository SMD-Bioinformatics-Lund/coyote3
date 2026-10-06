# Filter flag metadata file

This YAML file turns VCF `FILTER` values into readable badge labels and
tooltips. It does not change filtering or tiering logic.

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

For caller-specific definitions, see [Caller registries and flag descriptions](../administration/clinical-vocabulary.md#caller-registries-and-flag-descriptions).
Within a scope, matching order is: full `terms` match, full `exact` match, first matching
`prefixes` entry, then the application's general fallback for common `PASS`,
`FAIL`, and `WARN` patterns. Add a `terms` entry whenever a generic prefix
cannot give reviewers a sufficiently specific explanation.
