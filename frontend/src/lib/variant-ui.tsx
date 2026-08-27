import { AlertCircle, Ban, Bookmark, MessageSquare, ShieldCheck, XCircle, XSquare } from "lucide-react"
import { useState, type ReactNode } from "react"
import { TooltipSurface } from "@/components/ui/app-tooltip"
import {
  clinicalBadgeClassName,
  consequenceBadgeClassName,
  TableBadge,
  tierBadgeClassName,
} from "@/components/ui/table-badge"
import {
  badgeSeverityClass,
  inlineTooltipPosition,
  tooltipSeverityClass,
  VariantTooltipBadge,
  verticalTooltipPosition,
} from "@/lib/variant-badge-primitives"
import { cn } from "@/lib/utils"
import { clinpgxGeneUrl, oncokbGeneUrl } from "@/lib/external-links"
import { filterFlags, normalizedCallerList } from "@/lib/variant-helpers"
import { TIER_LABELS } from "@/lib/variant-ui-meta"

export type FilterFlagMetadata = {
  exact?: Record<string, FilterFlagMeta>
  prefixes?: Record<string, FilterFlagMeta>
  terms?: Record<string, FilterFlagMeta>
}

type FilterFlagMeta = {
  label?: string
  severity?: "pass" | "warn" | "fail" | "info" | "neutral" | string
  description?: string
  hidden?: boolean
}

const tierMeta: Record<number, { roman: string; short: string; description: string; severity: string }> = {
  1: { ...TIER_LABELS[1], severity: "fail" },
  2: { ...TIER_LABELS[2], severity: "warn" },
  3: { ...TIER_LABELS[3], severity: "info" },
  4: { ...TIER_LABELS[4], severity: "pass" },
}

export function TierBadge({ tier, className }: { tier: unknown; className?: string }) {
  const [position, setPosition] = useState<{ left: number; top: number } | null>(null)
  const value = Number(tier)
  if (!Number.isFinite(value) || value === 999) {
    return <span className="text-muted-foreground">-</span>
  }
  const meta = tierMeta[value] || {
    roman: String(value),
    short: "Classification",
    description: "No tier description is configured for this class.",
    severity: "neutral",
  }

  const color =
    value === 1
      ? "bg-tier1"
      : value === 2
        ? "bg-tier2"
        : value === 3
          ? "bg-tier3"
          : value === 4
            ? "bg-tier4"
            : "bg-tierother"

  return (
    <span
      className="inline-flex"
      data-tooltip-managed="true"
      onMouseEnter={(event) => setPosition(verticalTooltipPosition(event))}
      onMouseMove={(event) => setPosition(verticalTooltipPosition(event))}
      onMouseLeave={() => setPosition(null)}
      onFocus={(event) => setPosition(verticalTooltipPosition(event))}
      onBlur={() => setPosition(null)}
    >
      <TableBadge
        tabIndex={0}
        className={cn(
          "interaction-transition cursor-help text-white outline-none ring-offset-background hover:-translate-y-0.5 hover:shadow-md hover:ring-2 hover:ring-ring/35 focus:ring-2 focus:ring-ring/40",
          tierBadgeClassName,
          color,
          className,
        )}
      >
        {value}
      </TableBadge>
      {position && (
        <TooltipSurface position={position} className={tooltipSeverityClass(meta.severity)}>
          <span className="mb-1 block type-label font-semibold uppercase tracking-wide opacity-80">
            Tier {meta.roman}
          </span>
          <span className="block font-bold text-foreground">{meta.short}</span>
          <span className="mt-1 block type-meta leading-relaxed text-foreground/75">{meta.description}</span>
        </TooltipSurface>
      )}
    </span>
  )
}

/**
 * Shape of a finding/variant document as consumed by StatusBadges.
 * Fields are optional because not every variant type carries every flag.
 */
