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

## Installation and reference updates

Coyote Atlas owns the bundled HGNC/VEP resources. Fresh installation loads that
bundle into the selected knowledgebase database; existing reference collections
are preserved. Use the [HGNC](../hgnc-gene-installation.md) and
[VEP](../vep-metadata-updates.md) import procedures for reviewed updates.

The application does not relocate collections during startup or redeployment.
Review separately scoped database moves before using the maintained
[knowledgebase relocation procedure](../../deployment/mongodb-setup-and-recovery.md).
