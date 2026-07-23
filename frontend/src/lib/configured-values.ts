export type ConfiguredValueMetadata = {
  description: string
  className: string
}

/**
 * UI metadata for configuration values that are persisted by the API.
 *
 * The API owns allowed values in `api/config/constants.py`; this module owns
 * their concise browser labels, colors, and explanatory hover text.
 */
export const GENELIST_TYPE_METADATA: Record<string, ConfiguredValueMetadata> = {
  snv: {
    description: "Curated genes used to scope small-variant review and reporting.",
    className: "border-indigo-300 bg-indigo-100 text-indigo-800 dark:border-indigo-500/50 dark:bg-indigo-500/15 dark:text-indigo-200",
  },
  cnv: {
    description: "Curated genes used to scope copy-number review and reporting.",
    className: "border-orange-300 bg-orange-100 text-orange-800 dark:border-orange-500/50 dark:bg-orange-500/15 dark:text-orange-200",
  },
  fusion: {
    description: "Curated genes or partners used to scope fusion review and reporting.",
    className: "border-rose-300 bg-rose-100 text-rose-800 dark:border-rose-500/50 dark:bg-rose-500/15 dark:text-rose-200",
  },
  expression: {
    description: "Curated genes used for expression-based analysis and reporting.",
    className: "border-pink-300 bg-pink-100 text-pink-800 dark:border-pink-500/50 dark:bg-pink-500/15 dark:text-pink-200",
  },
  pgx: {
    description: "Curated pharmacogenomics genes used for PGx analysis and reporting.",
    className: "border-fuchsia-300 bg-fuchsia-100 text-fuchsia-800 dark:border-fuchsia-500/50 dark:bg-fuchsia-500/15 dark:text-fuchsia-200",
  },
  adhoc_snv: {
    description: "Temporary, user-applied small-variant gene scope rather than a curated clinical list.",
    className: "border-indigo-300 bg-indigo-50 text-indigo-700 dark:border-indigo-500/50 dark:bg-indigo-500/10 dark:text-indigo-200",
  },
  adhoc_cnv: {
    description: "Temporary, user-applied copy-number gene scope rather than a curated clinical list.",
    className: "border-orange-300 bg-orange-50 text-orange-700 dark:border-orange-500/50 dark:bg-orange-500/10 dark:text-orange-200",
  },
  adhoc_fusion: {
    description: "Temporary, user-applied fusion gene scope rather than a curated clinical list.",
    className: "border-rose-300 bg-rose-50 text-rose-700 dark:border-rose-500/50 dark:bg-rose-500/10 dark:text-rose-200",
  },
  adhoc_expression: {
    description: "Temporary, user-applied expression gene scope rather than a curated clinical list.",
    className: "border-pink-300 bg-pink-50 text-pink-700 dark:border-pink-500/50 dark:bg-pink-500/10 dark:text-pink-200",
  },
  adhoc_pgx: {
    description: "Temporary, user-applied pharmacogenomics gene scope rather than a curated clinical list.",
    className: "border-fuchsia-300 bg-fuchsia-50 text-fuchsia-700 dark:border-fuchsia-500/50 dark:bg-fuchsia-500/10 dark:text-fuchsia-200",
  },
}

export function configuredValueDescription(value: string) {
  return GENELIST_TYPE_METADATA[String(value || "").toLowerCase()]?.description || ""
}
