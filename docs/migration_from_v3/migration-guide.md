# Coyote v3 migration commands

The [clinical data migration procedure](../operations/migrations/clinical-data.md)
is the authoritative execution sequence for both source versions. Set
`SOURCE_VERSION=3` and select one supported lowercase assay ID at a time.

Use `migrations_scripts/v3/migrate_samples.py`, `migrate_variants.py` and
`migrate_related.py`. Do not use the removed scripts-directory converters.
The procedure covers reference prerequisites, 500-sample exports, source-bound
review, Bjorn/CDM enrichment, cumulative VEP evidence, related collections and
explicit destination imports. It also identifies shared curation stages that
still need fresh converters.
