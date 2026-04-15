# Clinical Semantics and Terminology

This document defines the standardized clinical terminology, classification tiers, and operational flags utilized throughout the platform. It provides the definitive mapping between visual indicators, clinical significance, and persistent backend data definitions.

## Diagnostic Triage Tiers (Tier I..IV)

The platform evaluates findings against a standardized four-tier evidence-based classification system. These are stored numerically (`1` through `4`) and presented as prioritized clinical tiers in all reporting and interpretation views.

| Tier Value (Data) | System Label | Clinical Classification | Visual Token |
|---|---|---|---|
| `1` | `Tier I` | Strong Clinical Significance | `--color-tier1` |
| `2` | `Tier II` | Potential Clinical Significance | `--color-tier2` |
| `3` | `Tier III` | Uncertain Clinical Significance | `--color-tier3` |
| `4` | `Tier IV` | Benign or Likely Benign | `--color-tier4` |
| `999` | `Unclassified` | Not Classified | `--color-tier999` |

### Tier Persistence and Aggregation

Tier assignments are maintained across several key platform domains to ensure auditing integrity:
- **Active Classifications**: Maintained in `annotations` collections for real-time interpretation.
- **Reporting Snapshots**: Persisted in `reported_variants` at the moment of report finalization to preserve a historical record.
- **Analytic Rollups**: Aggregated in `dashboard_metrics` for center-level operational reporting.

## Actionable Finding Flags

These operational flags are boolean state indicators that control the visibility and reporting status of specific findings within the diagnostic pipeline.

| Functional State | Boolean Flag | System Logic |
|---|---|---|
| **False Positive** | `fp` | Designated as a technical artifact; removed from standard reporting view. |
| **Interesting** | `interesting` | Explicitly selected for summary sections or prioritized reporting review. |
| **Irrelevant** | `irrelevant` | Classified as clinically insignificant for the current diagnostic context. |
| **Noteworthy** | `noteworthy` | Retained for visibility in structural views without mandatory reporting inclusion. |

## Sequence Quality Indicators (Filter Badges)

The platform normalizes raw sequencing metadata into concise diagnostic badges. These indicators provide immediate context regarding variant quality and technical reliability.

### Canonical grouped badges

The DNA findings UI does not show every raw VCF `FILTER` token verbatim. In `coyote/blueprints/dna/filters.py`, multiple raw values are collapsed into a smaller badge vocabulary for display.

| Badge | Metric Group | Professional Meaning | Raw filter examples |
|---|---|---|---|
| `PASS` | Resolved | Variant passed all primary quality filters. | `PASS` |
| `GERM` | Origin | Confirmed or suspected germline-origin signal. | `GERMLINE`, `GERMLINE_RISK` |
| `HP` | Warning | Variant falls in a homopolymer context. | `WARN_HOMOPOLYMER*` |
| `SB` | Warning / Failure | Strand-bias warning or strand-bias failure. | `WARN_STRANDBIAS`, `FAIL_STRANDBIAS` |
| `LO` | Warning | Low tumor allele fraction. | `WARN_LOW_TVAF` |
| `XLO` | Warning | Very low tumor allele fraction. | `WARN_VERYLOW_TVAF` |
| `PON` | Warning / Failure | Seen in a panel of normals. | `WARN_PON_*`, `FAIL_PON_*` |
| `FFPE` | Warning / Failure | Seen in an FFPE artifact panel. | `WARN_FFPE_PON_*`, `FAIL_FFPE_PON_*` |
| `N` | Failure | Too much signal in matched normal. | `FAIL_NVAF` |
| `P` | Failure | P-value based failure. | `FAIL_PVALUE` |
| `LD` | Failure | Long deletion failure. | `FAIL_LONGDEL` |

### Rendering rules

- Repeated raw filters that map to the same grouped badge are shown only once.
- `WARN_NOVAR` is intentionally hidden from display.
- Unknown `WARN_*` and `FAIL_*` tokens are still rendered as raw badges so new pipeline output remains visible.
- Badge color communicates warning versus failure, even when the short text token is the same, for example `SB`, `PON`, and `FFPE`.

