# Migrate from Coyote v2

Use `migrations_scripts/v2/` with exports from `coyote`.

1. Follow the [execution order and commands](../operations/migrations/clinical-data.md).
2. Review the [collection relationships](../reference/collection-dependencies/README.md).
3. Check the [source structure and field mapping](schema-inventory.md).

Source reads are read-only. Preparation writes local Extended JSON; destination
imports are separate operator commands. Preserve original sample ObjectIds and
only prepare related records owned by those selected samples.
