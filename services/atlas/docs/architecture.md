# Architecture

Atlas owns reference resources, release metadata and integrity verification.
The core owns HGNC/VEP collection contracts and VEP interpretation policy.
The server owns authorization, installation provenance, target selection and
deployment orchestration. The Mongo adapter owns persistence and reference
publication records.

The base distribution depends on `coyote-core` and the HTTP-only
`coyote-pyclient`. Neither offline verification nor HTTP installation imports
the server or Mongo adapter. The `api` extra supplies `coyote-server` for the
optional route factory, whose host imports occur only when that factory is loaded.

`ReferenceBundle` reads a checked manifest and validates snapshots using core
models. It returns fresh decoded records without changing their values. The
host applies its existing installation stamps and normalization before storage.
Binary diagrams use the existing content-addressed core contract.

Application assay groups, query-rule publications and clinical query seeds remain
server installation resources. RBAC catalogs and VEP interpretation policy remain
core resources. Atlas does not claim ownership of either category.

Installation proceeds from a reviewed manifest digest to administrator
authorization, host collection checks, existing installation behavior, then
installation results and audit/publication evidence. Resource integrity detects
changed bytes; it is not a cryptographic signature or evidence of clinical approval.
