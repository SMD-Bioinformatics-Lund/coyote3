# DNA And RNA Workflow Chain

## Why these collections matter

The smooth user experience in Coyote3 depends on two connected data layers:

1. Configuration layer (`asp`, `aspc`, `isgl`, roles, permissions): defines what should be shown and how filtering/reporting should behave.
2. Sample runtime layer (`samples`, `variants`, `cnvs`, `fusions`, coverage, RNA analysis): contains per-sample findings and interpretation state.

If these layers are aligned, users get correct gene scopes, filters, report sections, and stable workflows. If they drift, users see missing findings, wrong filters, or report errors.

## Collection name map (short names to Mongo collections)

- `asp` -> `assay_specific_panels`
- `aspc` -> `asp_configs`
- `isgl` -> `insilico_genelists`
- `samples` -> `samples`
- `variants` -> `variants` (DNA SNVs/indels)
- `cnvs` -> `cnvs` (DNA CNV findings)
- `fusions` -> `fusions` (RNA fusion findings)
- `cov` / panel coverage -> `panel_cov` (and `coverage` where used)

## Core relationship model

### 1) Configuration relationship (admin-defined)

```text
ASPC (asp_configs)
  - key: aspc_id = "<assay>:<environment>"
  - owns runtime behavior: filters defaults, analysis types, report settings, schema
            |
            | uses same assay + assay-group semantics
            v
ASP (assay_specific_panels)
  - key: asp_id (typically same assay id used by sample.assay)
  - owns panel gene universe: covered_genes / germline_genes
            |
            | ISGL docs reference assays[] and assay_groups[]
            v
ISGL (insilico_genelists)
  - key: isgl_id
  - owns selectable curated/adhoc gene subsets for interpretation
```

### 2) Sample runtime relationship (ingest + review)

```text
sample-bundle ingest
  -> create samples document (primary anchor)
  -> write dependents with SAMPLE_ID = samples._id:
       variants, cnvs, panel_cov, fusions, rna_expression, rna_classification, rna_qc, ...

UI/API read path
  sample.assay + sample.profile -> ASPC
  sample.assay                  -> ASP
  sample.filters.genelists[]    -> ISGL ids
  sample._id                    -> variants/cnvs/fusions/... by SAMPLE_ID
```

## How gene scope is computed during review

For DNA/coverage workflows, effective genes are derived as:

1. Start with ASP covered genes (`assay_specific_panels.covered_genes`).
2. Add selected ISGL genes from `sample.filters.genelists[]`.
3. Add adhoc genes from `sample.filters.adhoc_genes`.
4. Apply assay-group behavior:
- most panel assays: use intersection with ASP covered genes
- broad assays (`tumwgs`, `wts`): selected genes can become the active gene scope directly

This is why `asp`, `isgl`, and sample filters must be consistent.

## End-to-end flowchart (ingest to report)

```text
Input files/YAML
  -> /api/v1/internal/ingest/sample-bundle
  -> parse payload + validate contracts
  -> insert sample + dependent collections (atomic/restore-aware)
  -> user opens sample in UI
  -> API resolves ASPC + ASP + ISGL + sample dependents
  -> findings rendered (SNV/CNV/Fusion/Coverage)
  -> user classifies/comments/flags
  -> report generation reads same joined context
  -> report + reported_variants snapshot persisted
```

## Collection-by-collection responsibilities

| Collection | Primary purpose | Key links |
| --- | --- | --- |
| `asp_configs` (`aspc`) | Assay + environment runtime config (`aspc_id=assay:environment`) | Linked by `sample.assay` + `sample.profile` |
| `assay_specific_panels` (`asp`) | Panel metadata and covered gene universe | Linked by `sample.assay` (`asp_id`) |
| `insilico_genelists` (`isgl`) | Curated/adhoc gene lists available per assay/group | Linked by `assays[]`, selected via `sample.filters.genelists[]` |
| `samples` | Source-of-truth sample metadata and user filters | Parent anchor for all per-sample findings |
| `variants` | DNA SNV/indel findings with normalized identity | Linked by `SAMPLE_ID` |
| `cnvs` | DNA CNV findings | Linked by `SAMPLE_ID` |
| `fusions` | RNA fusion findings | Linked by `SAMPLE_ID` |
| `panel_cov` / `coverage` | Coverage data for low coverage and gene-level coverage views | Linked by `SAMPLE_ID` |
| `rna_expression` / `rna_classification` / `rna_qc` | RNA side analysis sections shown with RNA workflows | Linked by `SAMPLE_ID` |
| `reported_variants` | Snapshot rows of report output for traceability and fast report reopen | Linked to sample/report lifecycle |

## Important supporting collections

- `refseq_canonical`: canonical transcript map used during DNA ingest normalization.
- `hgnc_genes`: gene metadata/symbol mapping used by APIs and UI.
- `blacklist`: assay-scoped blacklist enrichment for variant review.
- Optional external knowledge (`civic_*`, `oncokb_*`, `cosmic`, `brcaexchange`, `iarc_tp53`, `vep_metadata`): richer interpretation UX.

## Operational rules for smooth experience

- Keep assay identifiers consistent across `samples.assay`, `asp.asp_id`, `aspc.assay_name`, and `isgl.assays[]`.
- Keep assay-group semantics aligned between ASPC and ASP/ISGL usage.
- Ensure sample `profile` resolves to a valid ASPC environment (`production`, `development`, `test`, `validation`).
- Seed configuration/reference collections before ingesting sample bundles.
- Treat `samples` as the parent record and dependent collections as child records keyed by `SAMPLE_ID`.

## DNA and RNA input artifact recap

DNA artifacts usually include:

- `vcf_files`
- `cnv`
- `cov` or `lowcov`
- optional `biomarkers`
- optional `transloc`

RNA artifacts usually include:

- `fusion_files`
- optional `expression_path`
- optional `classification_path`
- optional `qc`

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
