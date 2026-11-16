# Synthetic datasets

`coyote_demo.resources.WORKFLOW_BUNDLE` locates the installed workflow resources.
It contains configuration JSON under `setup/`, parser inputs under `raw/`, two
starter manifests and 18 additional selectable manifests. The starter keys are
`first_sample` and `rna_fusion`. Additional keys are manifest basenames.

Manifest file references resolve relative to their own directory and must remain
inside the installed bundle. There are no BAM/BAI files, user credentials or real
patient records in the package. Gene symbols are real vocabulary; the findings,
coordinates and identifiers are synthetic examples.

The installer validates configuration through core contracts and captures assay
and gene-list releases before writing. It uses ordinary ingestion for VCF and
JSON inputs. Its role is to populate a demonstration; it does not replace clinical
validation or the frozen regression expectations of other packages.

`coyote_demo.resources.DEMO_CENTER` locates the separately retained synthetic
center catalog used by configuration examples and consistency checks. Biological
group metadata used to compile the demonstration catalog is an explicit dataset
under `data/assay_groups.seed.ndjson`.
