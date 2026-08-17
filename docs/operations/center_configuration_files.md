# Center Configuration Reference

Each Coyote3 deployment keeps center-owned configuration under
`api/config/center/`. These files are reviewed and deployed with the
application. They define local terminology, data-source names, public contact
details, and presentation metadata without changing Python or React code.

!!! warning "Deploy the directory as one configuration unit"

    API, Celery worker, beat scheduler, and frontend-facing public endpoints
    must use the same revision of `api/config/center/`. Change the files in
    source control, review the change, then restart API and worker services
    together.

## Ownership Boundary

| Location | Owner | Purpose | Edit for a center deployment? |
| --- | --- | --- | --- |
| `api/config/center/` | Deploying center | Clinical vocabulary, input field names, collection names, public contact content, catalog copy, and flag wording. | Yes, through reviewed configuration changes. |
| `api/config/application_metadata.py` | Coyote3 software | Product description, repository, licence, issue, and support-request URLs. | No. This identifies the Coyote3 codebase. |
| `api/config/constants.py` | Coyote3 software | Supported workflow semantics, data-model values, validators, permission categories, and sequencing-platform capabilities. | No. Extend the software when a new semantic capability is needed. |
| `api/config/runtime_settings.py` | Coyote3 software | Environment-derived runtime, security, cache, mail, and service settings. | No. Supply the documented environment values instead. |

## Directory Layout

```text
api/config/
  application_metadata.py       # repository-owned product metadata
  app_config.py                 # public runtime configuration facade
  runtime_settings.py           # environment-derived runtime setting classes
  constants.py                  # software-owned semantic constants
  loaders/                      # Python loaders for center-owned assets
  center/
    contact.toml                # public center identity and support contacts
    clinical_vocabulary.toml    # center vocabulary and sample-file bindings
    clinical_query_policy.toml  # released analysis-specific query policy
    collections.toml            # Mongo database/collection mapping
    assay_catalog.yaml          # public assay-catalog narrative overlay
    filter_flag_metadata.yaml   # human-facing VCF filter badge metadata
```

The application resolves these paths internally. Do not add configuration-path
environment variables for normal deployments.

## Configuration Model

Coyote3 separates deployment wiring, center-owned configuration, and software
contracts. This prevents a local deployment choice from silently changing a
clinical workflow or a security rule.

| Layer | Location | Owner | Typical contents | Change method |
| --- | --- | --- | --- | --- |
| Runtime settings | A copied `deploy/env/example.env` file | Platform administrator | Database connection, secrets, public mount, paths, resource limits, local timezone | Update the environment and restart the affected services. |
| Center configuration | `api/config/center/` | Center clinical and technical owners | Local terminology, manifest field names, collection mapping, contacts, catalog text, filter explanations | Review the versioned file change and restart API, worker, and beat together. |
| Software contract | Python modules under `api/config/` and typed contracts | Coyote3 maintainers | Implemented analysis types, authentication mechanisms, permission semantics, persistence schemas | Change code, tests, and release documentation. |

The complete environment-variable table is maintained in
[Configuration and Environments](../start_here/configuration.md). This page
documents the center-owned TOML and YAML files.

!!! note "Keep referenced identifiers stable"

    An identifier referenced by an ASP, ASPC, ISGL, sample manifest, report,
    or historical sample is part of the clinical record. Do not rename it for
    presentation purposes. Create a reviewed replacement and plan a migration
    when a meaning must change.

## `contact.toml`

This file controls center-specific content shown on Contact and About pages.
Repository links and the product description are intentionally not present;
they are codebase metadata and remain consistent across deployments.

| TOML path | Required | Allowed value | Runtime behavior |
| --- | --- | --- | --- |
| `[organization]` | Yes | TOML table | Local center identity shown on Contact and About pages. |
| `organization.name` | Yes | Non-empty text | Retained as center metadata. The deployment `ORGANIZATION_NAME` is authoritative for the displayed runtime name; keep both aligned. |
| `organization.department` | No | Text | Department, laboratory, or service shown with center information. |
| `[support]` | Yes | TOML table | General center support information. |
| `support.primary_email` | No | A single support email address | General email contact. Leave blank only when the center intentionally has no general mailbox. |
| `support.urgent_phone` | No | Text | Telephone number or approved urgent escalation route. |
| `[[hours]]` | No, repeatable | TOML array of tables | Each row becomes one service-hours item. |
| `hours[].label` | Yes when present | Text | Short heading, such as `Service desk` or `Out of hours`. |
| `hours[].value` | Yes when present | Text | Schedule or escalation instruction. |
| `[[contacts]]` | Recommended, repeatable | TOML array of tables | Each row becomes one contact card. There is no maximum number of cards. |
| `contacts[].label` | Yes | Text | Visible card title. |
| `contacts[].role` | No | Text | Responsibility or scope beneath the title. |
| `contacts[].email` | No | One legacy email address | Backward-compatible single contact destination. Prefer `contacts[].people` for new configuration. |
| `[[contacts.people]]` | Recommended, repeatable | TOML array of tables nested below one contact channel | One named recipient rendered on its own clickable email line. |
| `contacts[].people[].name` | Recommended | Person or team name | Visible recipient label. |
| `contacts[].people[].email` | Yes when a person is present | One valid email address | `mailto:` destination for that named recipient. |
| `contacts[].phone` | No | Text | Optional direct telephone number. |
| `contacts[].description` | Yes | Text | Explain which questions belong to this contact channel. |

Repository URLs, issue templates, product description, documentation links,
and catalog links are intentionally not configurable per center. They are
loaded from `api/config/application_metadata.py`, because they identify the
Coyote3 software project rather than the deploying organization.

## `clinical_vocabulary.toml`

This file configures center-controlled vocabulary and manifest field names.
It is validated during API and worker startup. The full schema, supported
workflow options, validation rules, and change procedure are documented in
[Clinical Vocabulary Configuration](clinical_vocabulary.md).

