# DNA structural findings: SnpEff-annotated VCF

Manifest key: `transloc`. Stored destination: `translocations`.

## Before submission

Provide SnpEff `ANN` annotations on DNA `BND`, `DEL` or `DUP` records with
`FILTER=PASS`. Eligible consequences are `gene_fusion`, `bidirectional_gene_fusion`,
`feature_fusion`, `frameshift_variant` and `transcript_ablation`. An annotation with
an explicitly declared `pseudogene` biotype does not qualify a finding for retention.
Other event types, failed filters and records without eligible annotations are
excluded with aggregate counts in the ingest warnings. A frameshift or transcript
ablation describes a gene-disrupting event; it does not establish a two-gene fusion.

These are **SnpEff consequences**, independent of VEP consequence catalogs. All
annotations remain embedded in the finding; no shared transcript-vault entry is
created. RNA fusion JSON uses a separate parser and collection.
Unlike small variants, translocation parsing does not resolve case/control roles
from manifest IDs; source genotype column names are preserved.

[Download the complete synthetic VCF](../../assets/examples/ingest/translocations-vcf.vcf), including header declarations and tab-separated records. All example identifiers and values are synthetic.
Ingest assigns `SAMPLE_ID` from the parent sample. Do not supply database IDs or review
state in pipeline files. The file must also satisfy the assay's required/expected file policy.

## Raw structure and fields

Illustrative annotation-bearing breakend record (real columns are tab-separated):

```text
#CHROM POS ID REF ALT QUAL FILTER INFO FORMAT SYNTHETIC-T
1 10001 bnd1 A A]2:20001] 60 PASS SOMATIC;SVTYPE=BND;ANN=A|gene_fusion|HIGH|GENE1&GENE2|ENSG000001&ENSG000002|transcript|ENST000001&ENST000002|protein_coding||c.?|p.? GT:PR:SR:UR 0/1:10,5:8,3:3
```

The ANN header must define the same order using SnpEff's ` | ` field-name
separators. For the excerpt this is `Allele | Annotation | Annotation_Impact |
Gene_Name | Gene_ID | Feature_Type | Feature_ID | Transcript_BioType | Rank |
HGVS.c | HGVS.p`. Header-declared extra fields remain possible.

| Key | Description | Mapping to `translocations` |
| --- | --- | --- |
| Standard VCF columns | Contig, position, alleles, source ID, quality | Same top-level fields; FILTER and FORMAT become lists |
| `INFO.SVTYPE` | Structural event type | Same nested key |
| `INFO.END` | Required explicit end for symbolic DEL/DUP, in 1-based inclusive coordinates | Top-level `END`; preserved explicitly because pysam reserves this INFO field |
| `INFO.MATEID`, `INFO.EVENT` | Mate record and event identifiers | Same nested keys |
| `INFO.SVINSLEN`, `INFO.SVINSSEQ` | Inserted sequence length and sequence | Same nested keys |
| `INFO.SOMATIC` | Somatic flag | Boolean, default false |
| `INFO.SOMATICSCORE`, `INFO.JUNCTION_SOMATICSCORE` | Caller evidence scores | Optional integers |
| `INFO.BND_DEPTH`, `INFO.MATE_BND_DEPTH` | Breakend depths | Optional integers |
| `INFO.PANEL` or `INFO.set` | Panel labels | Normalized into `INFO.PANEL[]` |
| `ANN.Allele` | Annotated allele | `INFO.ANN[].Allele` |
| `ANN.Annotation` | Ampersand-separated effects | List; only records containing `gene_fusion` or `bidirectional_gene_fusion` are retained |
| `ANN.Annotation_Impact` | SnpEff impact | Same annotation key |
| `ANN.Gene_Name`, `ANN.Gene_ID` | Gene names and identifiers, possibly joined with `&` | Same annotation keys |
| `ANN.Feature_Type`, `ANN.Feature_ID` | Annotated feature class and identifiers | Same annotation keys |
| `ANN.Transcript_BioType`, `ANN.Rank` | Transcript type and rank | Same annotation keys |
| `ANN.HGVS.c`, `ANN.HGVS.p` | HGVS descriptions | Stored as `HGVSc`, `HGVSp` (dots removed from keys) |
| `ANN.cDNApos`, `ANN.cDNAlength`, `ANN.CDSpos`, `ANN.CDSlength`, `ANN.AApos`, `ANN.AAlength` | Optional positions and lengths | Optional integer fields with these storage names; they are not inferred from unrelated combined fields |
| `ANN.Distance` | Optional distance annotation | Text |
| `ANN.ERRORS`, `ANN.WARNINGS`, `ANN.INFO` | Annotation diagnostics | Preserved; combined key `ERRORS / WARNINGS / INFO` normalizes to `INFO` |
| Genotype `PR`, `SR` | Paired/split-read support | Text; tuple values become comma-separated strings; missing → empty text |
| Genotype `UR` | Unique-read evidence | Float or null |
| Sample column name | Genotype source | `GT[].sample`; translocation parser does not apply the SNV case/control role resolver |

