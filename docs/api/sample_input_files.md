# Sample Ingest Input Files

This page describes the file inputs consumed by the sample ingestion service.

It separates two different contracts:

1. The **sample bundle manifest**: the top-level YAML file that tells ingest which sample is being loaded and which files belong to it.
2. The **raw input files**: the VCF and JSON payloads that the parser reads and turns into collection-shaped documents.

For the manifest itself, see [API / Sample YAML Guide](sample_yaml.md).
For endpoint usage, see [API / Ingestion API](ingestion_api.md).
For final persisted collection shapes, see [API / Collection Contracts](collection_contracts.md).

## Two-Layer Model

```text
sample YAML manifest
  -> normalized from pipeline names to the canonical ingest contract
  -> validated as a SamplesDoc
  -> points to raw file paths
  -> resolves assay/environment/omics metadata

raw input files
  -> parsed by DnaIngestParser or RnaIngestParser
  -> normalized into collection-shaped payloads
  -> written as sample-linked dependent documents
```

## Demo Fixtures Used Here

These repo fixtures are the best concrete reference for expected input shapes:

- `demo_data/ingest/generic_case_control.yaml`
- `demo_data/ingest/generic_case_control.final.filtered.vcf`
- `demo_data/ingest/generic_case_control.cnvs.merged.json`
- `demo_data/ingest/generic_case_control.cov.json`
- `demo_data/ingest/generic_rna_sample.yaml`
- `demo_data/collections/all_collections_dummy/fusions.json`
- `demo_data/ingest/generic_rna_expression.json`
- `demo_data/ingest/generic_rna_classification.json`
- `demo_data/ingest/generic_rna_qc.json`

## Manifest Layer

The sample YAML is the top-level ingest manifest.

It is responsible for:

- sample identity such as `name`, `case_id`, `control_id`
- optional sample-level biological sex through `sex`; paired case and control
  specimens share this value because they represent the same individual
- pipeline assay and environment identity such as `assay` and `profile`, mapped
  at ingest to canonical `asp_id` and `environment`
- omics-layer selection through `omics_layer`
- pipeline metadata such as `pipeline` and `pipeline_version`; DNA annotation
  database versions are normally read from the VCF `##VEP=` header
- flat file references such as `vcf_files`, `cnv`, `cov`, and `fusion_files`

Important behavior:

- The manifest is validated first through `SamplesDoc`.
- `omics_layer` controls which file keys are legal.
- `sex`, when supplied, must be `female`, `male`, or `unknown`; it is not inferred.
- YAML bundle upload warns about file keys outside the ASP's expected files and ignores those files before parsing. Direct canonical payload ingestion rejects unexpected declarations. Required/expected policy comes from `assay_specific_panels` (ASP), not the ASPC.
- Required ASP files must be present and readable before parsing starts.
- Optional expected files may be omitted. If an optional expected file path is present, Coyote3 treats it as declared data and the sample will not be marked ready unless that file is parsed and written successfully.
- Pipeline-authored `filters` and `analysis_intents` are replaced by the resolved
  ASPC configuration, not used to override clinical review defaults.