Use it when a center needs to change local authentication-provider
availability, a sample YAML file key, baseline file requirement, the file
bound to an implemented analysis type, or the approved transcript-selection
order. It also controls exact fusion-description evidence categories and the
implemented analysis subset allowed for each assay family. Sequencing platforms
and their read capabilities are software-owned and cannot be changed in this
file. The transcript selector names are implemented software contracts, but
their released order is center configuration and is validated strictly at
startup.

!!! important "Assay groups are software-defined"

    Assay groups are not center configuration. They define persisted access,
    annotation, query, ASP, ASPC, and ISGL scope. The supported identifiers are
    `hematology`, `solid`, `pgx`, `tumwgs`, `wts`, `myeloid`, `lymphoid`,
    `fusion`, and `fusionrna`. Assay family (`panel-dna`, `wgs`, `panel-rna`,
    `wts`) and subpanel (for example `endometrie` or `breast`) are separate
    concepts.

## `clinical_query_policy.toml`

This file controls released finding-retrieval policy. It has independent
namespaces for `snv`, `cnv`, `translocation`, `fusion`, and `pgx`. It is
constrained configuration, not a free-form MongoDB query file: the application
validates all values at startup and converts only documented fields into the
stored contract for that analysis. A key accepted by one namespace is rejected
in every namespace where it has no defined meaning.

This policy is resolved alongside the basic SNV filters stored under
`samples.filters.<intent>.snv`. The sample filters supply the actual VAF,
depth, alternate-read, control-frequency, population-frequency, consequence,
ISGL, and ad-hoc gene values. `paired` and `case_only` apply those basic
values and may extend or exclude a narrow subset. `exception_only`
intentionally omits the general threshold/consequence admission branch and
admits only findings matching an approved `admit` exception. The policy file
therefore selects the evidence model; it never duplicates threshold values.

SNV has a configurable baseline evidence model because paired, case-only, and
exception-only SNV review use materially different genotype evidence. CNV,
translocation, and fusion keep their ordinary ASPC filter behavior and support
typed `admit` and `exclude` exceptions. PGX has its own validated namespace so
PGX policy cannot be placed under SNV; it becomes executable when a persisted
PGX finding query is introduced.

### File format

The file requires one table for each supported namespace. `[snv]` contains its
baseline settings and may contain `[[snv.exceptions]]`. `[cnv]`,
`[translocation]`, `[fusion]`, and `[pgx]` may each contain an analysis-specific
`exceptions` array. An empty table explicitly states that the released policy
has no additional rules for that analysis. Unknown or missing top-level blocks,
unknown child keys, and keys copied from another analysis are rejected during
application startup.

#### TOML block grammar

TOML uses single and double square brackets for different data structures:

| Syntax | Data structure | Cardinality | Purpose in this file |
| --- | --- | --- | --- |
| `[snv]` | Named table | Exactly one | Defines the default somatic policy, default germline policy, and indexed population-frequency fields. |
| `[snv.assay_group_policies]` | Named child table | Zero or one | Maps a supported assay-group identifier to a somatic policy override. |
| `[[snv.exceptions]]` | Array element | Zero or more | Appends one independent exception object to `snv.exceptions`. Double brackets are required because the policy may contain multiple exceptions. |
| `[snv.exceptions.info_equals]` | Named child table of the current exception | Zero or one per exception | Adds exact INFO-field comparisons to the immediately preceding `[[snv.exceptions]]` entry. It uses single brackets because it is one mapping inside that exception, not another exception. |
| `[cnv]` and `[[cnv.exceptions]]` | Named table and repeatable child entries | One table; zero or more entries | Owns CNV-only admissions and exclusions. |
| `[translocation]` and `[[translocation.exceptions]]` | Named table and repeatable child entries | One table; zero or more entries | Owns DNA translocation-only admissions and exclusions. |
| `[fusion]` and `[[fusion.exceptions]]` | Named table and repeatable child entries | One table; zero or more entries | Owns RNA fusion-only admissions and exclusions. |
| `[pgx]` and `[[pgx.exceptions]]` | Named table and repeatable child entries | One table; zero or more entries | Reserves PGX-only typed policy. It does not alter SNV retrieval. |

For example, the following creates two exceptions. The `info_equals` mapping
belongs only to `germline_myeloid_marker`. The second `[[snv.exceptions]]`
line starts a new array element and therefore closes the first exception:

```toml
[[snv.exceptions]]
id = "germline_myeloid_marker"
mode = "admit"
intents = ["germline"]

[snv.exceptions.info_equals]
MYELOID_GERMLINE = 1

[[snv.exceptions]]
id = "solid_lowqual_exclusion"
mode = "exclude"
intents = ["somatic"]
assay_groups = ["solid"]
filter_values = ["LOWQUAL"]
```

Keep `[snv.exceptions.info_equals]` directly below its owning exception and
before the next `[[snv.exceptions]]` entry. Writing
`[[snv.exceptions.info_equals]]` would describe an array of mappings and is
not supported by the application contract.

#### Condition Composition

Scope fields first decide whether an exception applies to the current request.
Match fields then identify findings. The combination rules are fixed and do
not depend on declaration order:

| Situation | Combination rule | Example |
| --- | --- | --- |
| Values within `intents`, `assay_groups`, `asp_ids`, or `subpanel_ids` | **OR** within that field | `assay_groups = ["solid", "hematology"]` permits either group. |
| Different populated scope fields | **AND** | `intents = ["somatic"]` plus `asp_ids = ["solid_gmsv3"]` requires both. |
| Values within `genes`, `consequence_terms`, `filter_values`, `chromosomes`, or `simple_ids` | **OR** within that match field | `genes = ["TERT", "TP53"]` matches either gene. |
| Different populated match fields | **AND** | `genes = ["TERT"]` plus `filter_values = ["LOWQUAL"]` matches only low-quality TERT findings. |
| `info_fields_present` values | **AND** | `info_fields_present = ["SVTYPE", "END"]` requires both INFO fields to exist. |
| Entries in `[snv.exceptions.info_equals]` | **AND** | Two entries require both exact INFO comparisons to pass. |
| `position_min` and `position_max` | **AND**, inclusive | With both values, `POS` must be inside the closed interval. Either bound may be used alone. |
| `alt_regex` with any other match field | **AND** | A FLT3 rule with `alt_regex` requires both the gene and ALT pattern. |
| Separate `[[snv.exceptions]]` entries with an inclusion mode | **OR**, additive | A finding may enter through any applicable inclusion exception. |
| Separate `exclude` entries | Remove on any match | A finding matching any applicable exclusion is removed after inclusion is evaluated. |