export type FindingRecord = {
  fp?: boolean | null
  blacklisted?: boolean | null
  blacklist?: boolean | null
  override_blacklist?: boolean | null
  irrelevant?: boolean | null
  interesting?: boolean | null
  noteworthy?: boolean | null
  NORMAL?: 0 | 1 | boolean | null
  comments?: unknown[]
  [key: string]: unknown
}

/**
 * Shape of a ClinPGx gene record as consumed by StatusBadges.
 */
export type ClinPgxRecord = {
  pharmgkb_accession_id?: string | null
  has_cpic_dosing_guideline?: boolean | null
  has_variant_annotation?: boolean | null
  [key: string]: unknown
}

export function StatusBadges({
  finding,
  gene,
  hasOncoKbCancerGene = false,
  hasOncoKbActionable = false,
  hasClinPgxGene = false,
  clinPgxRecord,
}: {
  finding: FindingRecord
  gene?: string
  hasOncoKbCancerGene?: boolean
  hasOncoKbActionable?: boolean
  hasClinPgxGene?: boolean
  clinPgxRecord?: ClinPgxRecord
}) {
  const isFp = Boolean(finding?.fp)
  const isBlacklist = Boolean(finding?.blacklisted || (finding?.blacklist && finding?.override_blacklist !== true))
  const isIrrelevant = Boolean(finding?.irrelevant)
  const isInteresting = Boolean(finding?.interesting)
  const isNoteworthy = Boolean(finding?.noteworthy)
  const isNormalCall = finding?.NORMAL === 1 || finding?.NORMAL === true
  const hasBlacklistOverride = Boolean(finding?.override_blacklist)
  const hasComments = Array.isArray(finding?.comments) && finding.comments.length > 0

  return (
    <div className="flex flex-wrap items-center gap-1">
      {isFp && (
        <VariantTooltipBadge
          label="False positive"
          description="This finding has been marked as a false positive for the current sample. It stays visible for traceability but should not be used as report evidence unless the flag is removed."
          severity="fail"
          ariaLabel="False positive"
        >
          <XCircle className="h-3.5 w-3.5" />
        </VariantTooltipBadge>
      )}
      {isBlacklist && (
        <VariantTooltipBadge
          label="Blacklisted"
          description="This finding matches the center blacklist. Blacklisted findings are de-prioritized and are normally excluded unless a sample-specific override is applied."
          severity="fail"
          ariaLabel="Blacklisted"
        >
          <Ban className="h-3.5 w-3.5" />
        </VariantTooltipBadge>
      )}
      {hasBlacklistOverride && (
        <VariantTooltipBadge
          label="Blacklist override"
          description="The center blacklist match has been overridden for this sample, so the finding remains eligible for review in this sample context."
          severity="info"
          ariaLabel="Blacklist override"
        >
          <ShieldCheck className="h-3.5 w-3.5" />
        </VariantTooltipBadge>
      )}
      {isIrrelevant && (
        <VariantTooltipBadge
          label="Irrelevant"
          description="This finding has been marked as irrelevant for the current sample review. It remains auditable and can be restored if the interpretation changes."
          severity="warn"
          ariaLabel="Irrelevant"
        >
          <XSquare className="h-3.5 w-3.5" />
        </VariantTooltipBadge>
      )}
      {isInteresting && (
        <VariantTooltipBadge
          label="Interesting"
          description="This finding has been marked as interesting or report-relevant for focused review."
          severity="pass"
          ariaLabel="Interesting"
        >
          <AlertCircle className="h-3.5 w-3.5" />
        </VariantTooltipBadge>
      )}
      {isNoteworthy && (
        <VariantTooltipBadge
          label="Noteworthy"
          description="This finding has been marked for additional reviewer attention without automatically including it in the report."
          severity="warn"
          ariaLabel="Noteworthy"
        >
          <Bookmark className="h-3.5 w-3.5" />
        </VariantTooltipBadge>
      )}
      {isNormalCall && (
        <VariantTooltipBadge
          label="Normal/control call"
          description="This CNV record was emitted for the normal or control genome. Whole-genome workflows retain these records for paired review."
          severity="neutral"
          ariaLabel="Normal or control CNV"
          textBadge
        >
          N
        </VariantTooltipBadge>
      )}
      {hasComments && (
        <VariantTooltipBadge
          label="Comments available"
          description="One or more sample-specific comments or annotations are attached to this finding."
          severity="info"
          ariaLabel="Has comments"
        >
          <MessageSquare className="h-3.5 w-3.5" />
        </VariantTooltipBadge>
      )}
      {hasOncoKbCancerGene && (
        <VariantTooltipBadge
          href={oncokbGeneUrl(gene)}
          label="OncoKB cancer gene"
          description="The gene is present in the local OncoKB public cancer-gene cache. Open OncoKB for current public gene context."
          severity="info"
          ariaLabel="OncoKB public cancer gene"
          textBadge
        >
          OKB
        </VariantTooltipBadge>
      )}
      {hasOncoKbActionable && (
        <VariantTooltipBadge
          label="Local actionable evidence"
          description="Historical local OncoKB actionable evidence is available for this gene, including drug-level fields from the local cache."
          severity="warn"
          ariaLabel="Historical local OncoKB actionable evidence"
          textBadge
        >
          Rx
        </VariantTooltipBadge>
      )}
      {hasClinPgxGene && (
        <VariantTooltipBadge
          href={clinpgxGeneUrl(gene, clinPgxRecord?.pharmgkb_accession_id)}
          label={
            clinPgxRecord?.has_cpic_dosing_guideline
              ? "ClinPGx dosing gene"
              : clinPgxRecord?.has_variant_annotation
                ? "ClinPGx variant annotation"
                : "ClinPGx gene"
          }
          description={
            clinPgxRecord?.has_cpic_dosing_guideline
              ? "ClinPGx contains pharmacogenomics context for this gene, including a CPIC dosing-guideline marker."
              : clinPgxRecord?.has_variant_annotation
                ? "ClinPGx contains pharmacogenomics variant-annotation context for this gene."
                : "The gene is present in the local ClinPGx gene marker set."
          }
          severity="pgx"
          ariaLabel="ClinPGx gene"
          textBadge
        >
          PGx
        </VariantTooltipBadge>
      )}
    </div>
  )
}

