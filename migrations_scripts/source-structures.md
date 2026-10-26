# Observed v2 and v3 sample structures

This reference records field relationships observed through read-only queries of
the explicitly selected `coyote` and `coyote3` databases. Inspection used 15 random
samples from each database, additional random v2 samples by supported assay, and
scope/diagnosis aggregates. It contains no source documents, patient identifiers,
authors, paths or report content. Sampling does not establish complete coverage of
all historical formats.

## Version-specific identity and scope

| Meaning | v2: `coyote.samples` | v3: `coyote3.samples` | Conversion |
| --- | --- | --- | --- |
| Sample identity | `_id`: ObjectId | `_id`: ObjectId | Retain exactly; derived records use BSON `sample_oid` or string `SAMPLE_ID` according to their contract. |
| Sample name | `name`: string | `name`: string | Retain; do not infer an unknown case ID from its naming convention. |
| Physical assay | `groups`: array, generally one item | `assay`: string; `groups` absent on most records | Select the version-specific field and produce scalar lowercase `asp_id`. |
| Biological assay group | Usually absent in sampled v2 records | `assay` is the physical ASP, not this group | Defined on the target ASP. `asp_group` is not a required declared sample field; retain it only when explicitly recorded or reviewed. |
| Diagnosis | `subpanel` optional | `subpanel`: string, including empty strings | Lowercase named IDs. Explicitly review old labels or empty/Base mappings against the installed target configuration. |
| Environment | Often absent | `profile`: string | Rename recorded `profile`; missing environment requires verified metadata. |
| Modality | Often absent | `omics_layer`: `DNA` | Normalize recorded modality to `dna`; missing v2 modality requires verified metadata. |
| Sequencing family | Often absent | `sequencing_scope`: `panel` or `WGS` | Combine recorded family and modality into `panel-dna` or `wgs-dna`. |
| Pipeline | Often absent | `pipeline`, `pipeline_version` | Preserve recorded values. Missing historical pipeline information is not taken from today's installed pipeline. |
| Case/control | Missing in sampled v2 cases | `case_id`, `control_id`, `case`, optional `control`, `paired`, `sample_no` | Preserve recorded IDs and nested sequencing data; request evidence for missing v2 identity. |
| Creation | `time_added`: BSON date | `time_added`: BSON date | Retain original instant; do not substitute migration time. |

The v3 distribution identifies the current physical hematology assay as
`hema_GMSv1`; almost all of those records lack `groups`. The v3 selector must therefore
match `assay` first. A `groups`-only query would miss most intended samples.
The listed `gmshem` v3 selector currently has no matching source records and must
not silently fall back to another assay.

For the older v2 `group`/`assay` format, the operator supplies this additional
mapping: `myeloid` → `myeloid_gmsv1`, `solid` → `solid_gmsv3`, and
`hematology` → `hema_gmsv1`. The same rule applies when `groups` contains the
matching older biological label. These are operator-supplied mappings, not inferred
from random document sampling. A newer physical identifier in `groups` remains
the authoritative ASP; the old `assay` is not renamed into `asp_group`.

## Files and saved filters

V2 `vcf_files` and `fusion_files` are arrays in inspected records, often with a
single path. V3 `vcf_files` is a string. One recorded path becomes a current file
registration; multiple paths need an explicit mapping rather than taking the first.
Original `cnv`, `cov`, `transloc`, `cnvprofile`, `gens` and `gensNorm` fields can occur.
Only current supported file keys are promoted into `files`; remaining source
metadata stays retained and must not be mistaken for an imported analysis collection.

V2 review state is stored in top-level fields including `filter_min_reads`,
`filter_min_depth`, frequency bounds, fusion read/span support, CNV size bounds,
and dictionaries such as `checked_csq`, `checked_genelists`, `checked_cnveffects`,
`checked_fusioneffects`, `checked_fusioncallers` and `checked_fusionlists`. Numeric
thresholds can be stored as strings. V3 has a flat `filters` object with SNV/CNV
thresholds, `vep_consequences`, `cnveffects`, `genelists` and coverage thresholds.

