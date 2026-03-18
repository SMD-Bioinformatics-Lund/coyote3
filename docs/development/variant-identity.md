# Variant Identity (`simple_id` + `simple_id_hash`)

## Why this was added
`variants.simple_id` can become very large for long indels and breakend-like alleles. Indexing that full string directly is expensive and can become unreliable for very long values.

To keep lookups fast and stable, the data model now stores both:
- `simple_id`: canonical, human-readable identity string
- `simple_id_hash`: deterministic MD5 hex digest of canonical `simple_id`

## Why MD5
MD5 is used here as a compact deterministic lookup key, not for cryptographic security. It is fast, broadly supported, and produces a fixed 32-char hex value that indexes efficiently.

## Why keep `simple_id`
`simple_id` remains in documents for:
- human readability/debugging
- exact identity verification after hash prefilter
- backward compatibility with existing exports and diagnostics

## Safe lookup pattern
For exact identity matching, query with both fields:

```python
{"simple_id_hash": <md5_hex>, "simple_id": <canonical_simple_id>}
```

This gives hash-index performance while preserving collision safety by verifying `simple_id`.

## Canonical normalization rules
Canonical identity generation uses:
- `CHROM`: strip whitespace, remove `chr` prefix, uppercase (`M`/`MT` -> `MT`)
- `POS`: normalized to integer string when possible
- `REF`/`ALT`: strip whitespace, uppercase
- delimiter: stable `_`

Canonical simple id format:

```text
CHROM_POS_REF_ALT
```

## Backfill
Use the canonical migration script:

```bash
/home/ram/.virtualenvs/coyote3/bin/python scripts/migrate_db_identity.py --mongo-uri mongodb://localhost:37017 --db coyote3_dev
```

Dry-run:

```bash
/home/ram/.virtualenvs/coyote3/bin/python scripts/migrate_db_identity.py --mongo-uri mongodb://localhost:37017 --db coyote3_dev --dry-run
```

Notes:
- the script also migrates non-ObjectId `_id` documents into ObjectId `_id` + business-key fields
- default exclusions protect collections that intentionally use string `_id` (`assay_specific_panels`, `asp_configs`, `insilico_genelists`, `vep_metadata`)
- use `--migrate-all-collections` only for deliberate broad `_id` conversion across additional collections