At least one match field is mandatory. Scope fields alone are not sufficient:
an exception restricted to `solid` still needs a gene, consequence, identity,
coordinate, INFO, FILTER, or ALT condition.

```toml
[snv]
default_somatic_policy = "paired"
default_germline_policy = "exception_only"
population_frequency_fields = ["gnomad_frequency", "gnomad_max"]

[[snv.exceptions]]
id = "endometrial_specific_variant"
mode = "extend_consequence"
intents = ["somatic"]
asp_ids = ["solid_gmsv3"]
subpanel_ids = ["endometrie"]
simple_ids = ["17_7674220_C_T"]
consequence_terms = ["missense_variant"]
```

When a clinically approved assay group must use a different somatic evidence
model, add the optional override separately:

```toml
[snv.assay_group_policies]
solid = "case_only"
```

Omit the table when every somatic assay group uses
`default_somatic_policy`. The released application configuration currently
uses the default for all supported assay groups.

### Baseline Keys

| TOML path | Required | TOML format | Allowed values | Runtime behavior |
| --- | --- | --- | --- | --- |
| `[snv]` | Yes | Table | One table only | Owns all released SNV retrieval settings. |
| `snv.default_somatic_policy` | Yes | String | `paired`, `case_only`, `exception_only` | Baseline policy for a somatic assay group that has no explicit override. Production default is `paired`. |
| `snv.default_germline_policy` | Yes | String | `paired`, `case_only`, `exception_only` | Baseline germline policy. Production configuration uses `exception_only`, so only approved `admit` exceptions return germline findings. |
| `snv.population_frequency_fields` | Yes | Array of unique strings | Stored scalar population-frequency field names, for example `gnomad_frequency` | Each numeric value must be at or below the sample `max_popfreq`; absent, null, and non-numeric values remain eligible. Use the exact stored field spelling. |
| `[snv.assay_group_policies]` | No | Table | Zero or more software-owned assay-group identifiers | Overrides the somatic default for named assay groups. |
| `snv.assay_group_policies.<assay_group>` | No, repeatable | String value within the table | `paired`, `case_only`, `exception_only` | Applies only to somatic retrieval in that exact normalized assay group. The key is a supported software-owned assay-group identifier, such as `solid` or `hematology`. |

### Exception Keys

Every `[[snv.exceptions]]` table requires `id`, `mode`, and at least one
**match key**. Scope keys are optional; omitting a scope key means it matches
every value of that scope. The application rejects unknown keys, duplicate
identifiers, duplicate list values, empty list values, unsupported characters
in identifiers, invalid mode/intent values, inverted position ranges, and raw
MongoDB expressions.

| TOML path | Required | TOML format | Allowed values / format | Meaning |
| --- | --- | --- | --- | --- |
| `snv.exceptions[].id` | Yes | String | Unique identifier using letters, numbers, `_`, or `-`; normalized to lowercase | Stable clinical exception name for review, tests, and release notes. Example: `endometrial_specific_variant`. |
| `snv.exceptions[].mode` | Yes | String | `extend_consequence`, `admit`, or `exclude` | `extend_consequence` adds an approved consequence-term route while retaining all baseline gates. `admit` is an alternative admission route used by `exception_only`. `exclude` removes matching findings after all baseline and admission rules are evaluated. |
| `snv.exceptions[].intents` | No | Array of strings | `somatic`, `germline` | Scope key. Restricts the exception to one or both review intents. Omit for either intent. |
| `snv.exceptions[].assay_groups` | No | Array of strings | Supported normalized assay-group identifiers | Scope key. Restricts to assay groups such as `solid` or `hematology`. |
| `snv.exceptions[].asp_ids` | No | Array of strings | Existing normalized ASP identifiers | Scope key. Restricts to design panels, for example `solid_gmsv3`. |
| `snv.exceptions[].subpanel_ids` | No | Array of strings | Existing normalized subpanel identifiers; use `base` only for the base scope | Scope key. Restricts to in-silico subpanels. |
| `snv.exceptions[].genes` | No | Array of strings | HGNC symbols; values are normalized to uppercase | Match key. Requires `INFO.selected_CSQ.SYMBOL` to be one listed gene. |
| `snv.exceptions[].consequence_terms` | No | Array of strings | Exact VEP consequence terms, for example `missense_variant` | Match key. Requires `variants.consequence_terms` to contain one listed term. Ingest derives this index from every VEP transcript consequence for the variant; it does not query a selected transcript or the versioned vault at request time. |
| `snv.exceptions[].filter_values` | No | Array of strings | Exact VCF FILTER values; values are normalized to uppercase | Match key. Requires the stored `FILTER` array to contain one listed value. |
| `snv.exceptions[].chromosomes` | No | Array of strings | Stored chromosome labels; values are normalized to uppercase | Match key. Requires `CHROM` to be one listed chromosome. |
| `snv.exceptions[].position_min` | No | Integer | Non-negative genomic position | Match key. Inclusive lower bound for `POS`. Use with or without `position_max`. |
| `snv.exceptions[].position_max` | No | Integer | Integer no smaller than `position_min` when both are present | Match key. Inclusive upper bound for `POS`. |
| `snv.exceptions[].simple_ids` | No | Array of strings | Exact stored `CHROM_POS_REF_ALT` identity strings | Match key. Restricts to a known variant identity. Case is preserved. |
| `snv.exceptions[].info_fields_present` | No | Array of strings | Stored VCF INFO identifiers using letters, numbers, `_`, or `-` | Match key. Requires each named `INFO.<field>` to exist. Field casing is preserved. |
| `[snv.exceptions.info_equals]` | No | Nested TOML table belonging to the preceding exception | INFO identifier to scalar value mapping | Match key. Requires every listed `INFO.<field>` to equal the supplied TOML value exactly. |
| `snv.exceptions[].alt_regex` | No | String | Valid Python regular expression | Match key. Requires ALT to match the released expression. Escape backslashes for TOML, for example `"\\w{10,200}"`. |