type ArtefactFrequencyItem = {
  key: string
  label: string
  frequency: number
  percent: number
  count: unknown
}

function artefactFrequencyItems(finding: FindingRecord): ArtefactFrequencyItem[] {
  if (!finding || typeof finding !== "object") return []
  return Object.entries(finding)
    .filter(([key]) => key.startsWith("AFRQ_"))
    .map(([key, value]) => {
      const frequency = Number(value)
      const label = key.slice("AFRQ_".length)
      return {
        key,
        label,
        frequency,
        percent: frequency * 100,
        count: finding[`ACOUNT_${label}`],
      }
    })
    .filter((item) => Number.isFinite(item.frequency))
    .sort((left, right) => left.label.localeCompare(right.label))
}

/** Render upstream CNV artefact frequencies with their reference-case counts. */
export function ArtefactFrequencyBadges({ finding }: { finding: FindingRecord }) {
  const items = artefactFrequencyItems(finding)
  if (!items.length) return <span className="text-muted-foreground">-</span>

  return (
    <div className="flex flex-wrap items-center gap-1">
      {items.map((item) => {
        const severity = item.percent >= 1 ? "info" : item.percent >= 0.1 ? "warn" : "pass"
        const countText = item.count !== undefined && item.count !== null && item.count !== ""
          ? ` The reference set contains ${item.count} matching case${Number(item.count) === 1 ? "" : "s"}.`
          : " No matching-case count was supplied."
        return (
          <VariantTooltipBadge
            key={item.key}
            label={`${item.label} artefact frequency`}
            description={`Observed frequency: ${item.percent.toFixed(1)}%.${countText} This evidence is supplied by the upstream CNV pipeline; Coyote displays it but does not recalculate it.`}
            severity={severity}
            ariaLabel={`${item.label} artefact frequency ${item.percent.toFixed(1)} percent`}
            textBadge
            contextLabel="CNV artefact evidence"
          >
            {item.label}
          </VariantTooltipBadge>
        )
      })}
    </div>
  )
}

