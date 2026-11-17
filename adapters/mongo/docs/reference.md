# MongoDB adapter reference

| Module or object | Purpose |
| --- | --- |
| `coyote_mongo.runtime_adapter.MongoAdapter` | Compose the application repository registry |
| `coyote_mongo.config.settings.MongoSettings` | Validate explicit persistence settings without environment loading |
| `coyote_mongo.config.settings.AuditContext` | Carry deployment ownership into transactional audit and artifact operations |
| `coyote_mongo.connections.MongoConnections` | Shared clients and logical database handles |
| `coyote_mongo.config.endpoints` | Endpoint resolution and namespace validation |
| `coyote_mongo.config.collections` | Collection mappings |
| `coyote_mongo.selection.compile_selection` | Compile core selections into provider queries |
| `coyote_mongo.records` | Portable record and storage codecs |
| `coyote_mongo.results` | Project driver results into core operation results |
| `coyote_mongo.transactions.run_transaction` | Execute a retryable transaction on its owning client |
| `coyote_mongo.repositories` | Collection-specific persistence operations |
| `coyote_mongo.resource_integrity.resource_content_hash` | Canonical persisted-resource hashes |

The distribution is `coyote-server`; the adapter's import is `coyote_mongo`.
Its version is the shared server version, not an independent adapter release.
Read method docstrings for selectors, return values and failure behavior.
The adapter preserves existing document and hash contracts; replacing canonical
BSON hashing with ordinary JSON hashing would invalidate recorded provenance.

`coyote_mongo.repositories.resource_reads.MongoResourceReadRepository` implements
the core metadata retrieval port. Its fixed collection mappings compile validated
filters and paired access grants before aggregation and pagination. It supports
only the public resource metadata schema, with bounded related-catalog filtering
and per-query execution limits. It never accepts raw MongoDB expressions.