### Policy and Mode Compatibility

The baseline policy determines which inclusion modes are executable. The
loader validates that every mode name is known, while the query builder uses
only the modes that belong to the selected evidence model:

| Resolved baseline policy | Baseline evidence | Effective inclusion exception | Final exclusion |
| --- | --- | --- | --- |
| `paired` | Case thresholds, paired-control rule, configured population-frequency fields, selected consequence terms, and gene scope | `extend_consequence` | `exclude` |
| `case_only` | Case or untyped-genotype thresholds, configured population-frequency fields, selected consequence terms, and gene scope; no paired-control predicate | `extend_consequence` | `exclude` |
| `exception_only` | No general threshold/consequence admission branch | `admit` | `exclude` |

An `admit` exception has no effect under `paired` or `case_only`.
An `extend_consequence` exception has no effect under `exception_only`.
Although these combinations are syntactically valid, they are not useful and
should fail clinical review. `exclude` is compatible with every baseline and
is always applied after the inclusion query has been assembled.

`[snv.assay_group_policies]` affects somatic retrieval only. Germline retrieval
always uses `default_germline_policy`. The override table keys are normalized,
software-supported assay-group identifiers; the values are one of `paired`,
`case_only`, or `exception_only`.

#### Keys Compatible Within One Exception

All scope keys are compatible with all match keys. All match keys can also be
combined with one another because they become AND predicates. Use combinations
that describe one coherent clinical rule:

| Combination | Supported | Guidance |
| --- | --- | --- |
| `genes` + `consequence_terms` | Yes | Preferred for a gene-specific extension to the accepted consequence set. |
| `genes` + `filter_values` | Yes | Matches the named gene only when one declared VCF FILTER value is present. |
| `chromosomes` + position bounds | Yes | Defines a genomic interval; normally use one chromosome with its bounds. |
| `simple_ids` + other identity fields | Yes | Usually redundant. `simple_ids` is already an exact variant identity, so add another field only when the extra restriction is intentional. |
| `info_fields_present` + `info_equals` | Yes | Useful when one INFO field must exist and another must equal a value. An `info_equals` entry already implies presence for that same field. |
| `alt_regex` + `genes` or coordinates | Yes | Narrows an ALT pattern to a clinically reviewed locus. Prefer a narrow scope over a global regex. |
| Scope keys without a match key | No | Rejected because it could admit or exclude an entire assay/request scope. |
| Raw MongoDB keys or operators | No | Rejected. Only the typed fields in the exception-key table are accepted. |
| `priority`, templates, report sections, or UI fields | No | They belong to other contracts and are not query-policy syntax. |

There is deliberately no `priority` key for query exceptions. The resulting
exception predicates are additive `$or` branches; their order cannot change
the returned result set. TOML order is retained only for human readability and
diagnostic output; it has no clinical or query meaning. Reporting-text rule
priority is a separate YAML concept used for first-match template rendering.

### Condition Examples

The following examples are complete `[[snv.exceptions]]` blocks. They show
every supported match-key form. They are patterns only: use clinically
approved identifiers and add fixture-based evidence before release.

#### Gene and Consequence Term

Include one or more VEP consequence terms for one gene while still
requiring the normal baseline evidence:

```toml
[[snv.exceptions]]
id = "solid_tert_regulatory"
mode = "extend_consequence"
intents = ["somatic"]
assay_groups = ["solid"]
genes = ["TERT"]
consequence_terms = ["regulatory_region_variant", "TF_binding_site_variant"]
```

#### Exact Variant Identity

Include one exact normalized variant identity for a named ASP and subpanel.
This is the narrowest rule form and is preferred when the clinical decision is
about one known variant:

```toml
[[snv.exceptions]]
id = "endometrial_known_variant"
mode = "extend_consequence"
intents = ["somatic"]
asp_ids = ["solid_gmsv3"]
subpanel_ids = ["endometrie"]
simple_ids = ["17_7674220_C_T"]
```

#### VCF FILTER Value

Include a finding only when its VCF `FILTER` array contains a declared value:

```toml
[[snv.exceptions]]
id = "germline_cebpa_filter"
mode = "admit"
intents = ["germline"]
genes = ["CEBPA"]
filter_values = ["GERMLINE"]
```

#### Genomic Interval

Include a bounded coordinate interval. The bounds are inclusive and can be
used together or individually:

```toml
[[snv.exceptions]]
id = "germline_chr1_interval"
mode = "admit"
intents = ["germline"]
chromosomes = ["1"]
position_min = 115256521
position_max = 115256537
```

#### INFO Field Presence and Exact Value

Match a declared VCF INFO field either by presence or exact value. The nested
`[snv.exceptions.info_equals]` table belongs to the exception immediately
above it:

```toml
[[snv.exceptions]]
id = "flt3_structural_marker"
mode = "extend_consequence"
intents = ["somatic"]
genes = ["FLT3"]
info_fields_present = ["SVTYPE"]

[[snv.exceptions]]
id = "myeloid_germline_marker"
mode = "admit"
intents = ["germline"]

[snv.exceptions.info_equals]
MYELOID_GERMLINE = 1
```

#### ALT Pattern

Include a finding whose ALT allele matches a released regular expression. TOML
requires the backslash to be escaped:

```toml
[[snv.exceptions]]
id = "flt3_large_insertion"
mode = "extend_consequence"
intents = ["somatic"]
genes = ["FLT3"]
alt_regex = "\\w{10,200}"
```

#### Exclude a Typed Subset

Exclusion rules use exactly the same scope and match keys as inclusion rules,
but remove matching findings after the baseline query and any admission rules
have been built. This is appropriate for a reviewed technical or clinical
exclusion, not for an informal reviewer preference:

