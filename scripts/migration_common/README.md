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
| `prepare_target.py`, `target_catalog.py` | Read-only validation and fingerprinting of preinstalled target configuration |
| `run_report.py` | Private JSON and Markdown evidence for completed or blocked migration runs |

Only target preflight and bundle application open MongoDB connections. Neither has
a source connection or reads application environment files. Converters consume local
BSON-derived indexes; tests use synthetic fixtures and in-memory database doubles.

## Clinical field mappings

These mappings apply to both source versions. Version-specific collection names
and required inputs remain in their respective runbooks. Converters preserve
original BSON identities; applying a bundle does not generate replacement IDs.

| Source field | Validated bundle | Target persistence |
| --- | --- | --- |
| `samples.comments[]` | `sample_comments` with the owning sample identity/name | Separate documents retaining comment identity, author, text, dates and hiding metadata |
| `samples.reports[]` | `reports` with owning sample and reviewed assay/diagnosis/environment scope | Original report identities, numbers, authors, dates and file references |
| Finding `comments[]` | `finding_comments` with sample and finding ownership | Separate comments retaining the original history |
| `SAMPLE_ID`; snapshot `sample_oid` | Original sample relationship | Never inferred from a similarly named case |
| Sample `profile` | `environment` | Reviewed target configuration must agree |
| Sample/annotation `subpanel` | `diagnosis_id` | Conflicting or absent required scope needs reviewed reconciliation |
| Sample `case.id` / `control.id` | Missing `case_id` / `control_id` | Existing conflicting values are not silently replaced |
| Sample case/control `sequencing_run`, `reads` | Same nested fields | Preserve recorded values; no guessed runs or zero-filled counts |
| Top-level registered file paths | `files.<key>.path` | Multiple paths require explicit file reconciliation |
| Annotation `assay` | `asp_group` | Requires an installed target group; null scope needs a digest-bound mapping |
| Annotation `nomenclature`, `variant` | Corresponding `hgvsp`, `hgvsc` or `genomic` identity | Classification/text, authorship and creation time are preserved |
| Blacklist `assay` | `assay_group` | The destination adapter writes the existing repository field `assay` |
| Blacklist `_id`, `pos`, `in_normal_perc` | Same fields | Preserve original identity, position and frequency, including zero |

For annotations, a reviewed `scope.diagnosis` writes `diagnosis_id`;
`scope.assay_group` supplies the source assay mapping. Both require the original
record digest and a reason. Unknown scopes do not default to `base` or a configured
group. Blacklist records with the same position and scope are not collapsed: their
distinct identities remain in the bundle, and conflicting values require review.

Saved report HTML/PDF and referenced analysis files require separate operator-managed
file transfer or retained compatible mounts. Database migration preserves their
references; it does not fetch remote files or recreate historical reports.

## Historical VEP evidence

The source clinical databases can contain transcript evidence in `INFO.CSQ` without
an `anno_vep` collection. Sample conversion builds versioned `anno_vep` records from
that evidence only when the original release is known. A source server's current
VEP metadata does not prove the release used for every historical finding.

Independent annotation conversion currently expands the recorded primary identity;
unknown complementary identities remain null. Enrichment from a separate VEP 103
reference requires identifying that reference snapshot and matching the annotation's
recorded transcript and variant unambiguously. Do not substitute a current transcript,
strip its version to force a match, or relabel unversioned consequences as VEP 103.

Legacy MongoDB 3.2 sources require compatible inspection/export tooling isolated
from the current application runtime. These converters consume offline BSON and
do not downgrade the application driver or connect to the live source.