export function InfoTooltipBadge({
  children,
  label,
  description,
  severity = "info",
  href,
  ariaLabel,
  className,
  contextLabel = "Transcript marker",
}: {
  children: ReactNode
  label: string
  description: string
  severity?: string
  href?: string
  ariaLabel?: string
  className?: string
  contextLabel?: string
}) {
  return (
    <VariantTooltipBadge
      label={label}
      description={description}
      severity={severity}
      href={href}
      ariaLabel={ariaLabel || label}
      textBadge
      textBadgeSize="clinical"
      contextLabel={contextLabel}
      className={className}
    >
      {children}
    </VariantTooltipBadge>
  )
}


function fallbackFlagSeverity(flag: string) {
  const upper = flag.toUpperCase()
  if (upper === "PASS" || upper.startsWith("PASS")) return "pass"
  if (upper.startsWith("FAIL")) return "fail"
  if (upper.startsWith("WARN")) return "warn"
  if (upper.startsWith("T_LOD") || upper.startsWith("LOD")) return "info"
  if (upper.startsWith("PON")) return "warn"
  return "neutral"
}

function severityLabel(severity: string) {
  return {
    pass: "Pass",
    fail: "Fail",
    warn: "Warning",
    info: "Review",
    neutral: "Filter",
  }[severity] || "Filter"
}

function compactFilterFlag(flag: string) {
  return flag
    .replace(/^(FAIL|WARN|PASS)_/i, "")
    .replace(/^T_LOD_/i, "LOD_")
    .replaceAll("_", " ")
}

function flagMetadata(flag: string, metadata?: FilterFlagMetadata): FilterFlagMeta {
  const upper = flag.toUpperCase()
  const exact = metadata?.terms?.[upper] || metadata?.exact?.[upper]
  if (exact) return exact
  for (const [prefix, meta] of Object.entries(metadata?.prefixes || {})) {
    if (upper.startsWith(prefix.toUpperCase())) return meta
  }
  return {}
}

function isDisplayableFilterFlag(flag: string, meta: FilterFlagMeta) {
  if (meta.hidden) return false
  if (meta.label || meta.description || meta.severity) return true
  const upper = flag.toUpperCase()
  return upper === "PASS" || upper.startsWith("FAIL") || upper.startsWith("WARN")
}

function displayFilterFlags(value: unknown, metadata?: FilterFlagMetadata) {
  const severityRank: Record<string, number> = { fail: 5, warn: 4, info: 3, pass: 2, neutral: 1 }
  const grouped = new Map<string, { flag: string; meta: FilterFlagMeta; severity: string; label: string }>()

  for (const flag of filterFlags(value)) {
    const meta = flagMetadata(flag, metadata)
    if (!isDisplayableFilterFlag(flag, meta)) continue
    const severity = String(meta.severity || fallbackFlagSeverity(flag))
    const label = meta.label || compactFilterFlag(flag)
    const key = label.toUpperCase()
    const existing = grouped.get(key)
    if (!existing || (severityRank[severity] || 0) > (severityRank[existing.severity] || 0)) {
      grouped.set(key, { flag, meta, severity, label })
    }
  }

  return Array.from(grouped.values())
}

