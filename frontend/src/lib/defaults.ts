// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

/** Presentation defaults owned by the frontend. The API stores explicit preferences only. */
const DEFAULT_LAYOUT = "classic" as const
const MODERN_VIEW_TRIED = false

export const DEFAULT_ENVIRONMENT = "production" as const
export const DEFAULT_TABLE_PAGE_SIZE = 200
export const TABLE_PAGE_SIZE_OPTIONS = [25, 50, 100, DEFAULT_TABLE_PAGE_SIZE] as const
export const SESSION_ACTIVITY_REFRESH_INTERVAL_MS = 30_000

export const USER_UI_DEFAULTS = {
  theme: "auto",
  analysis_layout: DEFAULT_LAYOUT,
  sample_list_layout: DEFAULT_LAYOUT,
  analysis_modern_view_tried: MODERN_VIEW_TRIED,
  sample_list_modern_view_tried: MODERN_VIEW_TRIED,
  table_page_size: DEFAULT_TABLE_PAGE_SIZE,
} as const

export const NOMENCLATURE_METADATA = {
  p: { label: "Protein (p)" },
  c: { label: "cDNA (c)" },
  g: { label: "Genomic (g)" },
  cn: { label: "Copy number (cn)" },
  f: { label: "Fusion (f)" },
  t: { label: "Translocation (t)" },
} as const
