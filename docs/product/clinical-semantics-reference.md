# Clinical Terms, Tiers, Flags, and Frequencies

This page is a practical reference for what users see in Coyote3 and what those values mean in backend/data terms.

## Why this page exists

The same concept can appear in multiple forms:

- a color badge in UI
- a short label or shorthand (`HP`, `PON`, `Tier III`)
- a backend field (`class`, `fp`, `max_popfreq`)
- a persisted DB value in one or more collections

This page maps those together so users and developers can read the system consistently.

## Tier system used in Coyote3

Tier values are numeric (`1..4`) in data and rendered as Tier I..IV in UI.

| Tier (DB/API) | UI text | Short clinical meaning | Badge preview | UI color token | Hex color |
|---|---|---|---|---|---|
| `1` | `Tier I` | Stark klinisk signifikans | <span style="display:inline-block;padding:2px 8px;border-radius:9999px;background:#d55e00;color:#ffffff;font-weight:600;">Tier I</span> | `--color-tier1` | `#d55e00` |
| `2` | `Tier II` | Potentiell klinisk signifikans | <span style="display:inline-block;padding:2px 8px;border-radius:9999px;background:#e69f00;color:#1f2937;font-weight:600;">Tier II</span> | `--color-tier2` | `#e69f00` |
| `3` | `Tier III` | Oklar klinisk signifikans | <span style="display:inline-block;padding:2px 8px;border-radius:9999px;background:#0072b2;color:#ffffff;font-weight:600;">Tier III</span> | `--color-tier3` | `#0072b2` |
| `4` | `Tier IV` | Benign/sannolikt benign | <span style="display:inline-block;padding:2px 8px;border-radius:9999px;background:#009e73;color:#ffffff;font-weight:600;">Tier IV</span> | `--color-tier4` | `#009e73` |
| `999` | (unclassified/internal fallback) | Not classified | <span style="display:inline-block;padding:2px 8px;border-radius:9999px;background:#666666;color:#ffffff;font-weight:600;">Unclassified</span> | `--color-tier999` | `#666666` |

Notes:

- Tier naming and short/long Swedish descriptions are defined centrally in report utility mappings.
- UI tier badges use classes like `bg-tier1`, `bg-tier2`, etc.

## Where tier is stored and grouped

| Area | Field/key | Meaning |
|---|---|---|
| Global annotation docs | `class` (annotation document) | Current classification for a variant/nomenclature in context |
| Report snapshot docs (`reported_variants`) | `tier` | Tier at report creation time (audit-safe snapshot) |
| Dashboard/API rollups | `tier1..tier4` | Aggregated counts by tier |
| UI tables/cards | `classification.class` or `doc.class` | Current value shown as badge |

Important behavior:

- Dashboard tier stats are computed from `reported_variants` snapshots (not only live annotation state), so historical report distribution is preserved.

## Variant action flags and consequences

These are boolean state fields toggled by UI actions and API routes.

| Concept in UI | Backend/API flag | Typical DB field | Effect in software |
|---|---|---|---|
| False positive | `false-positive` endpoint | `fp` | Marked as artifact/noise; often down-prioritized visually and in review |
| Interesting | `interesting` endpoint | `interesting` | Included in report-oriented/summary selections (for CNV/translocation paths) |
| Irrelevant | `irrelevant` endpoint | `irrelevant` | Explicitly de-prioritized/excluded in some workflows |
| Noteworthy (CNV) | `noteworthy` endpoint | `noteworthy` | Kept visible as notable, but not equivalent to report-positive |

Resource coverage (canonical API):

- Small variants: `false-positive`, `interesting`, `irrelevant`
- CNVs: `false-positive`, `interesting`, `noteworthy`
- Translocations: `false-positive`, `interesting`
- Fusions: `false-positive` (single + bulk), `irrelevant` (bulk)

## Filter shorthand badges shown in UI (SNV quality/filter badges)

These abbreviations are display shorthand grouped from raw caller/filter strings.

