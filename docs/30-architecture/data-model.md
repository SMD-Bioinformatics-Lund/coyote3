# Data Model & Collections

The app accesses MongoDB via handler classes under `coyote/db/`. Typical collections include:

- **samples**: cases with `assay`, `subpanel`, paths to VCF/CNV/COV, etc.
- **variants**, **cnvs**, **translocations**, **fusions**: genomic findings linked via `SAMPLE_ID`.
- **asp** (panels) and **asp_configs** (ASPC): schema‑driven assay metadata and defaults.
- **schemas**: master schemas that drive Admin forms (fields, sections, options).
- **roles**, **permissions**, **users**: RBAC.
- **isgl**: in‑silico gene lists per assay.
- **vep_meta**, **hgnc**: annotation metadata.

> See `coyote/db/mongo.py` where `MongoAdapter` wires handler attributes like `self.variant_handler`, `self.aspc_handler`, etc.
