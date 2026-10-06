# Clinical query policy file

The active file comes from the external center configuration directory. The
repository copy under `api/config/center/` is the initial example. This file is
one input to finding retrieval; it is not the query builder. Analysis-specific
Python builders combine the validated policy with sample filters, ASPC settings,
gene-list selections, and request controls. The
[query filtering reference](../reference/assay-filtering.md#clinical-query-policy)
describes these layers and their execution order.

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

## Required values and defaults

The external file is required; the application does not merge missing entries
from the bundled example. All five analysis tables are required. A missing table
or invalid key prevents startup. A default below means loader behavior, not a
clinically approved center choice.

| Setting | Requirement | Behavior if omitted |
| --- | --- | --- |
| `snv.default_somatic_policy`, `snv.default_germline_policy` | Required valid mode | Validation fails; there is no fallback mode. `paired`/`exception_only` in the example are explicit values. |
| `snv.population_frequency_fields` | Optional array; normally configured explicitly | Empty list; no population-field predicates are added by this policy. Omitting it can broaden retrieval. |
| `snv.assay_group_policies` | Optional mapping | No group overrides; use the configured somatic default. |
| Each analysis's `exceptions` | Optional array of tables | No additional exceptions. |
| Exception `id`, `mode` and at least one match condition | Required for each exception | Validation fails. |
| Optional scope lists | Optional | Unrestricted on that dimension; does not mean the rule is disabled. |
| Optional match fields | Optional individually | No condition for the omitted field; other populated conditions still apply. |
| `position_min`, `position_max`, CNV size bounds | Optional | No corresponding bound; supplied bounds remain inclusive. |
| `pgx.exceptions` | Keep empty for the current workflow | No PGX finding retrieval; populated configuration cannot implement it. |

Do not copy an exception without reviewing its scope. Empty/missing scope can
make it apply more widely. The following tables specify valid modes, keys and
combinations and explain how conditions compose.

## File format

The file requires one table for each supported namespace. `[snv]` contains its
baseline settings and may contain `[[snv.exceptions]]`. `[cnv]`,
`[translocation]`, `[fusion]`, and `[pgx]` may each contain an analysis-specific
`exceptions` array. An empty table explicitly states that the released policy
has no additional rules for that analysis. Unknown or missing top-level blocks,
unknown child keys, and keys copied from another analysis are rejected during
application startup.

### TOML block grammar

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

### Condition Composition

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

## Baseline Keys

| TOML path | Required | TOML format | Allowed values | Runtime behavior |
| --- | --- | --- | --- | --- |
| `[snv]` | Yes | Table | One table only | Owns all released SNV retrieval settings. |
| `snv.default_somatic_policy` | Yes | String | `paired`, `case_only`, `exception_only` | Baseline policy for a somatic assay group that has no explicit override. Production default is `paired`. |
| `snv.default_germline_policy` | Yes | String | `paired`, `case_only`, `exception_only` | Baseline germline policy. Production configuration uses `exception_only`, so only approved `admit` exceptions return germline findings. |
| `snv.population_frequency_fields` | No; explicitly configure for population filtering | Array of unique strings | Stored scalar population-frequency field names, for example `gnomad_frequency` | Each numeric value must be at or below the sample `max_popfreq`; absent, null, and non-numeric values remain eligible. Use the exact stored field spelling. |
| `[snv.assay_group_policies]` | No | Table | Zero or more registered assay-group identifiers | Overrides the somatic default for named assay groups. |
| `snv.assay_group_policies.<assay_group>` | No, repeatable | String value within the table | `paired`, `case_only`, `exception_only` | Applies only to somatic retrieval in that exact normalized assay group. Use a registered assay-group identifier, such as `solid` or `hematology`. |

## Exception Keys

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

## Policy and Mode Compatibility

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

### Keys Compatible Within One Exception

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
ordering is a separate governed rule-set concept used for deterministic match behavior.

## Condition Examples

The following examples are complete `[[snv.exceptions]]` blocks. They show
every supported match-key form. They are patterns only: use clinically
approved identifiers and add fixture-based evidence before release.

### Gene and Consequence Term

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

### Exact Variant Identity

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

### VCF FILTER Value

Include a finding only when its VCF `FILTER` array contains a declared value:

```toml
[[snv.exceptions]]
id = "germline_cebpa_filter"
mode = "admit"
intents = ["germline"]
genes = ["CEBPA"]
filter_values = ["GERMLINE"]
```

### Genomic Interval

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

### INFO Field Presence and Exact Value

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

### ALT Pattern

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

### Exclude a Typed Subset

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

## Analysis-specific exception blocks

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

### CNV keys

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

### DNA translocation keys

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

### RNA fusion keys

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

### PGX keys

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

The loader validates the PGX namespace separately from `[snv]`. The application
does not expose a persisted PGX finding table. Deployed PGX exceptions must remain
empty; configuring an exception does not enable PGX finding retrieval.

## Safe authoring protocol

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

> **Warning: Release discipline**
>
>
> Any change to this file can change finding visibility. Validate it with a
> representative fixture and documented expected count before deploying it
> with API, worker, and beat.
>