```toml
[[snv.exceptions]]
id = "solid_exclude_low_quality_tert"
mode = "exclude"
intents = ["somatic"]
assay_groups = ["solid"]
genes = ["TERT"]
filter_values = ["LOWQUAL"]
```

In this example, only a TERT finding with the `LOWQUAL` filter is removed. A
different gene, or a TERT finding without that filter, remains eligible.

### Analysis-specific exception blocks

CNV, translocation, fusion, and PGX rules use the same scope keys but have
different match vocabularies. Every rule requires `id`, `mode`, and at least
one match key. The only modes are:

| Mode | Meaning |
| --- | --- |
| `admit` | Adds a narrow alternative to the ordinary query or effective gene scope for that analysis. When the ordinary query is already unrestricted, an admission cannot broaden it further. |
| `exclude` | Removes a matching finding after the ordinary query and applicable admissions have been combined. |

These modes are deliberately simpler than SNV modes. `extend_consequence` is
an SNV-only operation because CNV, translocation, fusion, and PGX do not use
the SNV VEP consequence gate.

The shared scope keys are:

| Key | Required | Allowed format | Meaning |
| --- | --- | --- | --- |
| `id` | Yes | Unique letters, numbers, `_`, or `-` | Stable rule identifier within that analysis namespace. IDs need not be unique across different namespaces. |
| `mode` | Yes | `admit` or `exclude` | Selects alternative admission or final removal. |
| `intents` | No | `somatic`, `germline` | Restricts the rule to a review intent. Germline execution remains limited by the application capability for the analysis. |
| `assay_groups` | No | Supported normalized assay-group IDs | Restricts the rule to one or more assay groups. |
| `asp_ids` | No | Existing normalized ASP IDs | Restricts the rule to one or more design panels. |
| `subpanel_ids` | No | Existing normalized subpanel IDs | Restricts the rule to named in-silico scopes; use `base` for the base ASPC scope. |

Values inside one scope or match array are alternatives. Different populated
keys in the same rule are combined with AND. Separate applicable `admit` rules
are alternative OR branches. A match against any applicable `exclude` rule
removes the finding last. Declaration order has no query meaning and there is
no `priority` key.

#### CNV keys

Use `[[cnv.exceptions]]` only for CNV records. The ordinary CNV query continues
to use the sample's CNV loss/gain, size, evidence, normal-call, and target-specific
gene-scope configuration.

| Match key | Format | Stored meaning |
| --- | --- | --- |
| `genes` | HGNC symbols, normalized uppercase | Matches `genes.gene` or `panel_gene`. |
| `callers` | Caller IDs, normalized lowercase | Matches a member of the stored `callers` array. |
| `effects` | CNV type IDs, normalized uppercase | Matches stored `type`, for example `AMP`, `GAIN`, `LOSS`, or `DEL`. |
| `chromosomes` | Stored chromosome labels, normalized uppercase | Matches stored `chr`. |
| `size_min` | Non-negative integer | Inclusive minimum stored CNV `size`. |
| `size_max` | Non-negative integer not below `size_min` | Inclusive maximum stored CNV `size`. |

```toml
[[cnv.exceptions]]
id = "solid_retain_egfr_amplification"
mode = "admit"
intents = ["somatic"]
asp_ids = ["solid_gmsv3"]
genes = ["EGFR"]
effects = ["AMP"]
size_min = 1000
```

This rule admits only an EGFR amplification of at least 1,000 bases in the
named ASP scope. It does not modify SNV, fusion, or translocation results.

#### DNA translocation keys

Use `[[translocation.exceptions]]` for DNA structural translocation records.
Admissions extend the independently resolved translocation gene scope;
exclusions are applied after that scope.

| Match key | Format | Stored meaning |
| --- | --- | --- |
| `genes` | HGNC symbols, normalized uppercase | Matches either complete gene token in the translocation annotation. |
| `gene_pairs` | Two symbols separated by `--`, for example `BCR--ABL1` | Matches either orientation of the exact two-gene pair. |
| `svtypes` | Structural type IDs, normalized uppercase | Matches `INFO.SVTYPE`. |
| `chromosomes` | Stored chromosome labels, normalized uppercase | Matches stored `CHROM`. |

```toml
[[translocation.exceptions]]
id = "hematology_bcr_abl1"
mode = "admit"
intents = ["somatic"]
assay_groups = ["hematology"]
gene_pairs = ["BCR--ABL1"]
svtypes = ["BND"]
```

#### RNA fusion keys

Use `[[fusion.exceptions]]` for RNA fusion records. The ordinary fusion query
continues to apply the sample's spanning-read, spanning-pair, caller, effect,
description, and target-specific gene filters.

| Match key | Format | Stored meaning |
| --- | --- | --- |
| `genes` | HGNC symbols, normalized uppercase | Matches `gene1` or `gene2`. |
| `gene_pairs` | Two symbols separated by `--` | Matches either partner orientation. |
| `callers` | Canonical caller IDs, normalized lowercase | Matches `calls[].caller`. |
| `effects` | Fusion effect IDs, normalized lowercase | Matches `calls[].effect`, for example `in-frame`. |
| `descriptions` | Complete evidence tokens, normalized lowercase | Matches a complete comma-delimited `calls[].desc` token, not a substring. |

```toml
[[fusion.exceptions]]
id = "wts_retain_kmt2a_aff1"
mode = "admit"
intents = ["somatic"]
assay_groups = ["wts"]
gene_pairs = ["KMT2A--AFF1"]
callers = ["fusioncatcher"]
descriptions = ["known", "oncogene"]
```

The fields in this one rule are AND conditions. The fusion must have the named
pair and one stored call satisfying the configured caller and either listed
description token.

#### PGX keys

`[pgx]` is independent from SNV because pharmacogenomic findings use diplotype,
phenotype, and medication concepts rather than SNV genotype thresholds.

| Match key | Format | Intended PGX meaning |
| --- | --- | --- |
| `genes` | HGNC symbols, normalized uppercase | PGX gene symbol. |
| `diplotypes` | Exact case-preserved values | Called diplotype, for example `*1/*2`. |
| `phenotypes` | Normalized lowercase values | Interpreted metabolizer or response phenotype. |
| `medications` | Normalized lowercase values | Medication associated with the PGX finding. |

