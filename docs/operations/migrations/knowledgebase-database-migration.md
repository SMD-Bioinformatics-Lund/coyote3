# Reference database placement

`hgnc_genes` and `vep_metadata` live in the shared `KNOWLEDGEBASE_DB`, reached
through `KNOWLEDGEBASE_MONGO_URI`. They contain gene identity/transcript metadata
and VEP release-specific translations, consequence groups and source database
metadata. Sample `database_versions` and variant `anno_vep` records remain in the
application database. The migration does not rewrite their provenance.

The collection mapping places `hgnc_collection` and `vep_metadata_collection`
under `[knowledgebase]`. Update custom collection maps accordingly. API and
workers need read access; bootstrap, imports and migrations need controlled write
access. Bootstrap accepts `--knowledgebase-mongo-uri` and `--knowledgebase-db`,
or their environment variables. The URI may use a different replica set from
the application. Existing nonempty reference collections are not reseeded.

## Existing deployments

1. Stop API, worker and beat processes and any reference importers across all
   environments sharing the affected reference database. Keep databases running.
2. Export the intended `COYOTE3_MONGO_URI`, `COYOTE3_DB`,
   `KNOWLEDGEBASE_MONGO_URI` and `KNOWLEDGEBASE_DB`. The script does not load a
   private environment file automatically. Use an operator with read, create,
   index, rename and drop privileges on the relevant collections.
3. Run the read-only inspection, then apply with a new backup directory:

```bash
.venv/bin/python scripts/knowledgebase/migrate_reference_database.py
mkdir -p logs/maintenance-backups
.venv/bin/python scripts/knowledgebase/migrate_reference_database.py --apply \
  --backup-dir logs/maintenance-backups/reference-relocation
```

The script verifies that every current named legacy `assay_subpanels` scope has
a current shared definition and assay association. Current registry status and
metadata take precedence over old records. Missing replacements block removal;
run `scripts/upgrade_from_v3/migrate_assay_subpanels.py` first if needed.

Original documents, collection options and indexes are backed up as BSON in a
mode-0700 directory with mode-0600 files. HGNC/VEP documents retain their IDs and
fields. Copying uses staging collections, copies indexes and compares complete
content hashes before dropping either source. Conflicting target data is never
overwritten. Legacy subpanel history remains in the backup after removal.

Cross-deployment copy/rename/drop is not a single transaction. Keep writers
stopped throughout; after interruption, inspect the staging collections and rerun
the dry run before proceeding. Preserve the backup under center retention policy.
When complete, apply the normal index plan and restart the updated services.
Verify reference lookups before reopening clinical workflows.
