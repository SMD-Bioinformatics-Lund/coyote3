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
  -> resolves assay/profile/omics metadata

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
- `demo_data/collections/all_collections_dummy/rna_expression.json`
- `demo_data/collections/all_collections_dummy/rna_classification.json`
- `demo_data/collections/all_collections_dummy/rna_qc.json`

## Manifest Layer

The sample YAML is the top-level ingest manifest.

It is responsible for:

- sample identity such as `name`, `case_id`, `control_id`
- pipeline assay and environment identity such as `assay` and `profile`, mapped
  at ingest to canonical `asp_id` and `environment`
- omics-layer selection through `omics_layer`
- pipeline metadata such as `pipeline` and `pipeline_version`; DNA annotation
  database versions are normally read from the VCF `##VEP=` header
- flat file references such as `vcf_files`, `cnv`, `cov`, and `fusion_files`

Important behavior:

- The manifest is validated first through `SamplesDoc`.
- `omics_layer` controls which file keys are legal.
- ASP file policy rejects manifest file keys that are not listed in `assay_specific_panels.expected_files`; declared resources are never silently discarded.
- Required ASP files must be present and readable before parsing starts.
- Optional expected files may be omitted. If an optional expected file path is present, Coyote3 treats it as declared data and the sample will not be marked ready unless that file is parsed and written successfully.
- If `filters` is missing, ingest may seed `samples.filters` from ASPC defaults.

New manifests should use the nested `files` object documented in
[API / Sample YAML Guide](sample_yaml.md#pipeline-file-declaration-format). Each entry is
stored under `samples.files.<key>` with `path`, optional checksum metadata, and
optional file-size metadata.

See [API / Sample YAML Guide](sample_yaml.md) for the full manifest contract.

## DNA Raw Input Files

The DNA parser reads file paths from these manifest keys:

- `vcf_files`
- `cnv`
- `cnvprofile`
- `cov`
- `biomarkers`
- `transloc`

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
  `INFO.selected_CSQ_criteria` on the sample-local variant row. The complete
  transcript set is stored once in the versioned `anno_vep` collection.
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
- Transcript summaries include provenance fields:
  - `transcript_tags`: HGNC/VEP markers such as `ncbi_mane_plus_clinical`,
    `ensembl_mane_plus_clinical`, `ncbi_mane_select`, `ensembl_mane_select`,
    and `vep_canonical`.
  - `canonical_source`: VEP canonical authority when the source record carries
    `CANONICAL=YES`.
  - `is_canonical`: boolean helper used by the detail-page transcript table.
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

- `demo_data/ingest/generic_case_control.cov.json`

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

The RNA parser currently performs much less structural normalization than the DNA parser. In practice it:

- checks that the file exists
- loads JSON
- passes the loaded object onward
- relies on downstream collection validation during write

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

- `demo_data/collections/all_collections_dummy/rna_expression.json`

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

- `demo_data/collections/all_collections_dummy/rna_classification.json`

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

- `demo_data/collections/all_collections_dummy/rna_qc.json`

Observed fixture shape:

```json
[
  {
    "SAMPLE_ID": "...",
    "sample_id": "seed_sample",
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
