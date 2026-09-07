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
- ASP file policy rejects manifest file keys that are not listed in `assay_specific_panels.expected_files`; declared resources are never silently discarded.
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
| `case_bam`, `control_bam` | BAM path/URL string in YAML | Metadata only; BAM bytes are not read by ingest | `samples.case.bam`, `samples.control.bam` |
| `case_bai`, `control_bai` | BAI path/URL string in YAML | Metadata only; index bytes are not read by ingest | `samples.case.bai`, `samples.control.bai` |

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
| Sample columns | First case, second control for paired input | Column names become `GT[].sample`; order determines SNV case/control role, not name matching |
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
- For paired DNA input, the first sample column is treated as `case` and the second as `control`

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

## Related References

- [API / Sample YAML Guide](sample_yaml.md)
- [API / Ingestion API](ingestion_api.md)
- [API / Collection Contracts](collection_contracts.md)