function FilterFlagBadge({
  flag,
  meta,
  severity,
  label,
}: {
  flag: string
  meta: FilterFlagMeta
  severity: string
  label: string
}) {
  const [position, setPosition] = useState<{ left: number; top: number } | null>(null)
  const description = meta.description || "No center-specific description is configured for this filter flag."

  return (
    <span
      className="relative inline-flex"
      data-tooltip-managed="true"
      onMouseEnter={(event) => setPosition(inlineTooltipPosition(event))}
      onMouseMove={(event) => setPosition(inlineTooltipPosition(event))}
      onMouseLeave={() => setPosition(null)}
      onFocus={(event) => setPosition(inlineTooltipPosition(event))}
      onBlur={() => setPosition(null)}
    >
      <TableBadge
        tabIndex={0}
        className={cn(
          "max-w-[128px] cursor-help truncate uppercase outline-none ring-offset-background transition-colors duration-100 focus:ring-2 focus:ring-ring/40",
          clinicalBadgeClassName,
          badgeSeverityClass(severity),
        )}
      >
        {label}
      </TableBadge>
      {position && (
        <TooltipSurface position={position} className={tooltipSeverityClass(severity)}>
          <span className="mb-1 block type-label font-semibold uppercase tracking-wide opacity-80">
            {severityLabel(severity)} filter
          </span>
          <span className="block break-words font-bold text-foreground">{flag}</span>
          <span className="mt-1 block type-meta leading-relaxed text-foreground/75">{description}</span>
        </TooltipSurface>
      )}
    </span>
  )
}

export function FilterFlagBadges({ value, metadata }: { value: unknown; metadata?: FilterFlagMetadata }) {
  const flags = displayFilterFlags(value, metadata)
  if (!flags.length) return <span className="text-muted-foreground">-</span>

  return (
    <div className="flex max-w-[240px] flex-wrap items-center gap-1">
      {flags.map(({ flag, meta, severity, label }) => (
        <FilterFlagBadge
          key={`${severity}:${label}:${flag}`}
          flag={flag}
          meta={meta}
          severity={severity}
          label={label}
        />
      ))}
    </div>
  )
}

function impactClass(value: unknown) {
  const impact = String(value || "").toUpperCase()
  if (impact === "HIGH") return "matte-badge-fail"
  if (impact === "MODERATE") return "matte-badge-warn"
  if (impact === "LOW") return "matte-badge-pass"
  if (impact === "MODIFIER") return "matte-badge-neutral"
  return "border-muted bg-muted text-muted-foreground"
}

function impactSeverity(value: unknown) {
  const impact = String(value || "").toUpperCase()
  if (impact === "HIGH") return "fail"
  if (impact === "MODERATE") return "warn"
  if (impact === "LOW") return "pass"
  if (impact === "MODIFIER") return "neutral"
  return "info"
}

function impactDescription(value: unknown) {
  const impact = String(value || "").toUpperCase()
  if (impact === "HIGH") {
    return "High predicted consequence. These terms usually indicate a severe coding effect such as truncation, splice disruption, or loss of protein function."
  }
  if (impact === "MODERATE") {
    return "Moderate predicted consequence. These terms usually alter the protein sequence but are not automatically interpreted as loss of function."
  }
  if (impact === "LOW") {
    return "Low predicted consequence. These terms usually have limited expected effect on protein function, such as synonymous or retained-codon changes."
  }
  if (impact === "MODIFIER") {
    return "Modifier consequence. These terms are typically non-coding, intronic, regulatory, intergenic, or otherwise indirect in predicted effect."
  }
  return "No VEP impact description is configured for this value."
}

