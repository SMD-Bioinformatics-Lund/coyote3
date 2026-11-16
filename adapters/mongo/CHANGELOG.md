# MongoDB adapter changelog

## 1.0.0

- Verify assay-configuration repository defaults, scope and typed rollups against
  the core contract without changing dashboard results.
- Select coyote-core 4.0.0 while retaining the adapter's independent 1.0.0 identity.
- Own repository and adapter/core contract suites with explicit synthetic settings,
  fast record-conversion smoke checks and independent branch coverage.
- Include the separate copyright/affiliation notice in distributions and identify
  first-party source with GPL-3.0-only SPDX headers.
- Remove the unused adapter factory and forwarding module; consumers import
  `MongoAdapter` from its authoritative `runtime_adapter` module.
- Accept validated `MongoSettings` and explicit host ports without retaining the
  API runtime. Require explicit audit context for transactional writes and report
  erasure; remove process-environment reads and implicit queue-routing fallback.
- Extract repositories, query compilation, record codecs and transactions into
  `coyote-mongo`, without an API dependency.
- Own collection/index contracts and connection defaults in this package.
- Retain audit outboxes, revision history, session storage and report persistence.
- Accept host operation-observation callbacks without importing host metrics.
- License this package under GNU GPL version 3 only.
