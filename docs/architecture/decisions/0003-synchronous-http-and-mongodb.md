# ADR 0003: synchronous HTTP handlers and MongoDB execution

**Status:** Accepted
**Date:** 13 August 2026

## Context

Coyote3 uses PyMongo's synchronous client. Most FastAPI route handlers are
declared with `def`, so FastAPI runs them in its managed worker thread pool.
This keeps blocking MongoDB calls away from the asyncio event loop while
preserving the mature repository and transaction APIs used by the clinical
services.

Motor is not an appropriate migration target: its API is being superseded by
PyMongo's native asynchronous API. Converting only repository calls without
converting the complete service call chain would add two execution models and
would not provide a reliable throughput improvement.

## Decision

- Routes that perform synchronous repository work remain synchronous `def`
  handlers.
- Multipart ingest routes are also synchronous handlers because they combine
  file parsing or staging, schema validation, MongoDB writes, and sometimes
  Celery submission. FastAPI therefore runs the complete operation in its
  managed worker thread pool rather than blocking the event loop in several
  smaller sections.
- An `async def` route must not call a synchronous repository directly. It
  must use FastAPI's thread-pool boundary or delegate to an async-native call
  chain.
- MongoDB pool, timeout, read-concern, and write-concern settings are explicit
  deployment controls.
- A future async conversion, if justified by measured production contention,
  will use PyMongo's supported async API and migrate one complete vertical
  workflow at a time.

## Consequences

Concurrency is bounded by API workers, FastAPI's thread pool, and the MongoDB
connection pool. Operators must size these together and verify them using a
representative non-production workload. Application code must not use
`time.sleep()` in request handlers.
