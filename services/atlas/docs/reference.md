# Reference

## Commands

| Command | Operation |
| --- | --- |
| `coyote-atlas inspect` | Read manifest metadata without reading snapshot contents. |
| `coyote-atlas validate` | Check complete inventory, hashes, contracts and diagram references. |
| `coyote-atlas plan` | Return validated bundle identity and target record counts. |
| `coyote-atlas install --expected-manifest-sha256 SHA256` | Submit that reviewed identity to the configured API. |

The equivalent module entry point is `python -m coyote_atlas.cli`.

## Python API

```python
from coyote_atlas.bundle import ReferenceBundle

bundle = ReferenceBundle.packaged()
plan = bundle.plan()
records = bundle.load_documents()
diagrams = bundle.load_diagrams()
```

`load_documents()` returns fresh `hgnc_genes` and `vep_metadata` lists; it does
not stamp records or write them. `load_diagrams()` returns validated binary
documents for `vep_diagrams`. `plan()` identifies the checked manifest and records.

## Dataset identity

`data/reference/manifest.json` records bundle version independently of package
version and identifies dataset content by SHA-256. The retained gene snapshot
contains 44,084 records. Its original upstream release and acquisition date are
not recorded, so Atlas does not assign an invented upstream date.

The VEP snapshot contains 19 releases, 98 through 116, with three distinct
diagram assets. Source URLs and hashes are retained in
`vep_metadata.sources.json`; the original release 103 exception is explained
in the reference notice. Dataset versions identify the exact compressed bytes.

## Host integration

The `coyote.reference_bundles` entry point `atlas` calls
`coyote_atlas.bundle:ReferenceBundle.packaged`. The `coyote.api.routers` entry
point `atlas` calls `coyote_atlas.api:routers`.

| Endpoint | Result |
| --- | --- |
| `GET /api/v1/admin/references/plan` | `plan` with manifest/dataset identities and `pending` logical collections. |
| `POST /api/v1/admin/references/apply` | Per-collection statuses and the validated `plan`. |

Apply accepts only `expected_manifest_sha256` and optional `force`. It rejects
stale plans with HTTP 409. Client paths, record content and installer identities
are not accepted. The host's administrator policy and mutation audit apply.