| UI badge | Group | Badge preview | Meaning |
|---|---|---|---|
| `PASS` | pass | <span style="display:inline-block;padding:2px 8px;border-radius:9999px;background:#166534;color:#ffffff;font-weight:600;">PASS</span> | Variant passed quality filters |
| `GERM` | germline | <span style="display:inline-block;padding:2px 8px;border-radius:9999px;background:#b5761b;color:#ffffff;font-weight:600;">GERM</span> | Germline or germline-risk context |
| `HP` | warn | <span style="display:inline-block;padding:2px 8px;border-radius:9999px;background:#c17c00;color:#ffffff;font-weight:600;">HP</span> | Homopolymer warning |
| `SB` | warn/fail | <span style="display:inline-block;padding:2px 8px;border-radius:9999px;background:#c17c00;color:#ffffff;font-weight:600;">SB</span> | Strand-bias warning or fail |
| `LO` | warn | <span style="display:inline-block;padding:2px 8px;border-radius:9999px;background:#c17c00;color:#ffffff;font-weight:600;">LO</span> | Low tumor VAF warning |
| `XLO` | warn | <span style="display:inline-block;padding:2px 8px;border-radius:9999px;background:#c17c00;color:#ffffff;font-weight:600;">XLO</span> | Very low tumor VAF warning |
| `PON` | warn/fail | <span style="display:inline-block;padding:2px 8px;border-radius:9999px;background:#8c1d1d;color:#ffffff;font-weight:600;">PON</span> | In panel-of-normals warnings/failures |
| `FFPE` | warn/fail | <span style="display:inline-block;padding:2px 8px;border-radius:9999px;background:#8c1d1d;color:#ffffff;font-weight:600;">FFPE</span> | FFPE panel warnings/failures |
| `N` | fail | <span style="display:inline-block;padding:2px 8px;border-radius:9999px;background:#8c1d1d;color:#ffffff;font-weight:600;">N</span> | High VAF in normal sample |
| `P` | fail | <span style="display:inline-block;padding:2px 8px;border-radius:9999px;background:#8c1d1d;color:#ffffff;font-weight:600;">P</span> | P-value fail |
| `LD` | fail | <span style="display:inline-block;padding:2px 8px;border-radius:9999px;background:#8c1d1d;color:#ffffff;font-weight:600;">LD</span> | Long deletion fail |

These are normalized from multiple raw tags (`WARN_*`, `FAIL_*`) to concise UI badges.

## Consequence terminology: short form vs full form

Consequence data is rendered using VEP metadata translations and includes:

- short label (shown in compact UI chips)
- full display name
- detailed description
- impact class (`HIGH`, `MODERATE`, `LOW`, `MODIFIER`)

Example mapping pattern:

| Full consequence key | UI short label | Display name | Impact |
|---|---|---|---|
| `splice_acceptor_variant` | `splice acceptor` | Splice acceptor variant | `HIGH` |
| `frameshift_variant` | `frameshift` | Frameshift variant | `HIGH` |
| `missense_variant` | `missense` | Missense variant | `MODERATE` |
| `synonymous_variant` | `synonymous` | Synonymous variant | `LOW` |
| `intergenic_variant` | `intergenic` | Intergenic variant | `MODIFIER` |

DNA filtering uses grouped consequence selectors (`splicing`, `missense`, `other_coding`, etc.) which are expanded to one-or-more VEP SO terms before query execution.

## Population frequency fields and thresholds

### Which frequency values are used

During ingest, Coyote3 stores these per-variant population frequency fields:

- `gnomad_frequency`
- `gnomad_max`
- `exac_frequency`
- `thousandG_frequency`

`gnomad_frequency` is derived primarily from VEP `gnomAD_AF` (fallback: `gnomADg_AF`), and `gnomad_max` from VEP `MAX_AF`.

### Which threshold is used in filtering

- The active threshold is sample-level filter `sample.filters.max_popfreq`.
- Default in DNA ASP config schema is `0.01` (1%).

In query behavior, numeric `gnomad_frequency` values are filtered with:

- `gnomad_frequency <= max_popfreq`

Variants with missing/null/non-numeric population values are allowed through instead of hard-dropped (so unknown values are still reviewable).

### How it is shown in UI

- UI displays frequencies as percent (`value * 100`).
- Entries above `max_popfreq` are highlighted in red in the variant frequency table.

## How values are grouped in software and DB

### In software (runtime grouping)

- `analysis_sections` from assay config controls which sections appear (SNV, CNV, TRANSLOCATION, FUSION, etc.).
- Reporting/summary logic uses flag-aware subsets (for example, `interesting` CNVs/translocations for summary sections).

### In database (persisted grouping)

- `samples.filters.*`: active per-sample filter state (`max_popfreq`, `vep_consequences`, `cnveffects`, etc.)
- `variants`/`cnvs`/`translocations`/`fusions`: resource-level evidence + flags
- `annotations`: live classification/comment context (including `class`)
- `reported_variants`: frozen report-time tier snapshot (`tier`) for audit/history

## Practical reading guide for users

When you inspect a variant row in UI:

1. Read tier badge color + value for clinical priority level.
2. Read filter shorthand badges (`PASS`, `PON`, `FFPE`, etc.) for quality context.
3. Read consequence short label; hover/details map to full consequence meaning and impact class.
4. Compare displayed population frequencies against the active `max_popfreq` threshold.
5. Check flags (`interesting`, `false positive`, `irrelevant`, `noteworthy`) to understand reporting consequences.
