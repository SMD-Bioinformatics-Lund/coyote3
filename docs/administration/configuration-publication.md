# Configuration profiles and environment promotion

Open **Assay configurations → Profiles and promotions** to manage reusable defaults
and review configuration releases for another environment.

![Scoped profile compilation, sample pins and independently reviewed promotion](../assets/diagrams/configuration-publication.svg)

## Reusable profiles

A profile contains a stable `profile_id`, a display name, a version, one component
kind, scope bindings and component content. Supported kinds are `filters`,
`reporting`, `clinical_rules` and `template`. Creating a revision saves a draft;
it does not change sample configuration or the published profile selection.

The author records a reason and submits the exact content for independent review.
A different user with `configuration:publish` publishes the reviewed content hash.
Publication selects settings/template profiles for future configuration compilation
and clinical-rule profiles for subsequent report evaluation. Previous revisions
remain available. Existing configuration releases and sample pins remain unchanged.

### Scope and precedence

Bindings use registered resource keys, not display names. The resolver applies these
levels in order, from broadest to most specific:

1. Center defaults.
2. Biological group (`asp_group`).
3. Group, modality and technical family (`asp_category`, `asp_family`).
4. Group and named diagnosis (`diagnosis_id`).
5. Group, diagnosis, modality and family.
6. Group and assay (`asp_id`).
7. Group, diagnosis and assay.

At each level, a binding for the selected `environment` follows a shared binding.
Two different current profiles of the same kind at the same precedence are an
error. The configuration's explicit filter and reporting values take precedence.
Nested objects merge by field; explicit arrays and scalar values replace inherited
values. An empty flag exclusion array therefore removes inherited exclusions.

For example, a filter profile can bind to `{"asp_group": "solid"}` and supply
`{"somatic": {"snv": {"min_depth": 80}}}`. An assay binding uses the registered
`asp_id`, such as `solid_GMSv3`, with its group. Use the keys actually registered
at the center; names in this example do not create resources.

Each compiled configuration captures selected settings/template profile identities, versions, hashes,
bindings' precedence and content in `profile_sources`. Runtime resolution uses the
sample's exact configuration release for these settings. Clinical-rule profiles
resolve separately from current published bindings when a report runs.

### Reporting components

Reporting profiles supply validated reporting fields. Clinical-rule profiles contain
explicit `replace_blocks` and `disable_blocks` operations against a published base
rule release. Unknown block identifiers and invalid compiled rules are rejected.
The report resolution receipt retains the selected base rule, applied profile
sources and effective rule content. These are not attached to ASPC revisions.
When an override changes expected report text or matches, `replace_tests` supplies
reviewed replacements for the affected existing test cases. Other tests remain in
place, and the complete compiled test suite must pass. Unknown test identifiers are
rejected; profiles cannot silently discard the base test suite.

Template profiles select an installed layout by `template_name` and `content_hash`.
The configured layout must match the assay modality. Rendering verifies that the
installed template still has the captured hash; a different layout cannot silently
replace the approved template.

## Promote a configuration

1. Select the source configuration's ObjectId, target environment and validation
   evidence references. Record the reason for the promotion.
2. Create the proposal. It contains the complete candidate release, source hash and
   expected target version. No configuration is activated at this step.
3. A different authorized reviewer examines the candidate and evidence, then approves
   its exact content hash with a review reason.
4. Approval atomically retires the previous active target configuration and publishes
   the new target revision. A changed source or target requires a new proposal.

Promotion retains the source's assay resources, gene lists and settings. Query and
reporting rules resolve independently for the sample's runtime scope. It does not copy sample
findings or annotations, and it does not rebind existing samples. Apply a new
configuration through the sample configuration workflow when appropriate.

## Permissions and audit

Listing requires `assay.config:list`; creating drafts and proposals requires
`assay.config:create`; publication and promotion approval require
`configuration:publish`. Publication records the author, reviewer, time, reason,
content hash and target revision. These permissions do not grant permission to
delete samples or publish clinical annotations.

See [assay setup](assay-setup.md), [resource field contracts](clinical-resource-fields.md),
[query policy resolution](../reference/query-condition-fields.md) and
[report snapshots](../reference/report-snapshots.md).
