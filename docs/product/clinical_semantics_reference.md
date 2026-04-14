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

| Indicator | Metric Group | Professional Meaning |
|---|---|---|
| `PASS` | Resolved | Significant variant passing all primary quality filters. |
| `GERM` | Origin | Potential or confirmed germline variant. |
| `HP` | Warning | Located within a homopolymer region. |
| `SB` | Caution | Strand-bias detected above acceptable thresholds. |
| `LO` / `XLO` | Sensitivity | Low or Extremely Low Allele Frequency (VAF). |
| `PON` | Comparative | Frequently observed in technical Panel-Of-Normals. |
| `FFPE` | Preparation | Preparation artifact typical of FFPE tissue samples. |
| `N` | Background | Observed in matched normal sample above acceptable limits. |

## Sequence Consequence Terminology

The platform maps VEP-managed genomic consequences into standardized labels according to biological impact classes.

| Canonical Key | Platform Label | Impact Classification |
|---|---|---|
| `splice_acceptor_variant` | `splice acceptor` | `HIGH` |
| `frameshift_variant` | `frameshift` | `HIGH` |
| `missense_variant` | `missense` | `MODERATE` |
| `synonymous_variant` | `synonymous` | `LOW` |
| `intergenic_variant` | `intergenic` | `MODIFIER` |

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
