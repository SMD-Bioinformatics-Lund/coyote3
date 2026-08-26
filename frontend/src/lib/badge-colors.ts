import { GENELIST_TYPE_METADATA, configuredValueDescription } from "@/lib/configured-values"

export const configuredValueClasses: Record<string, string> = {
  local: "badge-warning",
  ldap: "badge-info",
  dna: "badge-info",
  rna: "badge-signal",
  production: "matte-badge-production",
  development: "badge-info",
  testing: "badge-neutral",
  validation: "badge-warning",
  hematology: "badge-danger",
  solid: "badge-warning",
  pgx: "badge-pgx",
  tumwgs: "badge-warning",
  wts: "badge-signal",
  myeloid: "badge-danger",
  lymphoid: "badge-success",
  "panel-dna": "badge-info",
  "panel-rna": "badge-signal",
  wgs: "badge-success",
  illumina: "badge-info",
  pacbio: "badge-success",
  nanopore: "badge-neutral",
  iontorrent: "badge-warning",
  ...Object.fromEntries(Object.entries(GENELIST_TYPE_METADATA).map(([value, metadata]) => [value, metadata.className])),
  SNV: "badge-info",
  CNV: "badge-warning",
  TRANSLOCATION: "badge-info",
  BIOMARKER: "badge-success",
  CNV_PROFILE: "badge-warning",
  FUSION: "badge-signal",
  TMB: "badge-warning",
  PGX: "badge-pgx",
  EXPRESSION: "badge-signal",
  CLASSIFICATION: "badge-success",
  QC: "badge-neutral",
}

export const roleFallbackClasses: Record<string, string> = {
  superuser: "badge-neutral",
  admin: "badge-danger",
  developer: "badge-info",
  tester: "badge-info",
  manager: "badge-warning",
  user: "badge-success",
  viewer: "badge-neutral",
}

export const namedAccentColors: Record<string, string> = {
  red: "var(--accent-red)",
  blue: "var(--accent-blue)",
  yellow: "var(--accent-yellow)",
  indigo: "var(--accent-indigo)",
  green: "var(--accent-green)",
  purple: "var(--accent-purple)",
  brown: "var(--accent-brown)",
  gray: "var(--accent-gray)",
  grey: "var(--accent-gray)",
}

export function accentColor(value: string) {
  return namedAccentColors[value.toLowerCase()] || value
}

export function valueBadgeClass(value: string, kind?: string) {
  const exact = configuredValueClasses[value] || configuredValueClasses[value.toLowerCase()] || configuredValueClasses[value.toUpperCase()]
  if (exact) return exact
  if (kind === "role") return roleFallbackClasses[value.toLowerCase()] || "badge-info"
  return "badge-neutral"
}

export { configuredValueDescription }
