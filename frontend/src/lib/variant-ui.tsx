import { AlertCircle, Ban, MessageSquare, ShieldCheck, XCircle, XSquare } from "lucide-react"
import { useState, type FocusEvent, type MouseEvent, type ReactNode } from "react"
import { createPortal } from "react-dom"
import { cn } from "@/lib/utils"
import { clinpgxGeneUrl, oncokbGeneUrl } from "@/lib/external-links"
import { filterFlags, normalizedCallerList } from "@/lib/variant-helpers"

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
  1: {
    roman: "I",
    short: "Stark klinisk signifikans",
    description: "Variant av stark klinisk signifikans.",
    severity: "fail",
  },
  2: {
    roman: "II",
    short: "Potentiell klinisk signifikans",
    description: "Variant av potentiell klinisk signifikans.",
    severity: "warn",
  },
  3: {
    roman: "III",
    short: "Oklar klinisk signifikans",
    description: "Variant av oklar klinisk signifikans.",
    severity: "info",
  },
  4: {
    roman: "IV",
    short: "Benign/sannolikt benign",
    description: "Variant bedömd som benign eller sannolikt benign.",
    severity: "pass",
  },
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
      onMouseEnter={(event) => setPosition(belowOrAboveTooltipPosition(event))}
      onMouseMove={(event) => setPosition(belowOrAboveTooltipPosition(event))}
      onMouseLeave={() => setPosition(null)}
      onFocus={(event) => setPosition(belowOrAboveTooltipPosition(event))}
      onBlur={() => setPosition(null)}
    >
      <span
        tabIndex={0}
        className={cn(
          "inline-flex h-6 min-w-6 cursor-help items-center justify-center rounded-full px-2 text-xs font-bold text-white shadow-sm outline-none ring-offset-background transition-all duration-100 hover:-translate-y-0.5 hover:shadow-md hover:ring-2 hover:ring-ring/35 focus:ring-2 focus:ring-ring/40",
          color,
          className,
        )}
      >
        {value}
      </span>
      {position && createPortal(
        <span
          className={cn(
            "pointer-events-none fixed z-[9999] w-72 rounded-lg border px-3 py-2 text-left text-xs shadow-lg",
            tooltipSeverityClass(meta.severity),
          )}
          style={{ left: position.left, top: position.top }}
        >
          <span className="mb-1 block text-[10px] font-black uppercase tracking-wide opacity-80">
            Tier {meta.roman}
          </span>
          <span className="block font-bold text-foreground">{meta.short}</span>
          <span className="mt-1 block text-[11px] leading-relaxed text-foreground/75">{meta.description}</span>
        </span>,
        document.body,
      )}
    </span>
  )
}

