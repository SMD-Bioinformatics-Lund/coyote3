# Images and alignment resources

Images and alignments support visual review. They are not substitutes for the VCF
or JSON evidence files parsed into finding records.

| Manifest key | Input | Ingest handling |
| --- | --- | --- |
| `cnvprofile` | Path to a CNV profile image, normally PNG | Registered under `samples.files.cnvprofile`; no CNV rows are derived from the image. |
| `case_bam`, `control_bam` | Case/control alignment filenames | Stored as alignment metadata under the corresponding sample specimen. |
| `case_bai`, `control_bai` | Matching alignment index filenames | Stored with the corresponding alignment metadata. |

## Requirements and missing resources

| Resource | Required? | Omitted value / effect |
| --- | --- | --- |
| `cnvprofile` | According to the ASP required-file policy | No profile image; numeric CNV JSON remains independent. |
| `case_bam`, `case_bai` | Optional | Empty text on initial ingest. Missing BAM metadata may use catalog lookup; no readable alignment is guaranteed. |
| `control_bam`, `control_bai` | Optional, paired specimen only | Empty text on initial ingest; an unpaired sample has no control specimen. |
| ASP `igv` configuration | Optional | Catalog directory lookup remains the fallback. |
| `igv.base_folder` | Required when `igv` is configured | No default folder is inferred. |
| `igv.bam_subfolder`, `igv.design_bed` | Optional | Empty text: BAMs use the base folder; no design BED is specified. |

These alignment fields register references, not uploaded BAM content. On metadata
updates, omission preserves existing references, while explicit null/empty values
clear them. See [alignment references](../sample-manifest.md#alignment-references-for-igv)
for index replacement and workstation path rules.

## Manifest example

```yaml
cnvprofile: /ingest/SYNTHETIC-T.cnv.png
case_bam: SYNTHETIC-T.bam
case_bai: SYNTHETIC-T.bam.bai
control_bam: SYNTHETIC-N.bam
control_bai: SYNTHETIC-N.bam.bai
```

This is a resource excerpt, not a complete sample manifest. Alignment names are
resolved within the ASP's IGV folder, with catalog fallback for unconfigured assays.
They are not ordinary JSON evidence paths. The alignment service must be able to
serve the alignment and its matching index for the intended sample and reference build.

The CNV image should identify its axes, scale, and contigs. Numeric copy-number
evidence must still be submitted separately as [CNV JSON](copy-number-json.md).
Coyote3 does not call variants from BAM files or extract measurements from images.

- [Sample manifest](../sample-manifest.md)
- [File preparation requirements](README.md)
