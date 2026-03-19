# DNA And RNA Workflow Chain

## Ingestion to report flow

```text
Input files/YAML -> Internal ingest endpoint -> Mongo collections -> API service logic -> UI rendering -> report generation
```

## DNA data chain

Input artifacts usually include:

- `vcf_files`
- `cnv`
- `cov` or `lowcov`
- optional `biomarkers`
- optional `transloc`

Ingestion service:

- `api/services/internal_ingest_service.py`

Core processing:

- variant normalization and identity fields
- CSQ selection and transcript shaping
- per-sample dependent inserts (`variants`, `cnvs`, `panel_cov`, etc)

## RNA data chain

Input artifacts usually include:

- `fusion_files`
- optional `expression_path`
- optional `classification_path`
- optional `qc`

Dependent collections:

- `fusions`
- `rna_expression`
- `rna_classification`
- `rna_qc`

## Atomicity and safety

- Sample-bundle ingest creates sample + dependents in a controlled sequence.
- On error, cleanup/restore paths are used to avoid partial state.
- Update mode is explicit and permission-gated.

## Example ingestion payload (YAML)

```yaml
subpanel: "Hem"
name: "DEMO_SAMPLE_001"
case_id: "DEMO_CASE_001"
control_id: "DEMO_CTRL_001"
genome_build: 38
assay: "ASSAY_A"
profile: "production"
vcf_files: "/data/demo.vcf"
cnv: "/data/demo.cnv.json"
cov: "/data/demo.cov.json"
paired: true
```
