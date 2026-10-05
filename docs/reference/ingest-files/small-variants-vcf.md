# Small variants: VEP-annotated VCF

Manifest key: `vcf_files`. Stored destination: `variants and anno_vep`.

## Before submission

Use normalized biallelic records. The parser does not split multiallelic sites. Match VCF sample column names to manifest `case_id` and `control_id`; explicit matches take precedence over the warned positional fallback. Supply `database_versions.vep` when version metadata cannot be extracted from the VCF header.

[Download the complete synthetic VCF](../../assets/examples/ingest/small-variants-vcf.vcf), including header declarations and tab-separated records. All example identifiers and values are synthetic.
Ingest assigns `SAMPLE_ID` from the parent sample. Do not supply database IDs or review
state in pipeline files. The file must also satisfy the assay's required/expected file policy.

## Raw structure and fields

The header must declare `INFO/CSQ`, `INFO/variant_callers`, the contigs, and each
FORMAT key used by the records. `CSQ` is a string list: commas separate transcripts
and pipes separate fields. Its description must end in the exact pipe-separated
field order. Blank annotation values retain their positions between delimiters.
The SNV parser reads raw `VAF`; a FORMAT field named only `AF` is not a substitute.

VCF `POS` is 1-based. Ingest does not normalize alleles, split multiallelic records,
or convert the reference build. Those operations belong in the producing pipeline.

An illustrative record, with columns separated by tabs in the real file:

```text
#CHROM POS ID REF ALT QUAL FILTER INFO FORMAT SYNTHETIC-T SYNTHETIC-N
1 10001 . A G 60 PASS variant_callers=sage;CSQ=G|missense_variant|MODERATE|GENE1|ENST000001.1|protein_coding|YES|ENST000001.1:c.10A>G|ENSP000001.1:p.Lys4Glu|SNV GT:DP:VAF:VD 0/1:100:0.4:40 0/0:100:0.0:0
```

The CSQ description for that example ends with this exact field order:

```text
Format: Allele|Consequence|IMPACT|SYMBOL|Feature|BIOTYPE|CANONICAL|HGVSc|HGVSp|VARIANT_CLASS
```

Declare `CSQ` as a string annotation list and declare each INFO/FORMAT field in
the VCF header. Use a `##contig` entry for each chromosome. This excerpt is not
a replacement for a valid VCF header. The manifest would specify
`case_id: SYNTHETIC-T` and `control_id: SYNTHETIC-N`.

| Section/key | Meaning and example | Stored mapping or transformation |
| --- | --- | --- |
| `CHROM` | Chromosome/contig, `1` | `variants.CHROM`; spelling preserved |
| `POS` | 1-based VCF position, `10001` | `variants.POS` integer |
| `ID` | Source variant identifier | `variants.ID`; missing ID becomes `.` |
| `REF` | Reference allele, `A` | `variants.REF` |
| `ALT` | Alternate allele, `G` | `variants.ALT`; multiple alleles are joined with commas, not split into independent findings |
| `QUAL` | Caller quality value | `variants.QUAL` |
| `FILTER` | Caller filter labels | Split into `variants.FILTER[]`; excluded FAIL records are not stored |
| `INFO.variant_callers` | Actual variant callers, such as `sage` or `sage\|mutect2` | Split into `variants.INFO.variant_callers[]`; VEP is an annotation version, not a caller |
| `INFO.SVTYPE` | Optional structural type | Also copied to `INFO.TYPE` by the SNV parser |
| `FORMAT.GT` | Genotype, `0/1` | `GT[].GT`; pysam allele tuple becomes slash-separated text |
| `FORMAT.DP` | Total read depth | `GT[].DP` |
| `FORMAT.VD` | Alternate read count | `GT[].VD` |
| `FORMAT.VAF` | Alternate fraction in 0–1 units | Renamed to `GT[].AF`; raw `VAF` removed |
| Sample column name | `SYNTHETIC-T` or `SYNTHETIC-N` | `GT[].sample`; `GT[].type` is resolved as case/control and the case entry is placed first |
| Other FORMAT fields | Pipeline-specific genotype evidence | Decoded from the header and retained when permitted by the genotype contract |
| `FORMAT` column definition | Colon-separated genotype key names | Used to decode each sample; standalone `FORMAT` is removed from stored small variants |
| `INFO.CSQ` | Transcript annotations | Used for selection, summary fields and `anno_vep`; full CSQ array removed from `variants` after staging |