## Transcript selection

The ingest service supplies the same internal `hgnc_genes` reference maps used for
SNV transcript selection. The selection order is:

1. NCBI MANE Plus Clinical.
2. Ensembl MANE Plus Clinical.
3. NCBI MANE Select.
4. Ensembl MANE Select.
5. First eligible protein-coding annotation.
6. First eligible available annotation.

The shared VEP-canonical step is inapplicable to SnpEff and is skipped. Within each
step, SnpEff impact orders candidates as HIGH, MODERATE, LOW, MODIFIER, then missing
impact. HGNC lookup supports approved, previous and alias symbols. A MANE match
requires an exact version-independent transcript accession in `Feature_ID`,
`HGVSc` or `HGVSp` for **every gene partner**. Missing HGNC records never create a
MANE designation. When the entire reference is unavailable, ingest records a warning
and uses the applicable fallback.

The selected annotation occupies `INFO.ANN[0]`; the remaining annotations stay
embedded. `INFO.ANN_selection_source` records the selection criterion.
`INFO.MANE_ANN` is populated only for a MANE selection, never for a fallback.

## Custom feature-fusion pairs

A `feature_fusion` annotation with `Feature_Type=CUSTOM&sorted` requires a
`Feature_ID` in `GENE_IDENTIFIER` format and a distinct reciprocal `MATEID` pair.
Both partners must be retained PASS BND records. Mixed consequence lists containing
`feature_fusion` are handled in the same way.

One finding represents the pair. Its representative is selected by chromosome,
position and source ID, independently of VCF record order. Both normalized source
records, including genotype evidence and every original annotation, remain in
`source_records`. All combinations of custom partner annotations are retained;
they are possible annotated partners, not evidence of fusion direction or a
uniquely resolved transcript. Paired annotations retain a common impact only when
both sources agree; otherwise the combined impact is null.

Duplicate IDs, malformed custom identifiers, self-links, nonreciprocal links,
multiple mate IDs or missing/filtered mates fail file parsing. No partial finding
list is returned. Correct the VCF and resubmit the ingest job. Ordinary annotated
breakends that already describe a gene fusion do not require custom pairing.

## Requirements and missing values

| Input | Requirement / omission behavior |
| --- | --- |
| Standard VCF identity and alleles | Required; no coordinate or allele default. Symbolic DEL/DUP requires explicit END at or after POS. |
| `INFO.ANN` and header order | Required on supported PASS records. Missing ANN fails parsing; nonqualifying annotations alone do not become findings. |
| ANN `Allele`, `Gene_Name`, `Gene_ID`, `Feature_Type`, `Feature_ID` | Required in a retained annotation; no substitute gene or transcript IDs. |
| ANN `Annotation` | At least one annotation must include an eligible SnpEff term and qualifying biotype. |
| Other listed ANN fields | Optional in the stored contract; missing fields remain absent/null rather than inferred. |
| `INFO.SOMATIC` | Missing normalizes to `false`; absence is not independent germline evidence. |
| Optional INFO event, insertion, score and depth fields | No measured default; missing values remain absent/null. |
| `INFO.PANEL` | Empty list when no panel/set values are supplied. |
| Genotype `PR`, `SR` | Missing becomes empty text, not zero support. |
| Genotype `UR` | Missing becomes null. |
| `ID`, `QUAL` | Ordinary missing ID remains `.`; custom pairs require explicit unique IDs. Missing quality remains null. |

The stored annotation contract is not permission to omit the VCF structure that
the parser needs. Use the downloadable file as a syntax example and validate real
producer outputs in an isolated test deployment.

## Existing installations and API consumers

`END`, `source_records` and `INFO.ANN_selection_source` are additive fields. Existing
stored findings remain readable without a database migration. Re-ingestion from
the source VCF is required to recover previously excluded events, pair provenance,
or missing interval endpoints; these cannot be reconstructed from incomplete
stored documents. Re-ingestion must follow the normal reviewed replacement workflow.

Translocation list and detail responses expose `snpeff_conseq_translations` instead
of `vep_conseq_translations`. Deploy matching API and frontend versions together.
SnpEff annotations do not require a sample VEP version to display. Query rules can
use `END`, `INFO.ANN_selection_source`, `INFO.SVTYPE` and embedded annotation fields.
Query rules cannot recover records excluded during ingest.

Symbolic interval identities include END: `CHROM:POS-END^ALT`. Classifications,
annotation lookup, exports and report snapshots therefore distinguish events with
the same start but different ends. Existing breakend identities remain
`CHROM:POS^ALT`.

## Related contracts

- [Bundle preparation and file index](README.md)
- [Sample manifest](../sample-manifest.md)
- [Stored collection contracts](../mongodb-collections.md)
