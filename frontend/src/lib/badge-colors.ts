import { GENELIST_TYPE_METADATA, configuredValueDescription } from "@/lib/configured-values"

/** Workflow colors shared by resource tables and governed document workspaces. */
export const workflowStatusClasses = {
  draft: "badge-info",
  submitted: "badge-warning",
  pending: "badge-warning",
  in_clinical_review: "badge-signal",
  approved: "badge-success",
  rejected: "badge-danger",
  published: "matte-badge-production",
  retired: "badge-neutral",
  unpublished: "badge-neutral",
} as const

export const sequencingValueClasses: Record<string, string> = {
  dna: "badge-dna",
  rna: "badge-rna",
  "panel-dna": "badge-panel-dna",
  "panel-rna": "badge-panel-rna",
  wgs: "badge-wgs",
  wts: "badge-wts",
}

export const configuredValueClasses: Record<string, string> = {
  ...sequencingValueClasses,
  local: "badge-auth-local",
  ldap: "badge-auth-ldap",
  production: "matte-badge-production",
  development: "badge-development",
  testing: "badge-testing",
  validation: "badge-validation",
  somatic: "badge-somatic",
  germline: "badge-germline",
  hematology: "badge-hematology",
  solid: "badge-solid",
  pgx: "badge-pgx",
  tumwgs: "badge-tumwgs",
  "tumwgs-hema": "badge-tumwgs-hema",
  "tumwgs-solid": "badge-tumwgs-solid",
  myeloid: "badge-myeloid",
  lymphoid: "badge-lymphoid",
  illumina: "badge-illumina",
  pacbio: "badge-pacbio",
  nanopore: "badge-nanopore",
  iontorrent: "badge-iontorrent",
  ...Object.fromEntries(Object.entries(GENELIST_TYPE_METADATA).map(([value, metadata]) => [value, metadata.className])),
  SNV: "badge-snv",
  CNV: "badge-cnv",
  TRANSLOCATION: "badge-translocation",
  HRD: "badge-hrd",
  MSI: "badge-msi",
  CNV_PROFILE: "badge-cnv-profile",
  FUSION: "badge-fusion",
  TMB: "badge-tmb",
  PGX: "badge-pgx",
  EXPRESSION: "badge-expression",
  CLASSIFICATION: "badge-classification",
  QC: "badge-analysis-qc",
}

export const roleFallbackClasses: Record<string, string> = {
  superuser: "badge-role-superuser",
  admin: "badge-role-admin",
  developer: "badge-role-developer",
  tester: "badge-role-tester",
  manager: "badge-role-manager",
  user: "badge-role-user",
  viewer: "badge-role-viewer",
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
  if (kind === "status" && Object.hasOwn(workflowStatusClasses, value.toLowerCase())) {
    return workflowStatusClasses[value.toLowerCase() as keyof typeof workflowStatusClasses]
  }
  const exact = configuredValueClasses[value] || configuredValueClasses[value.toLowerCase()] || configuredValueClasses[value.toUpperCase()]
  if (exact) return exact
  if (kind === "role") return roleFallbackClasses[value.toLowerCase()] || "badge-role-unknown"
  return "badge-value-unknown"
}

export { configuredValueDescription }