The example produces case evidence `AF=0.4, DP=100, VD=40` and control evidence
`AF=0.0, DP=100, VD=0`. These fractions are displayed as percentages in the UI.

Each CSQ transcript is split according to the header, not a fixed column number.
Before selection, numeric CSQ strings are converted to numbers; ampersand-separated
numeric values collapse to their maximum. The annotation vault therefore retains
the parsed, normalized transcript rows, not a byte-for-byte copy of the source VCF.

The recognized annotation keys are:

| CSQ key | Meaning | Mapping/use |
| --- | --- | --- |
| `Allele` | Annotated alternate allele | Retained in complete annotation-vault transcript data |
| `Feature` | Transcript ID including version | Selected transcript feature; `variants.transcripts[]` aggregates IDs without version suffixes |
| `HGNC_ID` | HGNC gene identifier | Selected CSQ and HGNC/MANE reference lookup |
| `SYMBOL` | Gene symbol | Selected CSQ and aggregated `variants.genes[]`; selected symbol may be canonicalized through HGNC |
| `Consequence` | Ampersand-separated consequence terms | List in selected CSQ; union across transcripts in `consequence_terms[]` |
| `IMPACT` | VEP impact category | Selected CSQ and transcript selection priority |
| `BIOTYPE` | Transcript biotype | Selected CSQ; protein-coding selection rule |
| `CANONICAL` | VEP canonical flag, normally `YES` or empty | Used by canonical protein-coding selection rule |
| `ENSP` | Protein identifier | Selected CSQ |
| `INTRON` | Intron position/count text | Selected CSQ |
| `EXON` | Exon position/count text | Selected CSQ |
| `STRAND` | Transcript strand | Selected CSQ |
| `PolyPhen` | Prediction text | Selected CSQ |
| `SIFT` | Prediction text | Selected CSQ |
| `CADD_PHRED` | Annotation score | Selected CSQ stores text, including numeric values normalized to text |
| `CLIN_SIG` | Clinical-significance terms | Split on `&`, with blanks and duplicates removed |
| `VARIANT_CLASS` | VEP variant class | Selected CSQ and top-level `variant_class` (from first CSQ) |
| `HGVSc` | Transcript-prefixed coding HGVS | Prefix removed for compact selected CSQ and aggregated `HGVSc[]` |
| `HGVSp` | Protein-prefixed protein HGVS | Prefix removed for compact selected CSQ and aggregated `HGVSp[]` |
| `COSMIC` | Ampersand-separated COSMIC identifiers | Aggregated `cosmic_ids[]` |
| `Existing_variation` | Existing variant IDs | dbSNP identifiers collected; first retained as `dbsnp_id` |
| `PUBMED` | Ampersand-separated publication IDs | Aggregated `pubmed_ids[]` |
| `gnomAD_AF` | gnomAD exome frequency | First CSQ supplies `gnomad_frequency`, using the parser's maximum-frequency extraction |
| `gnomADg_AF` | gnomAD genome frequency | Used when the exome frequency is absent |
| `MAX_AF` | Maximum population frequency | Supplies `gnomad_max` when a gnomAD source is present |
| `ExAC_MAF` | Allele-specific ExAC frequency | Parsed against ALT into `exac_frequency` |
| `GMAF` | Allele-specific 1000 Genomes frequency | Parsed against ALT into `thousandG_frequency` |
| Keys containing `dhotspot_OID`, `gihotspot_OID`, `luhotspot_OID`, `cnshotspot_OID`, `mmhotspot_OID`, `cohotspot_OID` | Pipeline hotspot identifiers | Grouped into `hotspots` by the corresponding prefix |
| Other CSQ header fields | Additional VEP/plugin annotations | Complete transcript rows are retained in the annotation vault; not every field is copied into selected CSQ |

