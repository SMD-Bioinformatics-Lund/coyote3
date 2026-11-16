# Repositories and transactions

Repositories implement the operations requested by core services. They translate
logical selections into MongoDB predicates and convert stored records into
portable values. Routes and clinical services should not access raw collections.

Use `MongoAdapter` when a host needs the application repository registry. Supply
adapter-owned settings with optional logger, cache and operation-observer ports:

```python
from coyote_mongo.config.settings import MongoSettings
from coyote_mongo.runtime_adapter import MongoAdapter

settings = MongoSettings(
    uri="mongodb://mongo:27017/?replicaSet=example-rs",
    primary_database="example_application",
    identity_database="example_identity",
    knowledgebase_database="example_reference",
    bam_database="example_alignments",
    environment="development",
)
adapter = MongoAdapter()
# Once the consuming host has supplied its collection bindings and infrastructure:
# adapter.initialize(settings, logger=logger, cache=cache)
# Close adapter-owned connections during host shutdown with adapter.close().
```

Use the [configuration guide](configuration.md) for supported inputs. Alternatively,
compose the required repositories and connection handles explicitly. Pass
`context=settings.audit` to transactional helper repositories such as
`DemoInstallationRepository`; repository operations never discover deployment
identity from environment variables.

Transactions use the client owning the affected database. The adapter's
`run_transaction` helper runs a retryable callback with snapshot read concern
and majority, journaled writes. Retried callbacks must not send messages or
change files.

Business mutations and audit-outbox records commit together in the owning
database. Delivery to a separate audit database is idempotent and recoverable;
it is not a distributed transaction across independent clients.

Report files have a separate lifecycle from database writes. Retain pending
artifact states, recorded digests and recovery behavior instead of assuming
filesystem writes become atomic with MongoDB commits.

Index inspection and index creation are separate operations. Hosts should invoke
the appropriate operation explicitly rather than changing indexes merely by
importing the package.