## Sequence Consequence Terminology

The platform uses VEP Sequence Ontology consequence terms from the selected transcript (`selected_CSQ`). These are not a single fixed platform vocabulary hardcoded in templates. Instead, consequence grouping and translation are sourced from the `vep_metadata` collection for the sample's `vep_version`.

### Consequence sources in the code

- Raw transcript consequence terms are stored from VEP on each variant.
- Filter-group options for the UI come from `vep_metadata.consequence_groups`.
- Report-time wording and translations come from `vep_metadata.conseq_translations`.
- Query filters expand a selected group such as `missense` or `splicing` into one or more underlying SO terms.

### Common consequence terms

The exact available groups depend on the seeded `vep_metadata` document, but common terms and examples include:

| SO Term | Typical short label | Impact Classification |
|---|---|---|
| `splice_acceptor_variant` | `splice acceptor` | `HIGH` |
| `splice_donor_variant` | `splice donor` | `HIGH` |
| `stop_gained` | `stop gained` | `HIGH` |
| `frameshift_variant` | `frameshift` | `HIGH` |
| `missense_variant` | `missense` | `MODERATE` |
| `splice_region_variant` | `splice region` | `MODERATE` |
| `inframe_insertion` | `inframe insertion` | `MODERATE` |
| `inframe_deletion` | `inframe deletion` | `MODERATE` |
| `synonymous_variant` | `synonymous` | `LOW` |
| `intron_variant` | `intron` | `MODIFIER` |
| `intergenic_variant` | `intergenic` | `MODIFIER` |

### Important behavior

- A single transcript consequence may contain more than one SO term, for example `missense_variant&splice_region_variant`.
- The DNA review UI splits multi-valued consequences and shows the selected transcript consequence terms directly.
- Filter groups in `sample.filters.vep_consequences` are version-aware through `sample.vep_version`, not a permanent global list baked into the frontend.

## Population Frequency Logic

### Threshold Enforcement

Population frequency analysis is driven by integrated gnomAD and ExAC datasets. The system resolves variant-level metadata against `gnomad_frequency` (Primary AF) and `gnomad_max` (MAX AF).

### Filter Behavior

The platform enforces population filters using the sample-specific `max_popfreq` attribute (Default: `0.01`). Findings with population frequencies exceeding the configured threshold are flagged in the interface for de-prioritization. Evaluation logic follows a "safe-include" model where missing or non-numeric frequency data does not result in automatic exclusion.

## Data Interpretation Framework

All interpretations must be read using the following diagnostic hierarchy:
1.  **Tier Assignment**: Primary indicates the clinical priority level.
2.  **Quality Context**: Badges address technical reliability (e.g., `PASS` vs `PON`).
3.  **Biological Impact**: Short labels indicate the genomic consequence and severity impact class.
4.  **Population Content**: Percentage-based frequencies compared against active cohort thresholds.
5.  **Operational Status**: Finding flags determine reporting participation and triage category.
6.  **Transcript Logic**: Selection is impact-driven and RefSeq-prioritized to ensure clinical relevance.

## Transcript Selection Strategy

During DNA variant ingestion, the platform automatically resolves a "Canonical" transcript for every finding. This strategy ensures clinical relevance and prioritized interpretation across diverse annotation sources.

### Selection Priority

The ingestion parser (`DnaIngestParser`) selects the primary transcript according to a strict priority sequence:

1.  **Database Canonical Override**: Matches against internal gene-to-RefSeq mappings (version-agnostic).
2.  **VEP Canonical Attribute**: Identical to detections where `CANONICAL == "YES"`.
3.  **Biotype Priority**: Selection of the first available "Protein Coding" transcript.
4.  **Sequential Fallback**: Selection of the first available transcript in the annotation payload.

### Impact-Driven Iteration

The selection logic iterates through consequence predictions grouped by biological impact severity (`HIGH` -> `MODERATE` -> `LOW` -> `MODIFIER`). This ensures that the most deleterious clinical effect is prioritized for the selected canonical transcript whenever multiple valid transcripts exist.