export function StatusBadges({
  finding,
  gene,
  hasOncoKbCancerGene = false,
  hasOncoKbActionable = false,
  hasClinPgxGene = false,
  clinPgxRecord,
}: {
  finding: any
  gene?: string
  hasOncoKbCancerGene?: boolean
  hasOncoKbActionable?: boolean
  hasClinPgxGene?: boolean
  clinPgxRecord?: any
}) {
  const isFp = Boolean(finding?.fp)
  const isBlacklist = Boolean(finding?.blacklisted || (finding?.blacklist && finding?.override_blacklist !== true))
  const isIrrelevant = Boolean(finding?.irrelevant)
  const isInteresting = Boolean(finding?.interesting)
  const hasBlacklistOverride = Boolean(finding?.override_blacklist)
  const hasComments = Array.isArray(finding?.comments) && finding.comments.length > 0

  return (
    <div className="flex flex-wrap items-center gap-1">
      {isFp && (
        <StatusTooltipBadge
          label="False positive"
          description="This finding has been marked as a false positive for the current sample. It stays visible for traceability but should not be used as report evidence unless the flag is removed."
          severity="fail"
          ariaLabel="False positive"
        >
          <XCircle className="h-3.5 w-3.5" />
        </StatusTooltipBadge>
      )}
      {isBlacklist && (
        <StatusTooltipBadge
          label="Blacklisted"
          description="This finding matches the center blacklist. Blacklisted findings are de-prioritized and are normally excluded unless a sample-specific override is applied."
          severity="fail"
          ariaLabel="Blacklisted"
        >
          <Ban className="h-3.5 w-3.5" />
        </StatusTooltipBadge>
      )}
      {hasBlacklistOverride && (
        <StatusTooltipBadge
          label="Blacklist override"
          description="The center blacklist match has been overridden for this sample, so the finding remains eligible for review in this sample context."
          severity="info"
          ariaLabel="Blacklist override"
        >
          <ShieldCheck className="h-3.5 w-3.5" />
        </StatusTooltipBadge>
      )}
      {isIrrelevant && (
        <StatusTooltipBadge
          label="Irrelevant"
          description="This finding has been marked as irrelevant for the current sample review. It remains auditable and can be restored if the interpretation changes."
          severity="warn"
          ariaLabel="Irrelevant"
        >
          <XSquare className="h-3.5 w-3.5" />
        </StatusTooltipBadge>
      )}
      {isInteresting && (
        <StatusTooltipBadge
          label="Interesting"
          description="This finding has been marked as interesting or report-relevant for focused review."
          severity="pass"
          ariaLabel="Interesting"
        >
          <AlertCircle className="h-3.5 w-3.5" />
        </StatusTooltipBadge>
      )}
      {hasComments && (
        <StatusTooltipBadge
          label="Comments available"
          description="One or more sample-specific comments or annotations are attached to this finding."
          severity="info"
          ariaLabel="Has comments"
        >
          <MessageSquare className="h-3.5 w-3.5" />
        </StatusTooltipBadge>
      )}
      {hasOncoKbCancerGene && (
        <StatusTooltipBadge
          href={oncokbGeneUrl(gene)}
          label="OncoKB cancer gene"
          description="The gene is present in the local OncoKB public cancer-gene cache. Open OncoKB for current public gene context."
          severity="info"
          ariaLabel="OncoKB public cancer gene"
          textBadge
        >
          OKB
        </StatusTooltipBadge>
      )}
      {hasOncoKbActionable && (
        <StatusTooltipBadge
          label="Local actionable evidence"
          description="Historical local OncoKB actionable evidence is available for this gene, including drug-level fields from the local cache."
          severity="warn"
          ariaLabel="Historical local OncoKB actionable evidence"
          textBadge
        >
          Rx
        </StatusTooltipBadge>
      )}
      {hasClinPgxGene && (
        <StatusTooltipBadge
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
        </StatusTooltipBadge>
      )}
    </div>
  )
}

function StatusTooltipBadge({
  children,
  label,
  description,
  severity,
  href,
  ariaLabel,
  textBadge = false,
  className,
}: {
  children: ReactNode
  label: string
  description: string
  severity: string
  href?: string
  ariaLabel: string
  textBadge?: boolean
  className?: string
}) {
  const [position, setPosition] = useState<{ left: number; top: number } | null>(null)
  const badgeClass = cn(
    textBadge
      ? "h-5 min-w-5 rounded-md px-1.5 text-[0.58rem] font-black leading-none"
      : "h-5 w-5 rounded-full p-0",
    "inline-flex cursor-help items-center justify-center border shadow-sm outline-none ring-offset-background transition-all duration-100 hover:-translate-y-0.5 hover:shadow-md focus:ring-2 focus:ring-ring/40",
    severityClass(severity),
    className,
  )
  const handlers = {
    onMouseEnter: (event: MouseEvent<HTMLElement>) => setPosition(belowOrAboveTooltipPosition(event)),
    onMouseMove: (event: MouseEvent<HTMLElement>) => setPosition(belowOrAboveTooltipPosition(event)),
    onMouseLeave: () => setPosition(null),
    onFocus: (event: FocusEvent<HTMLElement>) => setPosition(belowOrAboveTooltipPosition(event)),
    onBlur: () => setPosition(null),
  }
  const content = href ? (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className={badgeClass}
      aria-label={ariaLabel}
      tabIndex={0}
      {...handlers}
    >
      {children}
    </a>
  ) : (
    <span className={badgeClass} aria-label={ariaLabel} tabIndex={0} {...handlers}>
      {children}
    </span>
  )

  return (
    <span className="inline-flex">
      {content}
      {position && createPortal(
        <span
          className={cn(
            "pointer-events-none fixed z-[9999] w-72 rounded-lg border px-3 py-2 text-left text-xs shadow-lg",
            tooltipSeverityClass(severity),
          )}
          style={{ left: position.left, top: position.top }}
        >
          <span className="mb-1 block text-[10px] font-black uppercase tracking-wide opacity-80">Finding marker</span>
          <span className="block font-bold text-foreground">{label}</span>
          <span className="mt-1 block text-[11px] leading-relaxed text-foreground/75">{description}</span>
        </span>,
        document.body,
      )}
    </span>
  )
}

