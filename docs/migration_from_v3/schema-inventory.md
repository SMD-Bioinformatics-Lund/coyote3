# Full source schema inventory

MongoDB collections can contain multiple historical formats. A first document,
the newest document, or a bounded sample cannot establish the complete source
contract. Conversion requires a full offline inventory of every record in the
version-specific migration scope.

## Scan the complete export

Use an operator-provided consistent BSON snapshot. This command does not connect
to MongoDB and must not be replaced by a live production scan:

```bash
PYTHONPATH=. .venv/bin/python scripts/upgrade_from_v3/audit_source_schema.py \
  --export-dir /secure/migration/export/coyote3 \
  --output /secure/migration/v3-schema-audit
```

Every required collection file is scanned from beginning to end. There is no
record limit, sampling interval, or first-array-element shortcut. Invalid BSON,
missing files, or interruption prevent creation of a completion manifest.
The output directory must be new.

The scan is proportional to the complete export size and includes every nested
array member. Its aggregate statistics are stored in SQLite. Original document
values are not copied into the report; field names can themselves contain private
identifiers, so the audit still belongs in controlled storage outside the repository.

## Inventory contents

| Artifact | Contents |
| --- | --- |
| `schema.sqlite`, table `collections` | Total documents examined per migrated collection, including zero for empty collections |
| Table `paths` | Number of documents containing each nested field or array-item path |
| View `field_presence` | Present and missing document counts for each observed path |
| Table `types` | Occurrence counts for each decoded BSON type at every path; null is separate from missing |
| Table `shapes` | Exact object-key sets and their occurrence counts, including objects inside arrays |
| `manifest.json` | Complete-scan marker, version, source counts/hashes, inventory checksum, and unprofiled export files |

Paths are JSON arrays with tagged components. For example,
`[["field","INFO"],["field","CSQ"],["array"],["field","Feature"]]`
identifies transcript features across all CSQ array entries. A literal field name
containing a dot or brackets remains distinct from a nested path.

Type codes use BSON tags: `0x01` double, `0x02` string, `0x03` document,
`0x04` array, `0x05` binary (with subtype), `0x07` ObjectId,
`0x08` boolean, `0x09` date, `0x0a` null, `0x10` int32,
`0x12` int64, and `0x13` Decimal128. Other decoded BSON types retain their
encoder tag. This profiles the decoded representation consumed by the converters;
it is not a byte-level validator of retired BSON encodings.

Presence counts are per source document. Occurrence counts include repeated
array elements and may exceed the document count. A field absent from an array
element is reflected in that object's key shape; `documents_missing` means that
the path appears nowhere in the source document. Empty arrays are recorded as
arrays and have no child observations. Fields absent from every record cannot
appear in a discovered-field inventory; target-contract validation still checks
required fields.

Open the inventory with a read-only SQLite client. Useful review queries include:

```sql
-- Fields absent from some source documents.
SELECT collection, path, documents_present, documents_missing
FROM field_presence
WHERE documents_missing > 0
ORDER BY collection, path;

-- Paths that carry more than one decoded type.
SELECT collection, path, COUNT(*) AS type_variants
FROM types
GROUP BY collection, path
HAVING COUNT(*) > 1;

-- All object-key variations, including uncommon historical shapes.
SELECT collection, path, fields, occurrences
FROM shapes
ORDER BY collection, path, occurrences;
```

## Review source variations

For each migrated collection:

1. Review every field, type variation, object-key set, null representation, and
   missing-field pattern. Include rare shapes and later array elements.
2. Determine which fields are consumed by the current application, retained only
   as evidence, transformed, or unsupported. Schema acceptance alone does not
   establish that an unknown field has a supported clinical meaning.
3. Reconcile clinical identities, sample links, transcript selections, filters,
   annotations, reports, measurement units, and provenance using original evidence.
4. Add synthetic regression fixtures for newly identified historical shapes and
   verify their expected conversion before approving the mapping.
5. Account for every unprofiled BSON file. Knowledgebases and identity data are
   outside this migration; an unfamiliar clinical collection requires explicit
   scope review and, when needed, an extension to the converter and its tests.

The audit does not automatically certify clinical compatibility or repair source
documents. It does not count as a successful migration rehearsal. The per-record
converter and reference checks remain mandatory after inventory review.

## Bind review to the source snapshot

The audit command prints a `manifest_sha256` digest. Record it in the private
review file alongside the operator and review date:

```json
{
  "schema_audit": {
    "manifest_sha256": "digest-printed-by-the-complete-audit",
    "reviewed_by": "reviewing-operator",
    "reviewed_on": "ISO-8601-review-date",
    "unprofiled_files": {
      "users.bson": "Identity migration is managed separately"
    }
  }
}
```

`unprofiled_files` must account for every file listed in the audit manifest,
not just the example above. Keep field-disposition decisions, reconciliation
evidence, and synthetic test results with the migration review records.

Configuration, annotation, blacklist, and sample commands require
`--schema-audit /secure/migration/v3-schema-audit`. They verify the report
checksum, source version, collection counts/content digest, and recorded review
before building a bundle. An incomplete, altered, unreviewed, or different-snapshot
inventory blocks conversion. A new export requires a new audit and review.

Continue with the [migration procedure](migration-guide.md).

## Documentation lifecycle

This folder contains the version-specific entry guide, schema inventory procedure,
and migration runbook. After the version's migration support is retired, remove
this folder together with its MkDocs navigation block and documentation-index
links. The other version's migration folder remains self-contained.
