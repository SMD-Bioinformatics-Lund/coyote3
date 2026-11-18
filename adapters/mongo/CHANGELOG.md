# MongoDB adapter changelog

## v1.0.0

- Count distinct valid sign-ins and recent activity independently of TTL cleanup,
  excluding missing accounts and sessions invalidated by credential changes.
- Scope finding inventory by serialized sample IDs, matching stored `SAMPLE_ID`
  references. Keep report-snapshot scoping by sample name and exact assay/environment grants.
- Implement the resource retrieval port with safe field projections, scope before
  aggregation, stable pagination, bounded related filters and batched related reads.
- Share structural finding index installation while preserving collection-specific
  indexes, key order and existing index names.
- Record checked source-bundle provenance with reference publication and inspect
  authenticated privileges for isolated demonstration deployments.

- Verify assay-configuration repository defaults, scope and typed rollups against
  the core contract without changing dashboard results.
- Strictly type the assay repository, shared collection operations and transaction
  callbacks; check the concrete implementation against its core protocol.
- Select coyote-core 4.0.0 and share the server's 1.0.0 distribution identity.
- Own repository and adapter/core contract suites with explicit synthetic settings,
  fast record-conversion smoke checks and independent branch coverage.
- Include the separate copyright/affiliation notice in distributions and identify
  first-party source with GPL-3.0-only SPDX headers.
- Remove the unused adapter factory and forwarding module; consumers import
  `MongoAdapter` from its authoritative `runtime_adapter` module.
- Accept validated `MongoSettings` and explicit host ports without retaining the
  API runtime. Require explicit audit context for transactional writes and report
  erasure; remove process-environment reads and implicit queue-routing fallback.
- Keep repositories, query compilation, record codecs and transactions in the
  `coyote_mongo` namespace, with no imports from the API component; distribute
  both components together as `coyote-server`.
- Own collection/index contracts and connection defaults in this package.
- Retain audit outboxes, revision history, session storage and report persistence.
- Accept host operation-observation callbacks without importing host metrics.
- License this package under GNU GPL version 3 only.