function severityClass(severity: string) {
  if (severity === "pass") {
    return "border-pass/35 bg-pass/12 text-pass"
  }
  if (severity === "fail") {
    return "border-fail/35 bg-fail/12 text-fail"
  }
  if (severity === "warn") {
    return "border-warn/45 bg-warn/14 text-warn"
  }
  if (severity === "info") {
    return "border-tier3/35 bg-tier3/12 text-tier3"
  }
  if (severity === "pgx") {
    return "border-fuchsia-300/70 bg-fuchsia-50 text-fuchsia-800 hover:bg-fuchsia-50 hover:text-fuchsia-800 dark:border-fuchsia-300/35 dark:bg-fuchsia-400/12 dark:text-fuchsia-200 dark:hover:bg-fuchsia-400/12 dark:hover:text-fuchsia-200"
  }
  if (severity === "neutral") {
    return "border-muted-foreground/25 bg-muted text-muted-foreground"
  }
  return "border-primary/30 bg-primary/10 text-primary"
}

function tooltipSeverityClass(severity: string) {
  if (severity === "pass") {
    return "border-pass/45 bg-popover text-pass"
  }
  if (severity === "fail") {
    return "border-fail/45 bg-popover text-fail"
  }
  if (severity === "warn") {
    return "border-warn/50 bg-popover text-warn"
  }
  if (severity === "info") {
    return "border-tier3/45 bg-popover text-tier3"
  }
  if (severity === "pgx") {
    return "border-fuchsia-300/70 bg-fuchsia-50 text-fuchsia-800 dark:border-fuchsia-300/35 dark:bg-fuchsia-950/90 dark:text-fuchsia-200"
  }
  if (severity === "neutral") {
    return "border-muted-foreground/35 bg-popover text-muted-foreground"
  }
  return "border-primary/40 bg-popover text-primary"
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

function tooltipPosition(event: MouseEvent | FocusEvent) {
  const viewportWidth = window.innerWidth
  const viewportHeight = window.innerHeight
  const rect = event.currentTarget.getBoundingClientRect()
  const width = 288
  const height = 124
  const gap = 8
  const edge = 8
  let left = rect.right + gap
  if (left + width > viewportWidth - edge) left = rect.left - width - gap
  if (left < edge) left = rect.left
  left = Math.min(Math.max(left, edge), Math.max(edge, viewportWidth - width - edge))

  let top = rect.top + rect.height / 2 - height / 2
  if (top + height > viewportHeight - edge) top = rect.bottom - height
  if (top < edge) top = rect.bottom + gap
  top = Math.min(Math.max(top, edge), Math.max(edge, viewportHeight - height - edge))
  return { left, top }
}

function belowOrAboveTooltipPosition(event: MouseEvent | FocusEvent) {
  const viewportWidth = window.innerWidth
  const viewportHeight = window.innerHeight
  const rect = event.currentTarget.getBoundingClientRect()
  const width = 288
  const height = 132
  const gap = 8
  const edge = 8

  let left = rect.left + rect.width / 2 - width / 2
  left = Math.min(Math.max(left, edge), Math.max(edge, viewportWidth - width - edge))

  const hasRoomBelow = rect.bottom + gap + height <= viewportHeight - edge
  const hasRoomAbove = rect.top - gap - height >= edge
  let top = hasRoomBelow || !hasRoomAbove ? rect.bottom + gap : rect.top - height - gap
  top = Math.min(Math.max(top, edge), Math.max(edge, viewportHeight - height - edge))

  return { left, top }
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
      onMouseEnter={(event) => setPosition(tooltipPosition(event))}
      onMouseMove={(event) => setPosition(tooltipPosition(event))}
      onMouseLeave={() => setPosition(null)}
      onFocus={(event) => setPosition(tooltipPosition(event))}
      onBlur={() => setPosition(null)}
    >
      <span
        tabIndex={0}
        className={cn(
          "inline-flex max-w-[128px] cursor-help truncate rounded-md border px-2 py-0.5 text-[0.7rem] font-black uppercase leading-5 shadow-sm outline-none ring-offset-background transition-colors duration-100 focus:ring-2 focus:ring-ring/40",
          severityClass(severity),
        )}
      >
        {label}
      </span>
      {position && createPortal(
        <span
          className={cn(
            "pointer-events-none fixed z-[9999] w-72 rounded-lg border px-3 py-2 text-left text-xs shadow-lg",
            tooltipSeverityClass(severity),
          )}
          style={{ left: position.left, top: position.top }}
        >
          <span className="mb-1 block text-[10px] font-black uppercase tracking-wide opacity-80">
            {severityLabel(severity)} filter
          </span>
          <span className="block break-words font-mono font-bold text-foreground">{flag}</span>
          <span className="mt-1 block text-[11px] leading-relaxed text-foreground/75">{description}</span>
        </span>,
        document.body,
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
  if (impact === "HIGH") return "border-fail/35 bg-fail/12 text-fail"
  if (impact === "MODERATE") return "border-warn/45 bg-warn/14 text-warn"
  if (impact === "LOW") return "border-pass/35 bg-pass/12 text-pass"
  if (impact === "MODIFIER") return "border-muted-foreground/25 bg-muted text-muted-foreground"
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
      onMouseEnter={(event) => setPosition(belowOrAboveTooltipPosition(event))}
      onMouseMove={(event) => setPosition(belowOrAboveTooltipPosition(event))}
      onMouseLeave={() => setPosition(null)}
      onFocus={(event) => setPosition(belowOrAboveTooltipPosition(event))}
      onBlur={() => setPosition(null)}
    >
      <span
        tabIndex={0}
        className={cn(
          "inline-flex cursor-help rounded-md border px-2 py-0.5 text-[0.72rem] font-black uppercase leading-5 shadow-sm outline-none ring-offset-background transition-colors duration-100 focus:ring-2 focus:ring-ring/40",
          impactClass(value),
        )}
      >
        {impact}
      </span>
      {position && createPortal(
        <span
          className={cn(
            "pointer-events-none fixed z-[9999] w-72 rounded-lg border px-3 py-2 text-left text-xs shadow-lg",
            tooltipSeverityClass(severity),
          )}
          style={{ left: position.left, top: position.top }}
        >
          <span className="mb-1 block text-[10px] font-black uppercase tracking-wide opacity-80">VEP impact</span>
          <span className="block font-bold text-foreground">{impact}</span>
          <span className="mt-1 block text-[11px] leading-relaxed text-foreground/75">{impactDescription(value)}</span>
        </span>,
        document.body,
      )}
    </span>
  )
}

export function CallerBadges({ value }: { value: unknown }) {
  const callers = normalizedCallerList(value)
  if (!callers.length) return null

  return (
    <>
      {callers.map((caller) => (
        <span key={caller} className="soft-chip bg-primary/10 text-primary">
          {caller}
        </span>
      ))}
    </>
  )
}

function predictionSeverity(value: unknown) {
  const text = String(value || "").toLowerCase()
  if (!text) return "neutral"
  if (text.includes("deleterious") || text.includes("damaging") || text.includes("probably")) return "fail"
  if (text.includes("possibly") || text.includes("low_confidence")) return "warn"
  if (text.includes("tolerated") || text.includes("benign")) return "pass"
  return "info"
}

function predictionLabel(value: unknown) {
  const text = String(value || "").toLowerCase()
  if (text.includes("deleterious")) return "Deleterious"
  if (text.includes("probably") || text.includes("damaging")) return "Damaging"
  if (text.includes("possibly")) return "Possibly damaging"
  if (text.includes("low_confidence")) return "Low confidence"
  if (text.includes("tolerated")) return "Tolerated"
  if (text.includes("benign")) return "Benign"
  return "Prediction"
}

function predictionDescription(value: unknown) {
  const text = String(value || "").toLowerCase()
  if (text.includes("deleterious")) {
    return "SIFT predicts that the amino-acid substitution is likely to affect protein function."
  }
  if (text.includes("probably")) {
    return "PolyPhen predicts a probably damaging protein effect. Treat this as supporting computational evidence, not as a standalone classification."
  }
  if (text.includes("damaging")) {
    return "The prediction suggests a damaging protein effect. Use together with clinical, population, and assay evidence."
  }
  if (text.includes("possibly")) {
    return "PolyPhen predicts a possible damaging effect, with lower confidence than a probably damaging call."
  }
  if (text.includes("low_confidence")) {
    return "The prediction is low confidence and should be interpreted cautiously."
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
      onMouseEnter={(event) => setPosition(belowOrAboveTooltipPosition(event))}
      onMouseMove={(event) => setPosition(belowOrAboveTooltipPosition(event))}
      onMouseLeave={() => setPosition(null)}
      onFocus={(event) => setPosition(belowOrAboveTooltipPosition(event))}
      onBlur={() => setPosition(null)}
    >
      <span
        tabIndex={0}
        className={cn(
          "inline-flex cursor-help rounded-md border px-2 py-0.5 text-[0.72rem] font-bold leading-5 shadow-sm outline-none ring-offset-background transition-colors duration-100 focus:ring-2 focus:ring-ring/40",
          severityClass(severity),
        )}
      >
        {String(value)}
      </span>
      {position && createPortal(
        <span
          className={cn(
            "pointer-events-none fixed z-[9999] w-72 rounded-lg border px-3 py-2 text-left text-xs shadow-lg",
            tooltipSeverityClass(severity),
          )}
          style={{ left: position.left, top: position.top }}
        >
          <span className="mb-1 block text-[10px] font-black uppercase tracking-wide opacity-80">Protein prediction</span>
          <span className="block font-bold text-foreground">{predictionLabel(value)}</span>
          <span className="mt-1 block break-words font-mono text-[11px] font-semibold text-foreground/85">{String(value)}</span>
          <span className="mt-1 block text-[11px] leading-relaxed text-foreground/75">{predictionDescription(value)}</span>
        </span>,
        document.body,
      )}
    </span>
  )
}

function consequenceMeta(term: string, translations?: Record<string, any>) {
  return translations?.[term] || {}
}

function ConsequenceBadge({
  term,
  translations,
  compact,
}: {
  term: string
  translations?: Record<string, any>
  compact: boolean
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
      onMouseEnter={(event) => setPosition(belowOrAboveTooltipPosition(event))}
      onMouseMove={(event) => setPosition(belowOrAboveTooltipPosition(event))}
      onMouseLeave={() => setPosition(null)}
      onFocus={(event) => setPosition(belowOrAboveTooltipPosition(event))}
      onBlur={() => setPosition(null)}
    >
      <span
        tabIndex={0}
        className={cn(
          "max-w-[108px] cursor-help truncate rounded-md border px-2 py-0.5 text-[0.72rem] font-bold lowercase leading-5 shadow-sm outline-none ring-offset-background transition-colors duration-100 focus:ring-2 focus:ring-ring/40",
          impact ? severityClass(severity) : "border-border bg-muted text-foreground",
        )}
      >
        {compact ? label : term}
      </span>
      {position && createPortal(
        <span
          className={cn(
            "pointer-events-none fixed z-[9999] w-72 rounded-lg border px-3 py-2 text-left text-xs shadow-lg",
            impact ? tooltipSeverityClass(severity) : "border-border bg-popover text-popover-foreground",
          )}
          style={{ left: position.left, top: position.top }}
        >
          <span className="mb-1 flex items-center justify-between gap-2 text-[10px] font-black uppercase tracking-wide opacity-80">
            <span>VEP consequence</span>
            {impact && <ImpactBadge value={impact} />}
          </span>
          <span className="block font-mono font-bold text-foreground">{term}</span>
          <span className="mt-1 block text-[11px] leading-relaxed text-foreground/75">{description}</span>
        </span>,
        document.body,
      )}
    </span>
  )
}

export function ConsequenceBadges({
  value,
  translations,
  compact = true,
}: {
  value: unknown
  translations?: Record<string, any>
  compact?: boolean
}) {
  const terms = Array.isArray(value) ? value : String(value || "").split(/[,&]/).filter(Boolean)
  if (!terms.length) return <span className="text-muted-foreground">-</span>
  return (
    <div className="flex max-w-[220px] flex-wrap items-center gap-1">
      {terms.map((term) => (
        <ConsequenceBadge
          key={String(term)}
          term={String(term)}
          translations={translations}
          compact={compact}
        />
      ))}
    </div>
  )
}