export function ImpactBadge({ value }: { value: unknown }) {
  const [position, setPosition] = useState<{ left: number; top: number } | null>(null)
  if (!value) return <span className="text-muted-foreground">-</span>
  const severity = impactSeverity(value)
  const impact = String(value).toUpperCase()

  return (
    <span
      className="inline-flex"
      data-tooltip-managed="true"
      onMouseEnter={(event) => setPosition(verticalTooltipPosition(event))}
      onMouseMove={(event) => setPosition(verticalTooltipPosition(event))}
      onMouseLeave={() => setPosition(null)}
      onFocus={(event) => setPosition(verticalTooltipPosition(event))}
      onBlur={() => setPosition(null)}
    >
      <TableBadge
        tabIndex={0}
        className={cn(
          "cursor-help uppercase outline-none ring-offset-background transition-colors duration-100 focus:ring-2 focus:ring-ring/40",
          impactClass(value),
        )}
      >
        {impact}
      </TableBadge>
      {position && (
        <TooltipSurface position={position} className={tooltipSeverityClass(severity)}>
          <span className="mb-1 block type-label font-semibold uppercase tracking-wide opacity-80">VEP impact</span>
          <span className="block font-bold text-foreground">{impact}</span>
          <span className="mt-1 block type-meta leading-relaxed text-foreground/75">{impactDescription(value)}</span>
        </TooltipSurface>
      )}
    </span>
  )
}

export function CallerBadges({ value }: { value: unknown }) {
  const callers = Array.from(new Set(normalizedCallerList(value)))
  if (!callers.length) return null

  return (
    <div className="flex flex-wrap items-center gap-1">
      {callers.map((caller) => (
        <TableBadge key={caller} className="border-primary/25 bg-primary/10 text-primary">
          {caller}
        </TableBadge>
      ))}
    </div>
  )
}

function predictionSeverity(value: unknown) {
  const text = String(value || "").toLowerCase()
  if (!text) return "neutral"
  if (text.includes("possibly") || text.includes("low_confidence")) return "warn"
  if (text.includes("deleterious") || text.includes("damaging") || text.includes("probably")) return "fail"
  if (text.includes("tolerated") || text.includes("benign")) return "pass"
  return "info"
}

function predictionLabel(value: unknown) {
  const text = String(value || "").toLowerCase()
  if (text.includes("deleterious")) return "Deleterious"
  if (text.includes("possibly")) return "Possibly damaging"
  if (text.includes("low_confidence")) return "Low confidence"
  if (text.includes("probably") || text.includes("damaging")) return "Damaging"
  if (text.includes("tolerated")) return "Tolerated"
  if (text.includes("benign")) return "Benign"
  return "Prediction"
}

function predictionDescription(value: unknown) {
  const text = String(value || "").toLowerCase()
  if (text.includes("deleterious")) {
    return "SIFT predicts that the amino-acid substitution is likely to affect protein function."
  }
  if (text.includes("possibly")) {
    return "PolyPhen predicts a possible damaging effect, with lower confidence than a probably damaging call."
  }
  if (text.includes("low_confidence")) {
    return "The prediction is low confidence and should be interpreted cautiously."
  }
  if (text.includes("probably")) {
    return "PolyPhen predicts a probably damaging protein effect. Treat this as supporting computational evidence, not as a standalone classification."
  }
  if (text.includes("damaging")) {
    return "The prediction suggests a damaging protein effect. Use together with clinical, population, and assay evidence."
  }
  if (text.includes("tolerated")) {
    return "SIFT predicts that the amino-acid substitution is likely tolerated."
  }
  if (text.includes("benign")) {
    return "PolyPhen predicts a benign protein effect."
  }
  return "Computational protein-effect prediction. Interpret as supporting evidence only."
}

export function PredictionBadge({ value }: { value: unknown }) {
  const [position, setPosition] = useState<{ left: number; top: number } | null>(null)
  if (!value) return <span className="text-muted-foreground">-</span>
  const severity = predictionSeverity(value)
  return (
    <span
      className="inline-flex"
      data-tooltip-managed="true"
      onMouseEnter={(event) => setPosition(verticalTooltipPosition(event))}
      onMouseMove={(event) => setPosition(verticalTooltipPosition(event))}
      onMouseLeave={() => setPosition(null)}
      onFocus={(event) => setPosition(verticalTooltipPosition(event))}
      onBlur={() => setPosition(null)}
    >
      <TableBadge
        tabIndex={0}
        className={cn(
          "cursor-help outline-none ring-offset-background transition-colors duration-100 focus:ring-2 focus:ring-ring/40",
          badgeSeverityClass(severity),
        )}
      >
        {String(value)}
      </TableBadge>
      {position && (
        <TooltipSurface position={position} className={tooltipSeverityClass(severity)}>
          <span className="mb-1 block type-label font-semibold uppercase tracking-wide opacity-80">Protein prediction</span>
          <span className="block font-bold text-foreground">{predictionLabel(value)}</span>
          <span className="mt-1 block break-words type-meta font-semibold text-foreground/85">{String(value)}</span>
          <span className="mt-1 block type-meta leading-relaxed text-foreground/75">{predictionDescription(value)}</span>
        </TooltipSurface>
      )}
    </span>
  )
}

