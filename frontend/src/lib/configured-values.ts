export type ConfiguredValueMetadata = {
  description: string
  className: string
}

/**
 * UI metadata for configuration values that are persisted by the API.
 *
 * The API owns allowed values in `src/coyote3/config/constants.py`; this module owns
 * their concise browser labels, colors, and explanatory hover text.
 */
export const GENELIST_TYPE_METADATA: Record<string, ConfiguredValueMetadata> = {
  snv: {
    description: "Curated genes used to scope small-variant review and reporting.",
    className: "badge-snv",
  },
  cnv: {
    description: "Curated genes used to scope copy-number review and reporting.",
    className: "badge-cnv",
  },
  fusion: {
    description: "Curated genes or partners used to scope fusion review and reporting.",
    className: "badge-fusion",
  },
  expression: {
    description: "Curated genes used for expression-based analysis and reporting.",
    className: "badge-expression",
  },
  pgx: {
    description: "Curated pharmacogenomics genes used for PGx analysis and reporting.",
    className: "badge-pgx",
  },
  adhoc_snv: {
    description: "Temporary, user-applied small-variant gene scope rather than a curated clinical list.",
    className: "badge-adhoc-snv",
  },
  adhoc_cnv: {
    description: "Temporary, user-applied copy-number gene scope rather than a curated clinical list.",
    className: "badge-adhoc-cnv",
  },
  adhoc_fusion: {
    description: "Temporary, user-applied fusion gene scope rather than a curated clinical list.",
    className: "badge-adhoc-fusion",
  },
  adhoc_expression: {
    description: "Temporary, user-applied expression gene scope rather than a curated clinical list.",
    className: "badge-adhoc-expression",
  },
  adhoc_pgx: {
    description: "Temporary, user-applied pharmacogenomics gene scope rather than a curated clinical list.",
    className: "badge-adhoc-pgx",
  },
}

export function configuredValueDescription(value: string) {
  return GENELIST_TYPE_METADATA[String(value || "").toLowerCase()]?.description || ""
}
