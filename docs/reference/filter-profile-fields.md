# Review filter fields and defaults

ASPCs define initial review filters; samples retain their own saved filter state.
These are structured application fields, not environment variables or raw pipeline
measurements. For query behavior and precedence, use [assay filtering](assay-filtering.md).
For center exceptions, use the separate [query-policy file](../configuration/clinical-query-policy-file.md).

## Profile structure

| Object path below `filters` | Supported scope | Omission behavior |
| --- | --- | --- |
| `somatic.snv` | DNA somatic SNV | Absent profile; not automatically an enabled analysis. |
| `germline.snv` | DNA germline SNV | Absent profile; requires enabled germline intent when present. |
| `somatic.cnv` | DNA CNV | Absent profile. |
| `somatic.coverage` | DNA coverage | Absent profile. |
| `somatic.translocation` | DNA translocation | Absent profile. |
| `somatic.fusion` | RNA fusion | Absent profile; RNA does not accept germline intent. |

Unknown profile keys are rejected. Once an analysis object is supplied, its omitted
fields receive the defaults below. This is distinct from omitting the whole object.
ASPC validation also checks that profiles fit the selected analyses and intents.
An explicit empty list is a saved selection, not an instruction to reload an ASPC.

## SNV fields

These keys apply to both SNV profiles except `max_control_freq`, which is somatic-only.
All listed keys have defaults and may be omitted within a supplied profile.

| Field | Accepted value / units | Default | Meaning |
| --- | --- | --- | --- |
| `min_freq` | Number, 0–1 fraction | `0.0` | Lower sample allele-frequency threshold. |
| `max_freq` | Number, 0–1 fraction | `1.0` | Upper sample allele-frequency threshold. |
| `max_control_freq` | Number, 0–0.5 fraction | `0.05` | Somatic control threshold; not accepted in germline filters. |
| `max_popfreq` | Number, 0–0.5 fraction | `0.05` | Population-frequency threshold. |
| `min_depth` | Nonnegative integer reads | `100` | Minimum total depth. Must accommodate `min_alt_reads`. |
| `min_alt_reads` | Nonnegative integer reads | `5` | Minimum alternative-allele support. |
| `vep_consequences` | Array of consequence identifiers | `[]` | Selected consequence terms; query policy determines applicable admission exceptions. |
| `snvlists` | Array of ISGL IDs | `[]` | Selected eligible SNV gene lists. |
| `adhoc_genes` | Object | `{}` | Explicit ad-hoc gene selections maintained through the gene-selection workflow. |

These numbers are software defaults, not a center's clinically approved thresholds.
The actual sample may use different saved values. Fractions such as `0.05` are
5%, not 0.05%, even when the UI presents percentage controls.

## CNV fields

| Field | Accepted value / units | Default | Meaning |
| --- | --- | --- | --- |
| `min_cnv_size` | Nonnegative integer bases | `100` | Minimum interval size. |
| `max_cnv_size` | Nonnegative integer bases | `50000000` | Maximum interval size; must not be below minimum. |
| `cnv_loss_cutoff` | Number on the producer ratio scale | `-0.3` | Loss threshold. |
| `cnv_gain_cutoff` | Number on the producer ratio scale | `0.3` | Gain threshold; must exceed loss cutoff. |
| `cnveffects` | Array containing `gain` and/or `loss` | `["gain", "loss"]` | Selected event effects. |
| `cnvlists` | Array of ISGL IDs | `[]` | Selected eligible CNV gene lists. |
| `adhoc_genes` | Object | `{}` | Explicit ad-hoc gene selections. |

There is no single `cnv_cutoff` setting. Gain and loss have separate fields.
The parser's ratio normalization does not establish a new universal measurement scale.

## Coverage fields

| Field | Accepted value / units | Default | Meaning |
| --- | --- | --- | --- |
| `warn_cov` | Nonnegative integer depth | `100` | Warning threshold used for coverage review. |
| `error_cov` | Nonnegative integer depth | `10` | Error threshold; must not exceed `warn_cov`. |

These fields classify recorded coverage. They do not turn a missing measurement
into zero or alter the D4 coverage file.

## RNA fusion and DNA translocation fields

| Field | Profile | Accepted value | Default | Meaning |
| --- | --- | --- | --- | --- |
| `fusion_callers` | RNA fusion | Array of configured supported caller IDs | `[]` | Caller selection; does not run a caller. |
| `fusion_descriptions` | RNA fusion | Array of evidence terms | `[]` | Caller description selections. |
| `fusion_effects` | RNA fusion | Array of effect terms | `[]` | Fusion effect selections. |
| `min_spanning_pairs` | RNA fusion | Nonnegative integer | `0` | Minimum spanning-pair support. |
| `min_spanning_reads` | RNA fusion | Nonnegative integer | `0` | Minimum spanning-read support. |
| `fusionlists` | Both | Array of eligible ISGL IDs | `[]` | Gene-pair finding scope. |
| `adhoc_genes` | Both | Object | `{}` | Explicit ad-hoc gene selections. |

DNA translocation profiles do not accept RNA caller or spanning-support settings.
For RNA, one caller observation must satisfy the combined predicates; support
from separate calls is not added together to pass a filter. Display/reporting
uses the call marked selected. See [fusion evidence](ingest-files/fusions-json.md).

## Example and application

This synthetic fragment supplies two thresholds and lets the remaining SNV fields
use their typed defaults:

```json
{
  "filters": {
    "somatic": {
      "snv": {"min_depth": 100, "min_alt_reads": 5}
    }
  }
}
```

It is not a complete ASPC or sample request and does not enable an analysis by
itself. Use the assay configuration or sample filter editor for real changes.
A new ASPC revision does not overwrite existing sample selections. Resetting a
sample's filters is an explicit operation; saved report artifacts are not rewritten.