Derived identifiers include `simple_id` and `simple_id_hash`, built by the variant
identity helper from chromosome, position, reference, and alternate alleles.
`anno_vep` stores the complete transcript set keyed by variant identity and VEP
version. `variants.INFO.selected_CSQ` contains the compact chosen transcript;
`selected_csq_feature` identifies it. `samples.database_versions.vep` supplies the
VEP badge and version-specific metadata lookup. None of these makes VEP a caller.

## Parsing and retained evidence

### Sample columns and annotation versions

| Column identity | Role resolution |
| --- | --- |
| Case and control IDs both match | Matched columns retain their explicit roles. |
| Single column matches the case, without a declared control | Accepted as case-only evidence. |
| Two columns with one ID match | The match is preserved; the other role is inferred with a warning. |
| One or two columns with neither ID matching | Warned positional fallback: first is case, second is control when present. Producers should correct the IDs. |
| Unresolved multi-sample input, duplicate column names, or identical case/control IDs | Rejected when roles cannot be resolved unambiguously. |

When both role IDs match a larger VCF, only those matched columns are retained.
For predictable sample linkage, export only the intended case/control columns.

VEP version metadata is read from `##VEP=` within the first 500 text header lines.
Supply the manifest's `database_versions` explicitly when that header is unavailable,
including compressed inputs. `expression_version` and `classifier_version` belong
to other analysis formats and do not identify the VEP annotation release.

### Normalization and transcript selection

- `INFO.variant_callers` is split from a pipe-delimited string into a list.
- `FILTER` is split from semicolon text into a list.
- The VCF `CSQ` annotation is reduced into `INFO.selected_CSQ` and
  `INFO.selected_CSQ_criteria` on the sample-local variant row. The parser also
  stores `consequence_terms`, the ordered union of all VEP consequence terms
  across the variant's transcript rows. The complete transcript set is stored
  once in the versioned `anno_vep` collection.
- Canonical transcript selection prefers:
  1. NCBI/RefSeq MANE Plus Clinical transcript
  2. Ensembl MANE Plus Clinical transcript
  3. NCBI/RefSeq MANE Select transcript
  4. Ensembl MANE Select transcript
  5. VEP `CANONICAL == YES` on a protein-coding transcript
  6. first protein-coding transcript
  7. first transcript fallback
- `Feature` identifies the precise VEP transcript row. NCBI selectors require a
  native `NM_...` or `NR_...` feature, while Ensembl selectors require a native
  `ENST...` feature. Linked VEP `MANE` values are retained for review but do
  not make an Ensembl row eligible for an NCBI selector.
- Every parsed transcript consequence is also written to the immutable
  `anno_vep` vault under `simple_id_hash` and the sample VEP version. Manual
  transcript changes read from this vault, so SIFT, PolyPhen, CADD, HGVS, exon,
  intron, and consequence values remain tied to the exact VEP version used when
  the sample was ingested.
- `INFO.selected_CSQ` is a compact display projection. Raw MANE and canonical
  VEP evidence is retained in `anno_vep.CSQ[]`. The detail API derives current
  HGNC match information, MANE badges, and VEP-canonical display state when it
  returns alternate transcripts; those mutable values are not stored in either
  collection.
- Consequence filters query `variants.consequence_terms`, not the selected
  transcript and not the VEP vault. A consequence on a clinically relevant
  alternate transcript therefore remains filterable without changing the
  selected display transcript.
- The parser adds:
  - `genes`
  - `transcripts`
  - `HGVSc`
  - `HGVSp`
  - `cosmic_ids`
  - `dbsnp_id`
  - `pubmed_ids`
  - `hotspots`
  - `simple_id`
- GT rows are normalized so:
  - sample columns are assigned case/control roles by manifest ID matching
  - `VAF` is moved into `AF`

Current ingest exclusions:

- variants with `FAIL_NVAF`
- variants with `FAIL_LONGDEL`
- variants with any `FAIL_PON_*`

The parser also skips records whose transcript features all start with `X`, unless
their symbols include `HNF1A`, `MZT2A`, `SNX9`, `KLHDC4`, `LMTK3`, or `PTPA`.
This is an ingest exclusion, distinct from later user-controlled review filters.

## Related contracts

- [Bundle preparation and file index](README.md)
- [Sample manifest](../sample-manifest.md)
- [Stored collection contracts](../mongodb-collections.md)
