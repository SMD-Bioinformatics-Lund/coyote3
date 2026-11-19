# Knowledgebase updates

Coyote Atlas owns the source importers for HGNC/BioMart, VEP metadata and diagrams,
BRCA Exchange, CIViC, TP53, COSMIC and ClinPGx. Install the reviewed Atlas package
with its `importers` extra alongside the matching Coyote server wheel. The server
provides collection mappings, persistence and transactional audit support.

```bash
coyote-atlas update --help
coyote-atlas update hgnc --help
coyote-atlas update vep-metadata --help
coyote-atlas update cosmic --help
```

Use an explicit target environment. Source update commands validate before writing;
database publication requires `--apply`, except `clinpgx`, which explicitly imports
the supplied ZIP when invoked. Point each importer at its raw source files using
the parameters listed by `--help`. VEP commands accept `--input-dir` for offline
raw sources; without it they download upstream data even without `--apply`.
HGNC and VEP database updates require a new backup file.

Configure the knowledgebase endpoint and database, plus `ENV_NAME`, `IDENTITY_DB`
and the identity endpoint for audit routing. Data writes retain transactional audit
receipts; namespace swaps and indexes have separate maintenance records. A complete
multi-collection reference release is not one MongoDB transaction.

Source formats, licensing, backups, publication recovery and command options are
maintained in the [Atlas documentation](https://github.com/SMD-Bioinformatics-Lund/coyote-atlas/blob/dev/docs/README.md).

Application bootstrap still installs the reviewed bundled HGNC/VEP resources through
the existing host workflow. Database relocation remains an application operation;
see [knowledgebase database migration](migrations/knowledgebase-database-migration.md).
