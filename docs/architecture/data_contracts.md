# Data Contracts And Collection Models

## API contracts

Request/response contracts live in `api/contracts/*.py` and are the API
boundary schema. Routers accept and return these models rather than exposing
raw MongoDB documents.

## DB contracts

`api/contracts/schemas/` defines model validation for Mongo collection
documents, grouped by domain:

- `samples.py`
- `dna.py`
- `rna.py`
- `assay.py`
- `governance.py`
- `reference.py`
- `registry.py`

Managed admin UI schemas for core resources are backend-owned and generated from
contract models (not read from DB schema documents):

- `api/contracts/managed_resources.py`
- `api/contracts/managed_ui_schemas.py`

Admin create/edit pages use one canonical contract per resource and render
fields directly from backend-provided schema payloads. The UI does not provide
runtime schema switching.

Design principles:

- collection document shapes are defined in Pydantic contracts;
- write paths validate and normalize before any database write;
- API responses use Pydantic response contracts and JSON-safe serialization;
- nested structures are modeled explicitly (`INFO.selected_CSQ`, `filters`,
  coverage gene trees, and file metadata); full versioned VEP transcripts live
  in `anno_vep` rather than in mutable sample-local variant rows;
- ObjectIds and UTC datetimes are converted at the API boundary;
- missing, false, zero, and not-applicable values remain distinguishable;
- fixtures use plain JSON contract shape without Mongo Extended JSON wrappers.

Sample ingestion contract ownership:

- `api/contracts/schemas/samples.py` defines DNA/RNA ingest file-key groups and source-path keys
- `api/application/ingest/service.py` is the public ingest service and consumes those schema-defined constants directly, with helper modules in the same package handling parsing, dependent writes, and updates
- sample documents persist canonical file path fields from the ingest payload
- dependent writes use registry-owned mappings in `api/contracts/schemas/registry.py`

## Contract Layers

| Layer | Contract responsibility | May contain |
|---|---|---|
| Source manifest | External ingest declaration | Sample identity, assay scope, and source file paths |
| Collection document | Persisted domain state | Normalized sample, finding, result, configuration, and audit fields |
| API request/response | Stable HTTP boundary | JSON-safe, permission-scoped fields |
| Prepared report context | Read-only reporting handoff | Already filtered findings, results, configuration, gene scope, and provenance |
| Saved report snapshot | Immutable clinical history | Report metadata and selected finding identity at sign-out |

Each layer has a different purpose. A source manifest is not stored as an
unvalidated sample document. A raw variant document is not returned as a
report snapshot. A report-text evaluator does not receive repository objects.

## Canonical Sample Contract

`SamplesDoc` enforces:

- a required case and an optional control;
- `sample_no=1` and `paired=false` for tumor-only samples;
- `sample_no=2` and `paired=true` for paired case/control samples;
- different allowed file-key groups for DNA and RNA;
- canonical nested `files` metadata;
- canonical domain filter namespaces;
- normalized environment, sequencing scope, platform, VEP version, and
  database-version keys;
- current ASPC identity/version and report-state pointers.

DNA and RNA file keys cannot be mixed in one sample. At least one file from
the selected omics layer must be present.

`database_versions.vep` is the sole sample-level VEP version location. The
sample contract rejects flat `vep_version` and other retired version namespaces,
and database-version input accepts only the documented canonical keys. This
makes later consequence resolution deterministic: every reader uses the same
sample VEP key rather than resolving competing fields.

Sample-bound DNA operations reject a missing VEP version instead of selecting
the newest `vep_metadata` release. Repository methods that intentionally expose
generic metadata without a sample may still request the latest release.

!!! info
    ASP file policy adds stricter runtime requirements. A file can be valid for
    the DNA contract but still be required or disallowed by the selected ASP.

## Configuration Contracts

`AssaySpecificPanelsDoc` defines the physical assay. `AspConfigDoc` defines one
analytical configuration for an ASP, subpanel, and environment.

The ASPC contract validates:

- DNA ASPCs use DNA filters and DNA analysis options;
- RNA ASPCs use RNA filters and RNA analysis options;
- report analyses and report sections are valid for the analyte;
- report paths and required report text are non-empty;
- identifiers and controlled values are normalized.

Configuration rotation preserves historical versions. Samples and reports
retain the exact configuration references needed for reproducibility.

## Prepared Report Context Contract

The reporting application must eventually expose one explicit Pydantic model
for the read-only handoff to report composition. The model includes:

- sample, ASP, and resolved ASPC identity/version;
- enabled analyses and report sections;
- selected and effective gene scope;
- filtered, annotation-enriched reportable findings;
- structured biomarkers, coverage, and available plot artifacts;
- filter snapshot, source counts, and data versions.

This contract is deliberately downstream of query and interpretation services.
A clinical text evaluator consumes it but cannot query collections, choose
transcripts, apply filters, assign tiers, or mutate records.

See
[Clinical data preparation and reporting flow](clinical_data_and_reporting_flow.md)
for the complete producer/consumer protocol.

## Validation flow

- internal ingest normalizes and validates documents via collection contracts in `api/contracts/schemas/registry.py`
- admin create/update for ASP, ASPC, ISGL, users, roles, and permissions validates via collection contracts before DB write
- managed admin resource-to-schema/collection mapping is centralized in `api/contracts/managed_resources.py`
- unsupported collection names fail fast
- invalid shape fails before DB write

## Adding a new collection model

1. Define the source of truth and ownership boundary.
2. Create the Pydantic model.
3. Register it in
   `api/contracts/schemas/registry.py::COLLECTION_MODEL_ADAPTERS`.
4. Define indexes and uniqueness constraints.
5. Add positive, negative, boundary, and missing-value tests.
6. Add a plain JSON fixture.
7. Validate every ingest/admin write before persistence.
8. Add an API response model when the collection is externally readable.
9. Document relationships, units, provenance, and lifecycle.

## Versioning guidance

- Rotate clinically immutable assay configuration rather than rewriting a
  historical release.
- Keep users, roles, and permissions current in place while recording audit
  events and incrementing their version.
- Version reference metadata that changes interpretation, such as VEP
  consequence mappings.
- Evolve contracts intentionally and keep all writes contract-valid.

!!! caution
    A schema version does not by itself make historical output reproducible.
    Saved reports must retain the exact configuration, filters, and finding
    snapshots used at creation time.

## Fixture-driven validation

Use:

- `demo_data/collections/all_collections_dummy`
- `tests/unit/test_db_dummy_fixture.py`
- `scripts/validate_assay_consistency.py`

to prevent drift between contracts and example documents.