Neither shape is the current intent-aware filter contract. The converter requires
an explicitly reviewed `canonical_filters` document and `filters_reason`, bound to
the original source hash. V2 top-level filter fields are removed only after that
mapping is provided. Preserving them as unused extras while applying new defaults
would change review behaviour.

## Embedded comments and reports

Both sources embed `comments[]` with `_id`, `author`, `text`, `hidden` and
`time_created`; hidden comments can also have `hidden_by` and `time_hidden`.
Extraction preserves these values and adds `sample_oid` and `sample_name`.

V2 report entries contain `_id`, `author`, `filepath`, `report_num` and
`time_created`. V3 also stores `report_id`, `report_type` and `report_name`.
The v2 destination identifier can be derived from the original report ObjectId,
and its display name from the original filename. These operations do not assign
a new author/date or regenerate the report.

The parent `report_num` is checked against the maximum embedded report number;
the latest retained report sets the current latest-report pointer. Any existing
snapshot remains historical content. Report artifacts must be copied separately.

## RNA results and DNA QC

RNA samples can contain `expr` with `sample`, `reference` and `expression_version`;
`classification` with classifier results/version; and `QC[]` with alignment,
splicing, gene-body and insert-size values. Those become `rna_expression`,
`rna_classification` and `rna_qc`, with string `SAMPLE_ID` matching the original
sample ObjectId. Dynamic reference-expression column names belong in the protected
source archive, not public documentation or terminal logs.

Some observed RNA QC records lack provider genotype fields required by the current
`rna_qc` contract. Preserve these incomplete payloads unchanged in `samples.QC`,
without emitting an incomplete standalone `rna_qc` record or adding measurements.
Multiple QC results also remain embedded. Complete single results still become
standalone `rna_qc` records. Invalid values in otherwise complete records continue
to fail validation.

DNA `QC[]` has a different shape: read/duplication counts, insert-size data,
`pct_above_x` and sometimes coverage statistics. Some counts are strings, and there
can be multiple entries. There is no corresponding current standalone DNA-QC
collection in the collection registry. Retain this payload unchanged on the sample
and in `source_samples.jsonl`; never send it through the RNA QC schema.

## Scope gaps requiring explicit decisions

The v2 `tumwgs` source includes recorded `hema` and `solid` subpanels, but most
records have no subpanel. Only explicitly recorded matches are selected by
`tumwgs-hema` / `tumwgs-solid`. Migrate the remaining records separately using
`--assay-id tumwgs`, retaining that assay and assigning `diagnosis_id: "legacy"`.
This is the operator-approved label for missing, null, blank or `None` subpanels;
an existing `legacy` subpanel belongs to the same selection. No hema/solid cohort
is inferred from names or file paths.

V3 named subpanels include mixed-case historical labels and empty strings. The
scripts apply the [approved subpanel renames](README.md#scope-and-mapping), including
`AlloSCT` to `allo-sct` and empty strings to `base`. Additional changes outside
that table use the review's explicit `scope_mapping`, with a reason.
No diagnosis is created by these sample converters.

Separate source finding collections are outside this first sample-extraction stage.
The inspected v2 database contains both `cnvs` and `cnvs_wgs`, and both `variants`
and `variants_idref`. The separate converters retain original finding IDs and reject
overlapping sample/allele identities across reviewed bundles. Collection names alone
are insufficient evidence that either copy can be discarded.

The [non-variant related-data procedure](related-data.md) documents the additional
read-only collection inspection and source-to-target mappings, including old CNV
VCF fields, interval coverage versus structured D4 data, missing translocation
support fields, and orphan sample references.

The [variant procedure](variants.md) covers the additional read-only random inspection
of v2 `variants`, v2 `variants_idref` and v3 `variants`. V2 examples had numeric
chromosomes, raw VEP columns and no selected consequence; v3 examples had slim
CSQ arrays, recorded selections and summary fields. Full source CSQ rows and the
selected row go into `anno_vep`; the current variant keeps the selected row and
schema-defined summaries. The data owner confirmed VEP 103 for all v2/v3 variants;
conflicting recorded releases fail validation. Recorded selections are preserved.

[Procedure and commands](README.md)