type ConsequenceMetadata = {
  label?: string
  display_name?: string
  description?: string
  definition?: string
  tooltip?: string
  impact?: string
  IMPACT?: string
}

type ConsequenceTranslations = Record<string, ConsequenceMetadata>

function consequenceMeta(term: string, translations?: ConsequenceTranslations): ConsequenceMetadata {
  return translations?.[term] || {}
}

function ConsequenceBadge({
  term,
  translations,
  compact,
  wide,
}: {
  term: string
  translations?: ConsequenceTranslations
  compact: boolean
  wide: boolean
}) {
  const [position, setPosition] = useState<{ left: number; top: number } | null>(null)
  const meta = consequenceMeta(term, translations)
  const label = meta.label || meta.display_name || term.replace(/_variant$/i, "").replaceAll("_", " ")
  const description = meta.description || meta.definition || meta.tooltip || "No VEP metadata description is available for this consequence."
  const impact = meta.impact || meta.IMPACT
  const severity = impactSeverity(impact)

  return (
    <span
      className="inline-flex"
      data-tooltip-managed="true"
      onMouseEnter={(event) => setPosition(verticalTooltipPosition(event))}
      onMouseMove={(event) => setPosition(verticalTooltipPosition(event))}
      onMouseLeave={() => setPosition(null)}
      onFocus={(event) => setPosition(verticalTooltipPosition(event))}
      onBlur={() => setPosition(null)}
    >
      <TableBadge
        tabIndex={0}
        className={cn(
          "cursor-help lowercase outline-none ring-offset-background transition-colors duration-100 focus:ring-2 focus:ring-ring/40",
          consequenceBadgeClassName,
          wide ? "max-w-[280px] whitespace-normal break-words" : "max-w-[108px] truncate",
          impact ? badgeSeverityClass(severity) : "border-border bg-muted text-foreground",
        )}
      >
        {compact ? label : term}
      </TableBadge>
      {position && (
        <TooltipSurface
          position={position}
          className={impact ? tooltipSeverityClass(severity) : "border-border text-popover-foreground"}
        >
          <span className="mb-1 flex items-center justify-between gap-2 type-label font-semibold uppercase tracking-wide opacity-80">
            <span>VEP consequence</span>
            {impact && <ImpactBadge value={impact} />}
          </span>
          <span className="block font-bold text-foreground">{term}</span>
          <span className="mt-1 block type-meta leading-relaxed text-foreground/75">{description}</span>
        </TooltipSurface>
      )}
    </span>
  )
}

export function ConsequenceBadges({
  value,
  translations,
  compact = true,
  wide = false,
}: {
  value: unknown
  translations?: ConsequenceTranslations
  compact?: boolean
  wide?: boolean
}) {
  const terms = (Array.isArray(value) ? value : String(value || "").split(/[,&]/))
    .map((term) => String(term).trim())
    .filter(Boolean)
  if (!terms.length) return <span className="text-muted-foreground">-</span>
  return (
    <div className={cn("flex flex-wrap items-center gap-1", wide ? "max-w-[320px]" : "max-w-[220px]") }>
      {terms.map((term) => (
        <ConsequenceBadge
          key={String(term)}
          term={String(term)}
          translations={translations}
          compact={compact}
          wide={wide}
        />
      ))}
    </div>
  )
}
