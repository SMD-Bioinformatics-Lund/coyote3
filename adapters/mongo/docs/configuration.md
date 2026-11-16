# MongoDB adapter configuration

Construct `coyote_mongo.config.settings.MongoSettings` explicitly. The package does
not load `.env`, inspect process environment variables or import an API host.

Each logical service has a URI and database-name field:

| Service | URI | Database name |
| --- | --- | --- |
| Primary | `uri` | `primary_database` |
| Identity | `identity_uri` | `identity_database` |
| Knowledgebase | `knowledgebase_uri` | `knowledgebase_database` |
| BAM | `bam_uri` | `bam_database` |

A service URI can inherit `uri`; database names remain explicit.
The URI path does not select the logical database. Services cannot select the
same database namespace on the same deployment.

Connections sharing an identical URI reuse a client. Different URIs own separate
clients; a session must never cross those clients.

Connection pool, timeout and concern defaults are declared once in
`src/coyote_mongo/config/defaults.toml`. The supplied configuration overrides them.
Physical collection mappings belong to `config/collections.toml`, while software
operational collection names are declared in `config/operational_collections.py`.

Hosts provide configuration explicitly. Database credentials and URI values do
not belong in the package sources. Transactional workflows require a replica set
or supported sharded deployment.

The Coyote API translates its deployment environment names into this model in
`coyote_api.config.backend`. Another host can construct the same model directly
without those environment-variable names. URI fields are masked in model
representations; the internal connection mapping contains credentials and must
never be logged.

The model also accepts collection bindings, report storage, sample-cache duration
and an environment label. Unknown fields are rejected. Optional logger and cache
ports are passed separately to the adapter. The API runtime is never retained.

`settings.audit` supplies an immutable `AuditContext` with the normalized environment
and credential-free destination routing digest. Transactional audit and report
erasure helpers require this context explicitly. Queue delivery requires an
explicit route; no current-process environment fallback exists. Existing routing
digests and stored queue records keep their meaning.
