# Shared legacy migration implementation

Version-specific commands live in `../migrate_from_v2/` and `../upgrade_from_v3/`.
These modules share offline indexing, conversion, reconciliation, and target
application. See the [v2 runbook](../../docs/migration_from_v2/migration-guide.md)
and [v3 runbook](../../docs/migration_from_v3/migration-guide.md) for source contracts and execution order.

| Module | Responsibility |
| --- | --- |
| `schema_inventory.py` | Full-export nested field/type/shape inventory and snapshot-bound review checks |
| `offline.py` | BSON inventory, read-only SQLite access, private artifacts, and bundle manifests |
| `conversion.py` | Source-shape conversion with explicit historical evidence and scope |
| `clinical_plan.py` | Related sample, finding, history, snapshot, and VEP reference checks |
| `commands.py` | Version-specific CLI behavior and reviewed TSV backfills |
| `apply_bundle.py` | Guarded local target preflight and transactional bundle application |

Only `apply_bundle.py` opens a MongoDB connection. It has no source connection and
does not read application environment files. Converters consume local BSON-derived
indexes; tests use synthetic fixtures and in-memory database doubles.
