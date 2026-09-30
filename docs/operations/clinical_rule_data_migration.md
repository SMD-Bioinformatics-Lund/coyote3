# Clinical-Rule Data Maintenance

These procedures apply only to databases containing the specified obsolete fields
or revision serialization defect. New deployments using current seed data do not
need these migrations. They are not part of routine rule authoring or publication.

Use [clinical reporting rules](../product/clinical_reporting_rules.md) for the
current document model and approval workflow. Back up the target database and
follow each procedure's preflight checks and write restrictions.

## Deploying report policy configuration

`scripts/migrate_reporting_policy.py` reads the configured application database.
Supply `COYOTE3_MONGO_URI` and `COYOTE3_DB` through the deployment environment; it
does not load a private environment file implicitly or print credentials.

```bash
# Read-only plan. Use an operator identity for the resulting revisions.
.venv/bin/python scripts/migrate_reporting_policy.py --actor "$USER"

# Explicitly create ASPC revisions and rule drafts in a MongoDB transaction.
.venv/bin/python scripts/migrate_reporting_policy.py --actor "$USER" --apply
```

The migration creates new versions of active ASPCs missing a tier policy. SNVs
retain tiers 1 and 2 for the former `gmsonco` policy, otherwise 1 through 3; RNA
fusions retain tiers 1 through 3. Explicit policies, including empty selections,
are not overwritten. Superseded ASPCs remain as inactive history.

For each applicable published rule set, the script creates a draft with the
existing content and ordinary metadata blocks reproducing the former question and
header decisions. It uses canonical `sample.paired` and `sample.subpanel_id` facts.
Solid Base has no named clinical question. Existing embedded test assertions are
retained and extended with metadata expectations. Drafts receive immutable revision
snapshots; published source documents are unchanged.

An existing open draft/review version is counted as `open_rule_drafts` and is not
overwritten. Resolve those versions in the builder, adding the required metadata
blocks there or closing the draft before rerunning the script. Reruns do not
duplicate open migration drafts. The script does not approve or publish content.

Before enabling report generation after deployment, review tier selections, test
each draft with paired/unpaired and Base/named-subpanel cases where applicable,
then obtain independent approval and publish. Keep report generation paused during
this rollout: the renderer has no hardcoded text fallback, and unconverted releases
produce no metadata text. Scope identities do not need to change.
Annotations, samples and saved reports are not modified by the migration.

## Deploying Scope-Based Selection

Pause application/configuration writers, back up the application database, and run
the migration before starting the updated application. Export its
`COYOTE3_MONGO_URI` and `COYOTE3_DB` without placing credentials on the command line:

```bash
.venv/bin/python scripts/migrate_reporting_rule_resolution.py
.venv/bin/python scripts/migrate_reporting_rule_resolution.py --apply
```

The first command is read-only. The second replaces obsolete
`reporting.clinical_rule_set_id` fields with languages derived from their referenced
rules, across ASPC revisions and editable assay setup drafts, then installs the scope
uniqueness index. Unknown references, conflicting languages and duplicate published
scopes stop preflight. Return pending assay setups to draft first. Configuration
updates use a transaction and optimistic checks; index creation follows the commit,
so keep writers stopped until the command completes successfully.
Center overrides of `required_aspc_fields` must replace `clinical_rule_set_id` with
`language`; the application template already uses the current key.

Samples and saved reports are never rewritten. Embedded test facts no longer accept
`clinical_rule_set_id`. The migration removes that field from rule documents and
revision snapshots, derives the reporting language, and rebuilds affected content
hashes and revision chains together. It verifies the original revision checksums
and chains first and refuses to rewrite history referenced by saved reports.
Checksum failures require investigation; rerunning is not a way to repair them.

Preflight also checks active ASPCs with report sections against the selected
published release, its content hash and declared analyses. It reports configurations
whose selected rule identity changes. Review those changes before applying:
an exact subpanel release takes precedence even when the old binding selected Base.
The command is idempotent after a successful migration.

## Repairing Draft Revision Checksums

`scripts/repair_clinical_rule_revision_hashes.py` repairs one specific serialization
failure: a draft update hashed `content_hash: null` before omitting that null field
from its stored snapshot. The repair reconstructs that exact input and requires
its digest to match the original. Unknown checksum failures, broken chains and
references from saved reports stop the operation without writes.

With `COYOTE3_MONGO_URI` and `COYOTE3_DB` set explicitly, first run:

```bash
.venv/bin/python scripts/repair_clinical_rule_revision_hashes.py
```

Before applying, stop rule writers and back up the application database. Supply a
new file in a protected backup directory:

```bash
.venv/bin/python scripts/repair_clinical_rule_revision_hashes.py \
  --apply --backup-file /secure-backups/clinical-rule-revisions.bson
```

The command writes original affected revisions to an exclusive BSON file with
owner-only permissions before replacing snapshots transactionally. It rebuilds
downstream links without changing rule text or lifecycle metadata. Keep the backup
outside Git and public storage. Rerun the dry run to confirm zero replacements,
then run the scope-selection migration above and restart writers with the corrected
application code. The runtime verifier does not accept the faulty serialization.

## Removing obsolete engine-version fields

Unreleased development definitions may contain the obsolete
`minimum_engine_version` field. Strict import validation rejects that field; remove it
from exported authoring JSON before importing. For a database containing such records,
do not simply unset the field: it contributes to content and revision hashes.

Before starting the updated application, stop application writers, back up the
development database, and run the dedicated migration using an explicitly configured
`COYOTE3_MONGO_URI` and `COYOTE3_DB`:

```bash
.venv/bin/python scripts/remove_clinical_engine_version.py
.venv/bin/python scripts/remove_clinical_engine_version.py --apply
```

The first command only plans changes. The second atomically removes the obsolete field
and rebuilds affected content hashes and revision chains after checking their original
integrity. It preserves rule identities, content versions, revisions and workflow state.
The migration refuses to change any database containing saved reports; it is only for
unreleased development data, not a way to rewrite issued-report provenance. Revalidate
development rules and restart any pending review that relied on the previous hashes.
