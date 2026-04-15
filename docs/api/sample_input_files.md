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
  -> validated as a SamplesDoc
  -> points to raw file paths
  -> resolves assay/profile/omics metadata

raw input files
  -> parsed by DnaIngestParser or RnaIngestParser
  -> normalized into collection-shaped payloads
  -> written as sample-linked dependent documents
```

## Demo Fixtures Used Here

These repo fixtures are the best concrete reference for expected input shapes:

- `tests/data/ingest_demo/generic_case_control.yaml`
- `tests/data/ingest_demo/generic_case_control.final.filtered.vcf`
- `tests/data/ingest_demo/generic_case_control.cnvs.merged.json`
- `tests/data/ingest_demo/generic_case_control.cov.json`
- `tests/data/ingest_demo/generic_rna_sample.yaml`
- `tests/fixtures/db_dummy/all_collections_dummy/fusions.json`
- `tests/fixtures/db_dummy/all_collections_dummy/rna_expression.json`
- `tests/fixtures/db_dummy/all_collections_dummy/rna_classification.json`
- `tests/fixtures/db_dummy/all_collections_dummy/rna_qc.json`

## Manifest Layer

The sample YAML is the top-level ingest manifest.

It is responsible for:

- sample identity such as `name`, `case_id`, `control_id`
- assay and environment identity such as `assay` and `profile`
- omics-layer selection through `omics_layer`
- pipeline metadata such as `pipeline`, `pipeline_version`, `vep_version`
- file references such as `vcf_files`, `cnv`, `cov`, `fusion_files`

Important behavior:

- The manifest is validated first through `SamplesDoc`.
- `omics_layer` controls which file keys are legal.
- ASP file policy may ignore manifest file keys that are not listed in `assay_specific_panels.expected_files`.
- If `filters` is missing, ingest may seed `samples.filters` from ASPC defaults.

See [API / Sample YAML Guide](sample_yaml.md) for the full manifest contract.

## DNA Raw Input Files

The DNA parser reads file paths from these manifest keys:

- `vcf_files`
- `cnv`
- `cov`
- `biomarkers`
- `transloc`

### SNV / Indel VCF

Primary demo file:

- `tests/data/ingest_demo/generic_case_control.final.filtered.vcf`

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
- `INFO.CSQ` is reduced into:
  - `INFO.selected_CSQ`
  - `INFO.selected_CSQ_criteria`
  - remaining transcript summaries in `INFO.CSQ`
- Canonical transcript selection prefers:
  1. internal canonical RefSeq mapping
  2. VEP `CANONICAL == YES`
  3. first protein-coding transcript
  4. first transcript fallback
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

- `tests/data/ingest_demo/generic_case_control.cnvs.merged.json`

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
    "genes": [...],
    "nprobes": 0,
    "NORMAL": ...
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

- `tests/data/ingest_demo/generic_case_control.cov.json`

Observed demo shape:

```json
{
  "genes": {
    "UBA1": {
      "covered_by_panel": true,
      "transcript": {...},
      "exons": {...},
      "CDS": {...},
      "probes": {...}
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
- each gene entry may contain:
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
- `MANE_ANN` is added when the MANE summary file can resolve the selected annotation

## RNA Raw Input Files

The RNA parser reads file paths from these manifest keys:

- `fusion_files`
- `expression_path`
- `classification_path`
- `qc`

The RNA parser currently performs much less structural normalization than the DNA parser. In practice it:

- checks that the file exists
- loads JSON
- passes the loaded object onward
- relies on downstream collection validation during write

### Fusions JSON

Fixture used by the RNA demo manifest:

- `tests/fixtures/db_dummy/all_collections_dummy/fusions.json`

Observed fixture shape:

```json
[
  {
    "SAMPLE_ID": "65f0c0ffee00000000000001",
    "gene1": "BCR",
    "gene2": "ABL1",
    "genes": "BCR-ABL1",
    "calls": [
      {
        "selected": 1,
        "caller": "arriba",
        "spanpairs": 20,
        "spanreads": 42,
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

### RNA Expression JSON

Fixture:

- `tests/fixtures/db_dummy/all_collections_dummy/rna_expression.json`

Observed fixture shape:

```json
[
  {
    "SAMPLE_ID": "...",
    "expression_version": "1.0.0",
    "sample": [...],
    "reference": [...]
  }
]
```

Recommended raw structure:

- list of expression documents
- each document usually includes:
  - `expression_version`
  - `sample`
  - `reference`

### RNA Classification JSON

Fixture:

- `tests/fixtures/db_dummy/all_collections_dummy/rna_classification.json`

Observed fixture shape:

```json
[
  {
    "SAMPLE_ID": "...",
    "classifier_version": "1.0.0",
    "classifier_results": [
      {"class": "DEMO_CLASS", "score": 0.98, "true": 98, "total": 100}
    ]
  }
]
```

Recommended raw structure:

- list of classification documents
- each document usually includes:
  - `classifier_version`
  - `classifier_results`

### RNA QC JSON

Fixture:

- `tests/fixtures/db_dummy/all_collections_dummy/rna_qc.json`

Observed fixture shape:

```json
[
  {
    "SAMPLE_ID": "...",
    "sample_id": "DEMO_SAMPLE_001",
    "tot_reads": 1000000,
    "mapped_pct": 95.0,
    "multimap_pct": 3.0,
    "mismatch_pct": 0.5,
    "canon_splice": 12000,
    "non_canon_splice": 200
  }
]
```

Recommended raw structure:

- list of QC documents
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