```toml
[pgx]

# Add entries only when the persisted PGX finding query is released.
# [[pgx.exceptions]]
# id = "cyp2c19_intermediate_metabolizer"
# mode = "admit"
# genes = ["CYP2C19"]
# diplotypes = ["*1/*2"]
# phenotypes = ["intermediate metabolizer"]
```

The loader validates this namespace now so PGX policy cannot be misplaced
under `[snv]`. The current application does not yet expose a persisted PGX
finding table, so deployed PGX exceptions must remain empty until that query
workflow is implemented and tested.

### Safe authoring protocol

1. Start from the standard analysis baseline. For SNV, use
   `extend_consequence` when the
   normal case, control, depth, VAF, and population-frequency gates must remain
   mandatory.
2. Use the narrowest applicable scope: add `asp_ids` and `subpanel_ids` before
   adding a broad `assay_groups` scope.
3. Use match keys from the selected analysis only. For SNV, use `simple_ids`
   for one identity or `genes` plus `consequence_terms` for a gene-level rule.
   For structural findings, prefer an exact `gene_pairs` rule over a broad gene
   rule when the approved decision concerns one pair.
4. In SNV, use `admit` only with an `exception_only` baseline. In CNV,
   translocation, and fusion, `admit` is an explicit alternative to the normal
   analysis filter. Use `exclude` only for a reviewed removal; it applies after
   the baseline and every admission branch.
5. Add a representative fixture and expected result count to the release
   review. Restart API, worker, and beat together after deployment.

At least one clinical match field is required for every exception. The policy
cannot name an arbitrary MongoDB field, operator, aggregation expression, or
JavaScript fragment.

!!! warning "Release discipline"

    Any change to this file can change finding visibility. Validate it with a
    representative fixture and documented expected count before deploying it
    with API, worker, and beat.

### Field-Level Contract

| TOML path | Required | Allowed values | Used for |
| --- | --- | --- | --- |
| `assay.categories` | Yes | Non-empty, unique lowercase identifiers | Omics categories that own `files.<category>` and `analysis.<category>` configuration. |
| `assay.families` | Yes | Non-empty, unique lowercase identifiers | ASP family choices. Every family must appear in `assay.family_categories`, `assay.family_scopes`, and `files.required_by_family`. |
| `assay.base_subpanel_id` | Yes | One lowercase identifier | Base ASPC subpanel identifier used when an assay has no selected named subpanel. |
| `assay.family_categories.<family>` | Yes, once per family | One configured category | Associates each assay family with its file and analysis vocabulary. |
| `assay.family_scopes.<family>` | Yes, once per family | One non-empty identifier | Sets the sequencing scope written for samples of that family. |
| `environment.options` | Yes | Unique lowercase identifiers | Environment/profile options selectable in ASPC and sample workflows. |
| `environment.default` | Yes | One item in `environment.options` | Default environment used when none is specified. |
| Software platform registry | Not a TOML value | `illumina`, `iontorrent`, `pacbio`, `nanopore` | Validates ASP/sample platform. It derives read technology and constrains the read-mode field: Illumina permits `SE` or `PE`; the other current platforms have no selectable read mode. Add a platform only through a software release with its capability definition. |
| `authentication.providers` | Yes | One or both of `local`, `ldap` | Default values allowed in a user's `auth_type` list. `local` uses username and a local password; `ldap` uses email and the configured directory service. A deployment can override this default with `AUTHENTICATION_PROVIDERS`. No other provider is implemented. |
| `genelist.standard_types` | Yes | Non-empty, unique identifiers | ISGL types offered when the ad-hoc switch is off. |
| `genelist.adhoc_types` | Yes | Non-empty, unique identifiers with no overlap with standard types | ISGL types offered when the ad-hoc switch is on. |
| `reporting.required_aspc_fields` | Yes | Non-empty, unique ASPC reporting field identifiers | Lists the report metadata expected for active report-capable ASPCs. |
| `files.dna.keys` | Yes | Non-empty, unique identifiers using letters, numbers, `_`, or `-`; normalized to lowercase | All permitted file keys under `files` in a DNA sample manifest. |
| `files.rna.keys` | Yes | Same identifier rule as DNA | All permitted file keys under `files` in an RNA sample manifest. |
| `files.required_by_family.panel-dna` | Yes | One or more keys from `files.dna.keys` | Baseline mandatory declared files for every panel DNA sample. |
| `files.required_by_family.wgs` | Yes | One or more keys from `files.dna.keys` | Baseline mandatory declared files for every WGS sample. |
| `files.required_by_family.panel-rna` | Yes | One or more keys from `files.rna.keys` | Baseline mandatory declared files for every panel RNA sample. |
| `files.required_by_family.wts` | Yes | One or more keys from `files.rna.keys` | Baseline mandatory declared files for every WTS sample. |
| `analysis.dna.types` | Yes | Unique uppercase identifiers | DNA analysis labels enabled in ASPC forms. New labels also require a matching application workflow before ingest/reporting can process them. |
| `analysis.dna.file_keys.<TYPE>` | Yes, once for every enabled DNA type | One or more keys declared in `files.dna.keys` | Associates a DNA analysis type with its source file key(s). The mapping keys must exactly match `analysis.dna.types`. |
| `analysis.rna.types` | Yes | Unique uppercase identifiers | RNA analysis labels enabled in ASPC forms. New labels also require a matching application workflow before ingest/reporting can process them. |
| `analysis.rna.file_keys.<TYPE>` | Yes, once for every enabled RNA type | One or more keys declared in `files.rna.keys` | Associates an RNA analysis type with its source file key(s). The mapping keys must exactly match `analysis.rna.types`. |

