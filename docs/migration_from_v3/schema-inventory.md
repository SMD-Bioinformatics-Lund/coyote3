# Coyote v3 source structure

Run sample `inspect --all-samples` and collection-specific `inspect` commands
from the [execution procedure](../operations/migrations/clinical-data.md).
Inspection records nested keys and BSON types without inferring missing values.

- [Observed source structures](https://github.com/SMD-Bioinformatics-Lund/coyote3/blob/api/migrations_scripts/source-structures.md)
- [Sample scope and field mappings](https://github.com/SMD-Bioinformatics-Lund/coyote3/blob/api/migrations_scripts/README.md)
- [Related collections and coverage classification](https://github.com/SMD-Bioinformatics-Lund/coyote3/blob/api/migrations_scripts/related-data.md)
- [Variants and VEP 103 evidence](https://github.com/SMD-Bioinformatics-Lund/coyote3/blob/api/migrations_scripts/variants.md)
- [Current collection relationships](../reference/collection-dependencies/README.md)

Keep source exports and review artifacts private. The scripts retain specimen
identities and normalize only the documented assay/diagnosis identifiers.