Pipeline manifests declare file paths as flat top-level keys, as documented in
[API / Sample YAML Guide](sample_yaml.md#pipeline-file-declaration-format).
Ingestion converts each declaration into `samples.files.<key>`, where the
stored record contains the source `path` and any available checksum or file-size
metadata.

See [API / Sample YAML Guide](sample_yaml.md) for the full manifest contract.

## Raw file contract summary

Keys are case-sensitive. The names below are the configured defaults in
`api/config/center/clinical_vocabulary.toml`. Each manifest file key contains one
path string, even names such as `vcf_files` and `fusion_files`. JSON files are
UTF-8 JSON, not JSONL or arbitrary CSV/TSV exports. Ingest attaches `SAMPLE_ID`
from the parent sample; producers do not need to generate MongoDB identifiers.
Validation of all declared evidence must succeed before the bundle commits.

| Manifest key | Raw format/root | Fields consumed | Stored destination |
| --- | --- | --- | --- |
| `vcf_files` | VEP-annotated VCF | Standard columns, `INFO/CSQ`, `INFO/variant_callers`, `FORMAT/GT`, `DP`, `VAF`, `VD`; see table below | `variants`, versioned `anno_vep` |
| `cnv` | JSON array of objects or object keyed by region | `chr`, `start`, `end`, `size`; optional `ratio`, `type`, `nprobes`, `genes`, `callers` | `cnvs` |
| `cnvprofile` | Image resource, normally PNG | No JSON or VCF fields; not parsed as finding rows | `samples.files.cnvprofile` |
| `cov` | JSON object | `genes` keyed by gene symbol; each gene has `covered_by_panel`, `transcript`, optional `exons`, `CDS`, `probes` | `panel_coverage`; parent sample supplies `sample` |
| `biomarkers` | JSON object | `name`; optional `MSIS`, `MSIP`, `HRD` objects | `biomarkers` |
| `transloc` | SnpEff-annotated breakend VCF | Standard columns, `INFO/ANN`, genotype fields; see table below | `translocations` |
| `fusion_files` | JSON array of fusion objects | `gene1`, `gene2`, `genes`, non-empty `calls` | `fusions` |
| `expression_path` | JSON object | `expression_version`, `sample`, `reference` | `rna_expression` |
| `classification_path` | JSON object | `classifier_version`, `classifier_results` | `rna_classification` |
| `qc` | JSON object | Read, splice, gene-body, genotype, and fragment metrics listed below | `rna_qc` |
| `pgx` | JSON object or array of objects; DNA or RNA | Object keys preserved; arrays wrapped as `records` | `pgx`; storage does not imply PharmCAT interpretation or recommendations |
| `case_bam`, `control_bam` | BAM filename string in YAML | Metadata only; resolved within the ASP IGV folder, with catalog fallback for unconfigured assays | `samples.case.bam`, `samples.control.bam` |
| `case_bai`, `control_bai` | BAI filename string in YAML | Metadata only; resolved within the same BAM directory | `samples.case.bai`, `samples.control.bai` |

### VCF columns and annotations

| Raw column/key | Raw representation | Ingest handling |
| --- | --- | --- |
| `#CHROM`, `POS`, `ID`, `REF`, `ALT`, `QUAL` | Tab-separated VCF columns; `POS` is a 1-based integer | Parsed through pysam; use normalized, biallelic SNV/indel records rather than relying on ingest to split multiallelic sites |
| `FILTER` | `PASS`, `.`, or semicolon-separated filter IDs declared in the header | Stored as `FILTER` list; SNV exclusions include `FAIL_NVAF`, `FAIL_LONGDEL`, and `FAIL_PON_*` |
| `INFO` | Semicolon-separated key/value entries and flags, with VCF header declarations | Decoded into an object; not a JSON column |
| `INFO/variant_callers` | Pipe-separated caller names | Required by SNV parser; stored as a list |
| `INFO/CSQ` | Comma-separated transcripts, pipe-separated fields | Required for SNVs; header description must end in the matching pipe-separated field list, normally `Format: Allele\|Consequence\|...` |
| CSQ fields | `Feature`, `SYMBOL`, `HGNC_ID`, `IMPACT`, `BIOTYPE`, `CANONICAL`, `Consequence`, `HGVSc`, `HGVSp`, `VARIANT_CLASS`, plus annotations available from the pipeline | Provide usable transcripts and impact values for selection; identifiers, HGVS, consequences and annotation-vault rows are derived from them |
| `FORMAT` | Colon-separated keys such as `GT:DP:VAF:VD` | Describes each sample column; SNVs retain normalized genotype objects and discard the standalone FORMAT list; translocations retain it |
| `FORMAT/GT` | Genotype, for example `0/1` | Genotype string in stored `GT[]` |
| `FORMAT/DP`, `FORMAT/VD` | Integer total and alternate depth | Required SNV genotype fields; missing clinical values must not be supplied as invented zeros |
| `FORMAT/VAF` | Numeric allele fraction, for example `0.12`, not `12` | Required by the SNV parser; renamed to `GT[].AF`. `AF` alone is not a substitute for raw `VAF` |
| Sample columns | Names matching manifest `case_id` and `control_id` | Names become `GT[].sample`; explicit ID matches determine roles. If neither matches, warn and use first as case and second as control. With two columns and one match, preserve it and infer the remaining role with a warning. Ambiguous multi-sample input is rejected. |
| `INFO/ANN` | Comma-separated annotations, pipe-separated fields with SnpEff header field names | Required for translocations; includes `Annotation`, `Gene_ID`, `HGVS.p` and other SnpEff fields; retains gene-fusion annotations |
| Translocation `FORMAT/PR`, `SR`, `UR` | Read-support fields when supplied | PR/SR preserved as strings; UR converted to number or null; missing PR/SR become empty strings |
| `##VEP=` | VEP/database version header | Metadata extraction reads the first 500 text header lines. Supply `database_versions` explicitly when the header is unavailable, including compressed inputs |
| YAML `filters` | Clinical filter profile object, not a VCF field | Pipeline values are ignored; ASPC supplies somatic/germline profiles. Do not rename VCF `FILTER` to `filters` |

### JSON evidence fields

Required fields below exclude the parent linkage injected by ingest. Extra
pipeline fields may be retained where the collection contract permits them;
they are not substitutes for required fields. See the generated collection
contracts for exhaustive types and defaults.

| Input | Raw keys and types | Validation/normalization |
| --- | --- | --- |
| CNV row | `chr`: string; `start`, `end`, `size`: integers; `genes[]`: objects with `gene` and optional `class`, `cnv_type` | `callers` accepts list or delimited string; `ratio` accepts numeric or supported event labels; omitted `nprobes` currently normalizes to zero |
| Coverage gene | `covered_by_panel`: boolean; `transcript`: object with `chr`, `start`, `end`, `transcript_id` | `exons`, `CDS`, `probes` are keyed objects, not arrays |
| Coverage region | `chr`: string; `start`, `end`: integers; optional `cov`: number/null; exon/CDS may include `nbr` | Missing coverage remains null; it is not measured zero coverage |
| Biomarker | `name`: string; optional `MSIS`/`MSIP`: `{tot: int, som: int, per: number}`; optional `HRD`: `{tai: int, hrd: int, lst: int, sum: int}` | JSON object, not an array; pass only measurements that exist |
| Fusion call | `caller`, `breakpoint1`, `breakpoint2`: strings; `spanpairs`, `spanreads`: integers; `longestanchor`: integer or string; `selected`: 0/1 | Exactly one selected call; omitted selection becomes 0; omitted `effect`, `desc` become empty strings, `commonreads` becomes 0 |
| Expression `sample[]` | `hgnc_symbol`, `ensembl_gene_id`: strings; `sample_expression`, `reference_sd`, `reference_mean`, `reference_median`, `reference_mean_mod`, `sample_mod`, `z`: numbers | All listed fields required for each sample expression row |
| Expression `reference[]` | `hgnc_symbol`, `ensembl_gene_id`; numeric `reference_sd`, `reference_mean`, `reference_median`; numeric `quant_values` map | Additional dynamic numeric reference values are collected into `quant_values` |
| Classification row | `class`: string; `score`: number; `true`, `total`: integers | `true` cannot exceed `total` |
| QC object | `sample_id`: string; `tot_reads`, `canon_splice`, `non_canon_splice`, `splice_ratio`, `provider_called_genotypes`, `flendist`: integers; `genebody_cov`: integer array; `genebody_cov_slope`: number; `provider_genotypes`: string map | All listed fields required |
| QC percentages | `mapped_pct`, `multimap_pct`, `mismatch_pct`: numbers | Required; range 0 to 100, unlike SNV VAF fractions |

## DNA Raw Input Files

The DNA parser reads file paths from these manifest keys:

- `vcf_files`
- `cnv`
- `cnvprofile`
- `cov`
- `biomarkers`
- `transloc`
- `pgx`

`cnvprofile` is a sample image resource. It is retained under `samples.files.cnvprofile`
and shown in the CNV review tab, but it does not create a dependent database
document.

### SNV / Indel VCF

Primary demo file:

- `demo_data/ingest/generic_case_control.final.filtered.vcf`

Expected characteristics:

- VCF text file readable by `pysam.VariantFile`
- VEP-annotated `INFO/CSQ` field present
- `INFO.variant_callers` present
- Per-sample `FORMAT` fields include `GT`, `DP`, `VAF`, and `VD`
- For paired DNA input, sample IDs are matched before using the warned positional fallback described above.

Observed demo header features:

- `##fileformat=VCFv4.2`
- `##INFO=<ID=variant_callers,...>`
- `##INFO=<ID=CSQ,...>`
- `##FORMAT=<ID=GT,...>`
- `##FORMAT=<ID=DP,...>`
- `##FORMAT=<ID=VAF,...>`
- `##FORMAT=<ID=VD,...>`

Parser behavior:

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
  - sample 0 becomes `type=case`
  - sample 1 becomes `type=control`
  - `VAF` is moved into `AF`

Current ingest exclusions:

- variants with `FAIL_NVAF`
- variants with `FAIL_LONGDEL`
- variants with any `FAIL_PON_*`

Minimal practical requirements:

- valid VCF syntax
- usable `CSQ`
- usable per-sample genotype fields
- readable filesystem path from the API runtime

### CNV JSON

Primary demo file:

- `demo_data/ingest/generic_case_control.cnvs.merged.json`

Accepted raw shapes:

- object keyed by region string, where each value is a CNV object
- list of CNV objects

Observed demo object shape:

```json
{
  "17:42337980-42338541": {
    "callers": ["manta"],
    "ratio": -1.0,
    "size": 561,
    "PR": "350,73",
    "SR": "314,52",
    "chr": "17",
    "start": 42337980,
    "end": 42338541,
    "genes": [{"gene": "BRCA1"}],
    "nprobes": 0,
    "NORMAL": false
  }
}
```

Parser behavior:

- object values are converted into a list of CNV rows
- `_pipeline_key` is added when the source was a keyed object
- `callers` is normalized to `list[str]`
- `nprobes` is normalized to `int`
- `ratio` is normalized to `float | null`
- if `type` is missing, it is inferred from ratio:
  - `AMP` when ratio `> 1`
  - `DUP` when ratio `> 0`
  - `DEL` when ratio `< 0`

Recommended raw fields:

- `chr`
- `start`
- `end`
- `size`
- `ratio`
- `genes`
- `callers`

### Coverage JSON

Primary demo file:

- `demo_data/ingest/generic_case_control.cov.json`

Observed demo shape:

```json
{
  "genes": {
    "UBA1": {
      "covered_by_panel": true,
      "transcript": {"chr": "X", "start": 100, "end": 200, "transcript_id": "synthetic"},
      "exons": {"1": {"chr": "X", "start": 100, "end": 200, "cov": 120}},
      "CDS": {},
      "probes": {}
    }
  }
}
```

Parser behavior:

- coverage JSON is not transformed by the DNA parser
- the raw JSON document is loaded and then validated at write time against the `panel_coverage` contract

Recommended raw structure:

- top-level `genes` object
- one entry per gene
- each gene entry requires `covered_by_panel` and `transcript`; the region maps are optional:
  - `covered_by_panel`
  - `transcript`
  - `exons`
  - `CDS`
  - `probes`

### Biomarkers JSON

Manifest key:

- `biomarkers`

Parser behavior:

- the file is loaded as JSON and passed through without custom parser normalization
- contract validation happens later when writing to the target collection

### DNA Translocations VCF

Manifest key:

- `transloc`

Expected characteristics:

- VCF readable by `pysam.VariantFile`
- `INFO/ANN` annotations present
- fusion-style annotations must include `gene_fusion` or `bidirectional_gene_fusion`

Parser behavior:

- ALT values containing symbolic `<...>` alleles are skipped
- only gene-fusion style records are retained
- this parser does not read a MANE summary file or currently resolve `MANE_ANN`

Stored translocation documents use one object-shaped `INFO` field. `INFO.ANN`
contains all retained fusion annotations and `INFO.MANE_ANN` contains the selected
annotation when one is available. Gene names, consequence/type, HGVS values, panel
membership, and structural-event metadata shown in the UI are read from this
object. This is also the contract used by report rendering and CSV export.

## RNA Raw Input Files

The RNA parser reads file paths from these manifest keys:

- `fusion_files`
- `expression_path`
- `classification_path`
- `qc`
- `pgx`

The RNA parser validates each declared file, loads the JSON payload, normalizes
sparse caller fields to the canonical collection contract, attaches the parent
sample identifier, and validates every document before it is committed. A
declared RNA file that cannot be parsed or normalized fails the complete sample
bundle; the sample is not published as ready.

### Fusions JSON

Fixture used by the RNA demo manifest:

- `demo_data/collections/all_collections_dummy/fusions.json`

Observed fixture shape:

```json
[
  {
    "SAMPLE_ID": "sample_oid_seed",
    "gene1": "BCR",
    "gene2": "ABL1",
    "genes": "BCR-ABL1",
    "calls": [
      {
        "selected": 1,
        "caller": "arriba",
        "spanpairs": 20,
        "spanreads": 42,
        "longestanchor": 30,
        "breakpoint1": "22:23632600",
        "breakpoint2": "9:133589000",
        "effect": "gene_fusion",
        "desc": "Demo fusion call"
      }
    ]
  }
]
```

Recommended raw structure:

- list of fusion documents
- each document should include:
  - `gene1`
  - `gene2`
  - `genes`
  - `calls`
- each `calls[]` entry should carry caller-specific evidence and breakpoint fields

Note:

- `SAMPLE_ID` in raw files is overwritten or reattached at ingest time, so the sample-linking source of truth is the parent sample being ingested.
- Every fusion must contain exactly one call with `selected: 1`. Alternative
  calls may omit `selected`; ingest stores those values as `0`. The selected
  state identifies the caller observation displayed, classified, and reported.
- `calls[].effect` is caller-authored fusion frame or breakpoint-region context.
  The exact normalized value `in-frame` is presented as in-frame; every other
  non-empty value, including `out-of-frame` and `UTR/CDS(truncated)`, is
  presented as out-of-frame. It is not a DNA VEP `Consequence` value.
- `calls[].desc` is a comma-delimited, caller-controlled evidence vocabulary.
  Values such as `oncogene`, `cancer`, `reciprocal`, and caller-specific codes
  are retained verbatim. Coyote3 does not discard unknown future tags. The UI
  distinguishes curated/cancer-reference tags, cautionary context, and
  artifact-associated tags using the historical FusionCatcher vocabulary, but
  those visual groups are review aids rather than clinical classifications.
- Fusion description colors are driven by
  `api/config/center/clinical_vocabulary.toml`. Important cancer/reference
  terms are green, artifact or normal-tissue terms are red, contextual terms
  are gray, and unknown future caller terms remain visible with the neutral
  style.
- All caller alternatives remain in the same `fusions.calls` array. They are not
  written to `anno_vep`, because they are independent caller observations rather
  than alternate VEP transcript consequences. A reviewer may change the selected
  call on the fusion detail page; that operation clears the previous selection
  and marks exactly one call as selected.

Fusion eligibility and fusion presentation are intentionally separate. The
query admits a fusion when one individual call satisfies all configured caller,
effect, evidence, and read-support predicates. The table and report then present
the call marked `selected`. This preserves alternative caller observations
without allowing support from one call and effect from another to satisfy a
single filter expression.

### RNA Expression JSON

Fixture:

- `demo_data/ingest/generic_rna_expression.json`

Observed fixture shape:

```json
  {
    "expression_version": "1.0.0",
    "sample": [],
    "reference": []
  }
```

Recommended raw structure:

- one expression object (not the array wrapper used by collection seed exports)
- each document usually includes:
  - `expression_version`
  - `sample`
  - `reference`

### RNA Classification JSON

Fixture:

- `demo_data/ingest/generic_rna_classification.json`

Observed fixture shape:

```json
  {
    "classifier_version": "1.0.0",
    "classifier_results": [
      {"class": "DEMO_CLASS", "score": 0.98, "true": 98, "total": 100}
    ]
  }
```

Recommended raw structure:

- one classification object
- each document usually includes:
  - `classifier_version`
  - `classifier_results`

### RNA QC JSON

Fixture:

- `demo_data/ingest/generic_rna_qc.json`

Observed fixture shape:

```json
  {
    "sample_id": "seed_sample",
    "tot_reads": 1000000,
    "mapped_pct": 95.0,
    "multimap_pct": 3.0,
    "mismatch_pct": 0.5,
    "canon_splice": 12000,
    "non_canon_splice": 200,
    "splice_ratio": 60,
    "genebody_cov": [100, 102, 99],
    "genebody_cov_slope": -0.5,
    "provider_genotypes": {},
    "provider_called_genotypes": 0,
    "flendist": 150
  }
```

Recommended raw structure:

- one QC object
- each document usually includes:
  - read totals
  - mapped / multimap / mismatch percentages
  - splice metrics
  - any other pipeline QC fields expected by the `rna_qc` collection contract

## What Ingest Normalizes vs What It Passes Through

### Explicitly normalized by the parser

- DNA VCF records
- DNA CNV JSON rows
- DNA translocation VCF records

### Loaded mostly as-is, then validated later

- DNA coverage JSON
- DNA biomarkers JSON
- RNA fusion JSON
- RNA expression JSON
- RNA classification JSON
- RNA QC JSON

## Practical Guidance For New Input Producers

If you are building or updating an upstream pipeline:

1. Make the manifest match `SamplesDoc` and the correct omics layer.
2. Keep file paths readable from the API runtime environment.
3. Use the demo fixtures as shape references for raw files.
4. For DNA VCFs, ensure VEP `CSQ`, `variant_callers`, and per-sample `GT/DP/VAF/VD` are present.
5. For JSON payloads, shape them close to the target collection contracts even if the parser mostly passes them through.

## Field-by-field input and storage walkthroughs

The examples below are synthetic. JSON examples are complete input shapes;
VCF record examples illustrate a row and require matching VCF header declarations.
Keys are case-sensitive. A blank field is not automatically a measured zero.
Validation can reject an entire bundle before commit. `SAMPLE_ID` is assigned by
ingest from the parent sample's MongoDB ID, and must not be supplied as a sample
name by a producer. Producer `_id` values are not an identity contract.

These tables cover the fields read or normalized by sample-file ingestion.
VCF header-defined extension fields and permissive JSON collection extensions
can carry additional pipeline data; ingest does not assign a clinical meaning to
every possible extension. The linked collection contracts list the typed storage
fields, defaults, and constraints. Arbitrary extension fields are not a substitute
for the fields listed here.

### Small-variant VCF: record, genotype, and transcript sections

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

### CNV JSON: one interval row

```json
[
  {"chr":"1","start":10000,"end":20000,"size":10000,
   "ratio":-0.6,"type":"loss","nprobes":12,
   "genes":[{"gene":"GENE1","class":"coding","cnv_type":"loss"}],
   "callers":["cnvkit"]}
]
```

| Key | Description | Storage/normalization |
| --- | --- | --- |
| `chr` | Chromosome string | `cnvs.chr` |
| `start` | Interval start supplied by producer | `cnvs.start`; no coordinate conversion is performed |
| `end` | Interval end supplied by producer | `cnvs.end` |
| `size` | Producer-supplied interval size | `cnvs.size`; supply it explicitly |
| `ratio` | Numeric copy-number ratio or supported event label | Float/null; `DEL`/`LOSS` → -1, `AMP` → 1, `DUP`/`GAIN` → 0.5 |
| `type` | Event type | Preserved when provided; inferred from normalized ratio when absent |
| `nprobes` | Probe count | Integer; missing value normalizes to 0, which is a parser default rather than measured evidence |
| `genes` | Affected-gene objects | `cnvs.genes[]`; absent → empty list |
| `genes[].gene` | Gene name | Stored gene identifier |
| `genes[].class` | Producer gene class | Stored as supplied |
| `genes[].cnv_type` | Per-gene event type | Stored as supplied |
| `callers` | Calling tools | List, or comma/pipe/semicolon-delimited text; normalized to lowercase list |

An alternative root is an object keyed by interval ID. Each value becomes one
row and receives `_pipeline_key` from its object key when not already supplied.

### Coverage JSON: one gene with transcript and regions

```json
{"genes":{"GENE1":{"covered_by_panel":true,
  "transcript":{"chr":"1","start":10000,"end":20000,"transcript_id":"ENST000001"},
  "exons":{"1":{"chr":"1","start":10000,"end":10100,"nbr":1,"cov":120.5}},
  "CDS":{"1":{"chr":"1","start":10020,"end":10100,"nbr":1,"cov":118.0}},
  "probes":{"p1":{"chr":"1","start":10000,"end":10050,"cov":null}}
}}}
```

| Key | Description | Stored mapping |
| --- | --- | --- |
| `genes` | Object keyed by gene name | `panel_coverage.genes` |
| `genes.<gene>.covered_by_panel` | Panel-membership boolean | Same nested field |
| `transcript.chr`, `transcript.start`, `transcript.end` | Transcript interval | Same keys below the gene; producer coordinates preserved |
| `transcript.transcript_id` | Transcript identifier | Same nested field |
| `exons`, `CDS`, `probes` | Objects keyed by producer region ID | Same nested region maps; omitted maps default to empty objects |
| Region `chr`, `start`, `end` | Genomic interval | Required for each supplied region |
| Exon/CDS `nbr` | Optional region number | Integer or null |
| Region `cov` | Optional measured coverage | Number or null; missing does not become zero |
| `sample` | Parent display name | Overwritten by ingest with the parent sample name |
| `SAMPLE_ID` | Parent database identity | Injected by ingest |

### Biomarkers JSON: MSI and HRD sections

```json
{"name":"SYNTHETIC-T",
 "MSIS":{"tot":100,"som":4,"per":4.0},
 "MSIP":{"tot":200,"som":6,"per":3.0},
 "HRD":{"tai":2,"hrd":3,"lst":4,"sum":9}}
```

| Key | Description and mapping to `biomarkers` |
| --- | --- |
| `name` | Required producer sample label; separate from injected `SAMPLE_ID` |
| `MSIS`, `MSIP` | Optional MSI measurement objects; preserve these exact source labels |
| `MSIS.tot`, `MSIP.tot` | Total evaluated count, integer |
| `MSIS.som`, `MSIP.som` | Producer-reported somatic/unstable count, integer |
| `MSIS.per`, `MSIP.per` | Producer-reported percentage, number; not recomputed from counts |
| `HRD.tai` | Producer TAI score/count |
| `HRD.hrd` | Producer HRD component |
| `HRD.lst` | Producer LST component |
| `HRD.sum` | Producer aggregate; validated against the HRD contract |

Omit unavailable measurement objects. Do not invent zeros to satisfy a schema.

### Translocation VCF: breakend and ANN sections

Illustrative annotation-bearing breakend record (real columns are tab-separated):

```text
#CHROM POS ID REF ALT QUAL FILTER INFO FORMAT SYNTHETIC-T
1 10001 bnd1 A A]2:20001] 60 PASS SOMATIC;SVTYPE=BND;ANN=A|gene_fusion|HIGH|GENE1&GENE2|ENSG000001&ENSG000002|transcript|ENST000001&ENST000002|protein_coding||t(1;2)|p.? GT:PR:SR:UR 0/1:10,5:8,3:3
```

The ANN header must define the same order using SnpEff's ` | ` field-name
separators. For the excerpt this is `Allele | Annotation | Annotation_Impact |
Gene_Name | Gene_ID | Feature_Type | Feature_ID | Transcript_BioType | Rank |
HGVS.c | HGVS.p`. Header-declared extra fields remain possible.

| Key | Description | Mapping to `translocations` |
| --- | --- | --- |
| Standard VCF columns | Contig, position, alleles, source ID, quality | Same top-level fields; FILTER and FORMAT become lists |
| `INFO.SVTYPE` | Structural event type | Same nested key |
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

`INFO.MANE_ANN` is not selected by the current file parser because its MANE map
is empty. Symbolic ALT values containing `<` are skipped. Do not submit a generic
unannotated SV VCF and assume every structural variant will become a translocation.

### RNA fusion JSON: caller evidence keys

Use the complete example in [Fusions JSON](#fusions-json). Each root array item
becomes one `fusions` document; alternative calls stay in its `calls[]` array.

| Key | Description and storage |
| --- | --- |
| `gene1`, `gene2` | Required fusion-partner names, stored at the root |
| `genes` | Required combined producer label, for example `BCR-ABL1` |
| `calls` | Nonempty array of independent caller observations |
| `calls[].caller` | Calling tool name, not the annotator version |
| `calls[].breakpoint1`, `calls[].breakpoint2` | Breakpoint strings retained as provided |
| `calls[].spanpairs` | Spanning-pair count, integer |
| `calls[].spanreads` | Spanning-read count, integer |
| `calls[].longestanchor` | Anchor length; integer or string accepted |
| `calls[].selected` | Exactly one call must be 1; omitted values become 0 |
| `calls[].effect` | Caller-authored frame/region description; omitted → empty text |
| `calls[].desc` | Caller evidence tags as text; omitted → empty text |
| `calls[].commonreads` | Common-read count; omitted → 0 |

### RNA expression JSON: sample and reference rows

```json
{"expression_version":"1.0.0",
 "sample":[{"hgnc_symbol":"GENE1","ensembl_gene_id":"ENSG000001",
 "sample_expression":12.0,"reference_sd":2.0,"reference_mean":10.0,
 "reference_median":9.5,"reference_mean_mod":10.0,"sample_mod":12.0,"z":1.0}],
 "reference":[{"hgnc_symbol":"GENE1","ensembl_gene_id":"ENSG000001",
 "reference_sd":2.0,"reference_mean":10.0,"reference_median":9.5,
 "quant_values":{"reference_a":9.0,"reference_b":11.0}}]}
```

| Key | Description and mapping to `rna_expression` |
| --- | --- |
| `expression_version` | Required producer format/analysis version, not VEP version |
| `sample` | Array of sample gene-expression rows |
| `reference` | Array of reference gene-expression rows |
| Row `hgnc_symbol` | Gene symbol |
| Row `ensembl_gene_id` | Ensembl gene identifier |
| Sample `sample_expression` | Producer expression measurement; units follow the upstream pipeline |
| Row `reference_sd` | Reference standard deviation |
| Row `reference_mean` | Reference mean |
| Row `reference_median` | Reference median |
| Sample `reference_mean_mod` | Producer-modified reference mean |
| Sample `sample_mod` | Producer-modified sample expression |
| Sample `z` | Producer z-score; ingest does not recompute it |
| Reference `quant_values` | Map of reference labels to numeric values |
| Other reference-row keys | Collected into `quant_values` and converted to float; matching top-level values override explicit map entries |

### RNA classification JSON: one score row

```json
{"classifier_version":"1.0.0",
 "classifier_results":[{"class":"SYNTHETIC_CLASS","score":0.98,"true":98,"total":100}]}
```

| Key | Description and mapping to `rna_classification` |
| --- | --- |
| `classifier_version` | Required classifier version |
| `classifier_results` | Array of result rows |
| Row `class` | Class label; Pydantic internal alias is `class_`, persisted key is `class` |
| Row `score` | Numeric producer score; no reclassification during ingest |
| Row `true` | Integer supporting count |
| Row `total` | Integer total count; `true` cannot exceed `total` |

### RNA QC JSON: every metric

Use the complete object in [RNA QC JSON](#rna-qc-json). One file becomes one
`rna_qc` document. All these fields are required; keys are stored unchanged.

| Key | Type | Meaning |
| --- | --- | --- |
| `sample_id` | string | Producer sample label; distinct from ingest-injected `SAMPLE_ID` |
| `tot_reads` | integer | Total reads |
| `mapped_pct` | number | Mapped percentage, 0–100 |
| `multimap_pct` | number | Multimapped percentage, 0–100 |
| `mismatch_pct` | number | Mismatch percentage, 0–100 |
| `canon_splice` | integer | Canonical splice count |
| `non_canon_splice` | integer | Noncanonical splice count |
| `splice_ratio` | integer | Producer splice ratio; current contract requires integer |
| `genebody_cov` | integer array | Ordered gene-body coverage measurements |
| `genebody_cov_slope` | number | Producer gene-body coverage slope |
| `provider_genotypes` | string-to-string map | Producer genotype labels |
| `provider_called_genotypes` | integer | Number of called provider genotypes |
| `flendist` | integer | Producer fragment-length metric |

### PGX and non-row resources

```json
{"pipeline_version":"synthetic-1","records":[{"gene":"GENE1","result":"example"}]}
```

PGX object keys are preserved without defining gene/drug interpretation semantics.
A root array is wrapped as `{"records": [...]}`. The resulting object is stored
in `pgx` with injected `SAMPLE_ID`; each arbitrary record is not a separate MongoDB
document. The example keys are illustrative extensions, not mandatory PGX fields.

`cnvprofile` is an image path, not a parsed evidence row. It is registered in
`samples.files.cnvprofile`. BAM/CRAM and index names are alignment resources for
IGV, not variant-ingest inputs; they populate `samples.case` and `samples.control`.
The ingest service does not derive SNVs from alignment files.

## Source and contract references

- [API / Sample YAML Guide](sample_yaml.md)
- [API / Ingestion API](ingestion_api.md)
- [API / Collection Contracts](collection_contracts.md)