| Analysis type | Input expectation | Notes |
| --- | --- | --- |
| `SNV` | Small-variant VCF | DNA only. The first configured file key is the primary source. |
| `CNV` | CNV calls | DNA only. Typically a CNV JSON result. |
| `CNV_PROFILE` | CNV profile image | DNA only. Rendered beside the CNV table. |
| `TRANSLOCATION` | Structural-variant calls | DNA only. May share the same source as `FUSION`. |
| `FUSION` | DNA structural-variant or RNA fusion calls | The supported source depends on the omics section. |
| `BIOMARKER` | Biomarker payload | DNA only. |
| `COVERAGE` | Coverage payload | DNA only. Provides quality and gene/exon coverage views. |
| `TMB` | Tumour mutational burden result | DNA only. |
| `PGX` | Pharmacogenomic result | DNA or RNA. |
| `EXPRESSION` | Expression result | RNA only. |
| `CLASSIFICATION` | Classifier result | RNA only. |
| `QC` | Quality-control payload | RNA only. |

!!! warning "Manifest, ASPC, and source-file agreement"

    A file may be omitted only when it is neither required by assay family nor
    declared for an enabled analysis. If the manifest declares a file for an
    analysis, ingest must load it successfully. A missing or unreadable
    declared file fails the ingest instead of producing a partly ready sample.

## `collections.toml`

This file maps logical repository attributes to physical MongoDB collection
names. Each top-level TOML table is one database name, for example
`[coyote3_dev]` or `[BAM_Service]`.

### Mapping Contract

`collections.toml` maps typed repositories to physical MongoDB collections. It
does not define a document schema and it does not move data.

| TOML element | Required | Allowed value | Meaning |
| --- | --- | --- | --- |
| Application database table, for example `[coyote3_dev]` | Yes for every database used as `COYOTE3_DB` | Exact MongoDB database name | The mapping selected for the primary Coyote3 database. |
| BAM database table, for example `[BAM_Service]` | Required when `BAM_DB` integration is enabled | Exact MongoDB database name | The mapping selected for BAM-service lookup data. |
| `*_collection` | Yes for every active logical repository | Non-empty MongoDB collection name, excluding the reserved `system.*` namespace | Physical destination for one logical repository. Keep the key fixed; change only its value when the center uses another collection name. |
| `bam_samples` | Required when the selected BAM database is used | Non-empty MongoDB collection name | BAM-service sample lookup collection. |

| Collection family | Logical configuration keys | Content stored in the mapped collection |
| --- | --- | --- |
| Users and governance | `users_collection`, `roles_collection`, `permissions_collection`, `groups_collection`, `schemas_collection` | User accounts, roles, permission definitions, optional groups, and administration schemas. |
| Assay configuration | `asp_collection`, `aspc_collection`, `insilico_genelist_collection` | Assay definitions, active/versioned assay configurations, and curated gene lists. Clinical report wording remains in repository-owned YAML sources. |
| Sample and reporting workflow | `samples_collection`, `sample_comments_collection`, `reports_collection`, `reported_variants_collection`, `blacklist_collection` | Sample lifecycle records, sample-level comments, reports, report snapshots, and blacklist state. |
| DNA findings | `variants_collection`, `annotations_collection`, `anno_vep_collection`, `cnvs_collection`, `fusions_collection`, `transloc_collection`, `biomarkers_collection` | Parsed small variants and their annotations, CNVs, fusions, translocations, and biomarkers. |
| Coverage and RNA results | `coverage_collection`, `groupcov_collection`, `expression_collection`, `rna_expression_collection`, `rna_qc_collection`, `rna_classification_collection` | Coverage, grouped coverage, expression, RNA quality control, and RNA classification data. |
| Reference annotations | `hgnc_collection`, `vep_metadata_collection`, `cosmic_collection` | HGNC identity/transcript data, VEP metadata, and COSMIC data. |
| Knowledgebases | `civic_variants_collection`, `civic_gene_collection`, `oncokb_collection`, `oncokb_actionable_collection`, `oncokb_genes_collection`, `oncokb_public_collection`, `oncokb_genes_public_collection`, `oncokb_cancer_genes_public_collection`, `clinpgx_genes_public_collection`, `brcaexchange_collection`, `iarc_tp53_collection` | Local knowledgebase imports and public reference material used for clinical markers and detail views. |

!!! caution "Changing names is not a migration"

    A collection mapping change redirects future reads and writes only. It does
    not copy documents, indexes, report links, or audit history. Create and
    validate the destination collection before changing a production mapping.

## `assay_catalog.yaml`

This YAML file provides catalog narrative and presentation metadata. Clinical
assay records, ASPCs, and ISGLs remain the authoritative source for active
analysis configuration and gene content.

### Catalog Key Reference

The catalog is a presentation overlay. ASPs define assays, ASPCs define active
analysis configuration, and ISGLs define curated genes. Editing this YAML file
changes public catalog content; it does not change clinical filtering, ingest
requirements, or report behavior.

| YAML path | Required | Allowed value | Use and fallback behavior |
| --- | --- | --- | --- |
| `version` | Yes | Text or number | Catalog-content revision. |
| `last_updated` | Recommended | ISO-style date or text | Public maintenance date. |
| `maintainer` | Recommended | Text | Center team responsible for catalog content. |
| `header` | Recommended | Text | Catalog landing-page heading. |
| `description` | Recommended | Text, including multiline YAML text | Catalog landing-page introduction. |
| `layout.order` | Recommended | Ordered list of modality keys | Display order. Modalities omitted from the list are appended after configured values. |
| `modalities.<modality>` | Yes for each modality | Mapping | A public modality, for example `WGS`, `WTS`, or `GenePanels`. Its key is a stable presentation identifier. |
| `modalities.<modality>.label` | Yes | Text | Visible modality label. |
| `modalities.<modality>.title` | No | Text | Expanded title; falls back to `label`. |
| `modalities.<modality>.description` | No | Text | Modality explanatory text. |
| `modalities.<modality>.categories.<category>` | Yes for every catalog section | Mapping | One public assay/category section. |
| `category.catalog_id` | Recommended | Stable text identifier | Catalog route and presentation identity. |
| `category.label` | Yes | Text | Visible category heading. |
| `category.title` | No | Text | Expanded heading; falls back to `label`. |
| `category.description` | Recommended | Text | Public assay description; falls back to the ASP description where available. |
| `category.subheading` | No | Text | Supplemental heading. |
| `category.asp_id` | Recommended | Existing ASP `asp_id` | Links the catalog section to the physical assay definition. |
| `category.subpanel_id` | No | Existing ASPC subpanel identifier | Narrows the category to a subpanel. Use the configured base subpanel when no specific subpanel applies. |
| `category.aspc_id` | No | Existing ASPC identifier | Direct configuration reference. |
| `category.aspc_ids` | No | Mapping of environment label to existing ASPC identifier | Environment-specific catalog context. |
| `category.family` / `category.asp_family` | No | Supported ASP family identifier | Optional public family override; normally inherited from the ASP. |
| `category.assay_group` | No | Existing center assay-group value | Optional public group override; normally inherited from the ASP. |
| `category.input_material` | No | List of display strings | Public sample/input badges. |
| `category.tat` | No | Text | Turnaround-time statement, for example `7-14 days`. |
| `category.sample_modes` | No | List of display strings | Sample-mode badges, for example `Tumor-only` or `Tumor-normal`. |
| `category.analysis` | No | List of display strings | Public analysis summary. If omitted, available analysis is derived from the ASPC. |
| `category.report_sections` | No | List of display strings | Public report-content summary. |
| `category.clinical_indications` | No | List of text values | Public clinical indication list. |
| `category.limitations`, `category.public_notes` | No | Text | Public limitations and supplementary notes. |
| `category.gene_lists` | No | Ordered list of mappings | Gene-list sections within the category. |
| `gene_lists[].key` or `gene_lists[].isgl_id` | Required for an ISGL-backed list | Existing ISGL `isgl_id` | Resolves active ISGL metadata and gene coverage. Remove blank placeholder entries in new catalog content. |
| `gene_lists[].label`, `description` | No | Text | List-specific visible text; label falls back to the ISGL display name. |
| `gene_lists[].diagnosis` | No | List of display strings | List-specific clinical context. |
| `gene_lists[].subpanel_id`, `list_type` | No | Existing subpanel ID or ISGL list type | List-specific context overrides. |
| `gene_lists[].tat`, `input_material`, `sample_modes`, `analysis` | No | Same forms as the category keys | List-level values override the corresponding category value. |

!!! info "Use ASP, ASPC, and ISGL for clinical truth"

    Catalog YAML is appropriate for descriptions, turnaround-time wording,
    public input labels, and display order. Use ASP, ASPC, and ISGL records for
    active assay behavior, required files, analytical settings, and genes.
    ASPC contributes only `catalog.is_public` to the public catalog. All other
    public catalog wording and presentation values belong in this YAML file.

## `filter_flag_metadata.yaml`

This YAML file turns VCF `FILTER` values into readable badge labels and
tooltips. It does not change filtering or tiering logic.

### Flag Metadata Key Reference

| YAML path | Required | Allowed value | Interface behavior |
| --- | --- | --- | --- |
| `exact` | Recommended | Mapping keyed by an exact upper-case VCF `FILTER` string | Used for known exact values, including `PASS`. |
| `prefixes` | Recommended | Mapping keyed by an upper-case prefix | Used when neither a detailed term nor an exact value matches. The first matching configured prefix supplies the fallback metadata. |
| `terms` | Recommended | Mapping keyed by a complete known VCF `FILTER` string | Used for caller-specific terms. A term takes precedence over an `exact` value and a prefix. |
| `*.label` | Yes for displayed metadata | Short text | Visible badge text. Keep it compact for dense clinical tables. |
| `*.severity` | Yes for displayed metadata | `pass`, `fail`, `warn`, `info`, or `neutral` | Badge and tooltip color family: green, red, amber, blue/indigo, or muted respectively. |
| `*.description` | Yes for displayed metadata | A clear sentence | Tooltip explanation. Describe the biological or technical implication, not merely the color. |
| `*.hidden` | No | Boolean, default `false` | When `true`, the term remains known but is suppressed from visible badges. |

Matching order is: full `terms` match, full `exact` match, first matching
`prefixes` entry, then the application's general fallback for common `PASS`,
`FAIL`, and `WARN` patterns. Add a `terms` entry whenever a generic prefix
cannot give reviewers a sufficiently specific explanation.

## Software-Owned Values

The following values are intentionally not configurable by a center. They are
application behavior and changing them requires a software change.

| Item | Defined in | Why it is software-owned |
| --- | --- | --- |
| Permission identifiers and permission categories | `api/config/constants.py` and authorization contracts | Centers assign existing permissions to roles; they do not define new authorization semantics. |
| Authentication implementation | `api/config/security.py` and authentication services | The vocabulary file can enable `local` and/or `ldap`, but it cannot add an authentication protocol. |
| Supported analysis types | Typed contracts, parsers, repositories, UI, and reporting services | A new type requires end-to-end ingestion, storage, display, report, and test support. |
| Reporting-rule operators and rendering behavior | Reporting contracts and rule engine | Clinical content follows its own controlled reporting-rule release process. |
| Normalized database-version keys | `api/config/database_versions.py` | Keys such as `database_versions.vep` are stable software contracts; source parsing is not a center vocabulary setting. |
| Product, licence, repository, and issue URLs | `api/config/application_metadata.py` | These identify Coyote3 itself rather than the deploying center. |

## Safe Change Protocol

1. Identify whether the change is center vocabulary, presentation content, or
   a software capability. Only the first two belong in `api/config/center/`.
2. Edit the smallest relevant file and retain stable identifiers already used
   by historical samples, ASPCs, ISGLs, or report releases.
3. Review the diff with clinical and technical owners.
4. Run configuration and contract validation in a non-production environment.
5. Restart API, worker, and beat services together.
6. Verify one representative public page and one representative ingest or
   report workflow affected by the change.

!!! tip "When not to edit a configuration file"

    Do not use center configuration to introduce a new analysis type, parser,
    authentication protocol, permission semantic, or report rule evaluator.
    Those are software capabilities and require a typed implementation,
    contracts, tests, and documentation update.
