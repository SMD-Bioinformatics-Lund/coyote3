import { AlertCircle, Ban, Bookmark, MessageSquare, ShieldCheck, XCircle, XSquare } from "lucide-react"
import { useState, type FocusEvent, type MouseEvent, type ReactNode } from "react"
import { TooltipSurface } from "@/components/ui/app-tooltip"
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
      {position && (
        <TooltipSurface position={position} className={tooltipSeverityClass(meta.severity)}>
          <span className="mb-1 block text-[10px] font-black uppercase tracking-wide opacity-80">
            Tier {meta.roman}
          </span>
          <span className="block font-bold text-foreground">{meta.short}</span>
          <span className="mt-1 block text-[11px] leading-relaxed text-foreground/75">{meta.description}</span>
        </TooltipSurface>
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
  const isNoteworthy = Boolean(finding?.noteworthy)
  const isNormalCall = finding?.NORMAL === 1 || finding?.NORMAL === true
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
      {isNoteworthy && (
        <StatusTooltipBadge
          label="Noteworthy"
          description="This finding has been marked for additional reviewer attention without automatically including it in the report."
          severity="warn"
          ariaLabel="Noteworthy"
        >
          <Bookmark className="h-3.5 w-3.5" />
        </StatusTooltipBadge>
      )}
      {isNormalCall && (
        <StatusTooltipBadge
          label="Normal/control call"
          description="This CNV record was emitted for the normal or control genome. Whole-genome workflows retain these records for paired review."
          severity="neutral"
          ariaLabel="Normal or control CNV"
          textBadge
        >
          N
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

type ArtefactFrequencyItem = {
  key: string
  label: string
  frequency: number
  percent: number
  count: unknown
}

function artefactFrequencyItems(finding: any): ArtefactFrequencyItem[] {
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
export function ArtefactFrequencyBadges({ finding }: { finding: any }) {
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
          <StatusTooltipBadge
            key={item.key}
            label={`${item.label} artefact frequency`}
            description={`Observed frequency: ${item.percent.toFixed(1)}%.${countText} This evidence is supplied by the upstream CNV pipeline; Coyote displays it but does not recalculate it.`}
            severity={severity}
            ariaLabel={`${item.label} artefact frequency ${item.percent.toFixed(1)} percent`}
            textBadge
            contextLabel="CNV artefact evidence"
          >
            {item.label}
          </StatusTooltipBadge>
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
    <StatusTooltipBadge
      label={label}
      description={description}
      severity={severity}
      href={href}
      ariaLabel={ariaLabel || label}
      textBadge
      contextLabel={contextLabel}
      className={className}
    >
      {children}
    </StatusTooltipBadge>
  )
}

const fusionCallerDescriptions: Record<string, string> = {
  arriba: "Fusion call emitted by Arriba.",
  fusioncatcher: "Fusion call emitted by FusionCatcher.",
  starfusion: "Fusion call emitted by STAR-Fusion.",
}

/** Render fusion callers independently from DNA variant callers. */
export function FusionCallerBadges({ callers }: { callers: unknown }) {
  const values = normalizedCallerList(callers)
    .map((caller) => caller.toLowerCase())
    .filter((caller, index, items) => items.indexOf(caller) === index)
  if (!values.length) return <span className="text-muted-foreground">-</span>

  return (
    <div className="flex flex-wrap gap-1">
      {values.map((caller) => (
        <InfoTooltipBadge
          key={caller}
          label={caller}
          description={fusionCallerDescriptions[caller] || "Fusion caller reported by the upstream RNA analysis pipeline."}
          severity="info"
          contextLabel="Fusion caller"
        >
          {caller}
        </InfoTooltipBadge>
      ))}
    </div>
  )
}

function fusionEffectDescription(effect: string) {
  const normalized = effect.toLowerCase()
  if (normalized === "in-frame") {
    return "The selected fusion call is predicted to preserve the coding reading frame. This value is supplied by the fusion caller, not recalculated by Coyote3."
  }
  return `The fusion caller reported "${effect}". In the RNA review model, every non-empty effect other than the exact in-frame value is treated as out-of-frame.`
}

/** Render caller-authored fusion effect/frame context with provenance-aware help. */
export function FusionEffectBadge({ effect }: { effect: unknown }) {
  const value = String(effect || "").trim()
  if (!value) return <span className="text-muted-foreground">-</span>
  const normalized = value.toLowerCase()
  const severity = normalized === "in-frame" ? "pass" : "fail"
  return (
    <InfoTooltipBadge
      label={value}
      description={fusionEffectDescription(value)}
      severity={severity}
      contextLabel="Caller-reported fusion effect"
      className="h-auto min-h-5 max-w-full whitespace-normal text-left leading-tight"
    >
      {value}
    </InfoTooltipBadge>
  )
}

const fusionEvidenceDescriptions: Record<string, string> = {
  cancer: "The upstream caller marked this fusion with cancer-associated evidence.",
  oncogene: "The upstream caller associated one or both partners with an oncogene reference set.",
  reciprocal: "The upstream caller marked evidence for a reciprocal fusion configuration.",
  ribosomal: "The upstream caller marked a ribosomal-gene association.",
  tumor: "The upstream caller marked tumor-associated reference evidence.",
  "exon-exon": "The upstream caller marked an exon-to-exon breakpoint pattern.",
  polya: "The upstream caller marked sequence evidence involving a poly-A region.",
  polyt: "The upstream caller marked sequence evidence involving a poly-T region.",
}

export type FusionAnnotationMetadata = {
  important?: string[]
  not_important?: string[]
  context?: string[]
}

function fusionEvidenceMetadata(value: string, metadata: FusionAnnotationMetadata) {
  const normalized = value.toLowerCase()
  const configuredDescription = fusionEvidenceDescriptions[normalized]
  if ((metadata.important || []).includes(normalized)) {
    return {
      severity: "pass",
      description: configuredDescription || "The upstream caller associated this fusion with a cancer or curated fusion reference set. This is supporting caller evidence, not a Coyote3 clinical classification.",
    }
  }
  if ((metadata.not_important || []).includes(normalized)) {
    return {
      severity: "fail",
      description: configuredDescription || "The upstream caller associated this fusion with a normal-tissue, recurrent-artifact, overlap, or sequence-similarity reference set. Review this artifact evidence before interpretation.",
    }
  }
  if ((metadata.context || []).includes(normalized)) {
    return {
      severity: "neutral",
      description: configuredDescription || "The upstream caller reported contextual fusion evidence. Review the breakpoints and supporting reads together with this annotation.",
    }
  }
  return {
    severity: "neutral",
    description: configuredDescription || "Caller-specific evidence tag retained verbatim from the selected fusion call. Its vocabulary may vary by caller and caller database version.",
  }
}

/** Display selected-call evidence tags while preserving the complete raw description. */
export function FusionEvidenceBadges({
  description,
  metadata = {},
}: {
  description: unknown
  metadata?: FusionAnnotationMetadata
}) {
  const raw = String(description || "").trim()
  if (!raw) return <span className="text-muted-foreground">-</span>
  const values = raw.split(",").map((value) => value.trim()).filter(Boolean)
  const visible = values.slice(0, 3)
  return (
    <div className="flex max-w-full flex-wrap gap-1" aria-label={`Fusion evidence: ${raw}`}>
      {visible.map((value, index) => {
        const badgeMetadata = fusionEvidenceMetadata(value, metadata)
        return (
          <InfoTooltipBadge
            key={`${value}-${index}`}
            label={value}
            description={badgeMetadata.description}
            severity={badgeMetadata.severity}
            contextLabel="Fusion evidence"
          >
            {value}
          </InfoTooltipBadge>
        )
      })}
      {values.length > visible.length && (
        <InfoTooltipBadge
          label={`${values.length - visible.length} additional evidence tags`}
          description={values.slice(visible.length).join(", ")}
          severity="neutral"
          contextLabel="Fusion evidence"
        >
          +{values.length - visible.length}
        </InfoTooltipBadge>
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
  contextLabel = "Finding marker",
}: {
  children: ReactNode
  label: string
  description: string
  severity: string
  href?: string
  ariaLabel: string
  textBadge?: boolean
  className?: string
  contextLabel?: string
}) {
  const [position, setPosition] = useState<{ left: number; top: number } | null>(null)
  const badgeClass = cn(
    textBadge
      ? "h-5 min-w-5 rounded-md px-2 text-[0.68rem] font-bold leading-none"
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
      {position && (
        <TooltipSurface position={position} className={tooltipSeverityClass(severity)}>
          <span className="mb-1 block text-[10px] font-black uppercase tracking-wide opacity-80">{contextLabel}</span>
          <span className="block font-bold text-foreground">{label}</span>
          <span className="mt-1 block text-[11px] leading-relaxed text-foreground/75">{description}</span>
        </TooltipSurface>
      )}
    </span>
  )
}

function severityClass(severity: string) {
  if (severity === "pass") {
    return "matte-badge-pass"
  }
  if (severity === "fail") {
    return "matte-badge-fail"
  }
  if (severity === "warn") {
    return "matte-badge-warn"
  }
  if (severity === "info") {
    return "matte-badge-info"
  }
  if (severity === "success") {
    return "matte-badge-pass"
  }
  if (severity === "pgx") {
    return "badge-pgx"
  }
  if (severity === "neutral") {
    return "matte-badge-neutral"
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
  if (severity === "success") {
    return "border-pass/45 bg-popover text-pass"
  }
  if (severity === "pgx") {
    return "badge-pgx"
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
      {position && (
        <TooltipSurface position={position} className={tooltipSeverityClass(severity)}>
          <span className="mb-1 block text-[10px] font-black uppercase tracking-wide opacity-80">
            {severityLabel(severity)} filter
          </span>
          <span className="block break-words font-mono font-bold text-foreground">{flag}</span>
          <span className="mt-1 block text-[11px] leading-relaxed text-foreground/75">{description}</span>
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
      {position && (
        <TooltipSurface position={position} className={tooltipSeverityClass(severity)}>
          <span className="mb-1 block text-[10px] font-black uppercase tracking-wide opacity-80">VEP impact</span>
          <span className="block font-bold text-foreground">{impact}</span>
          <span className="mt-1 block text-[11px] leading-relaxed text-foreground/75">{impactDescription(value)}</span>
        </TooltipSurface>
      )}
    </span>
  )
}

export function CallerBadges({ value }: { value: unknown }) {
  const callers = Array.from(new Set(normalizedCallerList(value)))
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
      {position && (
        <TooltipSurface position={position} className={tooltipSeverityClass(severity)}>
          <span className="mb-1 block text-[10px] font-black uppercase tracking-wide opacity-80">Protein prediction</span>
          <span className="block font-bold text-foreground">{predictionLabel(value)}</span>
          <span className="mt-1 block break-words font-mono text-[11px] font-semibold text-foreground/85">{String(value)}</span>
          <span className="mt-1 block text-[11px] leading-relaxed text-foreground/75">{predictionDescription(value)}</span>
        </TooltipSurface>
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
  wide,
}: {
  term: string
  translations?: Record<string, any>
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
      onMouseEnter={(event) => setPosition(belowOrAboveTooltipPosition(event))}
      onMouseMove={(event) => setPosition(belowOrAboveTooltipPosition(event))}
      onMouseLeave={() => setPosition(null)}
      onFocus={(event) => setPosition(belowOrAboveTooltipPosition(event))}
      onBlur={() => setPosition(null)}
    >
      <span
        tabIndex={0}
        className={cn(
          "cursor-help rounded-md border px-2 py-0.5 text-[0.68rem] font-bold lowercase leading-5 shadow-sm outline-none ring-offset-background transition-colors duration-100 focus:ring-2 focus:ring-ring/40",
          wide ? "max-w-[280px] whitespace-normal break-words" : "max-w-[108px] truncate",
          impact ? severityClass(severity) : "border-border bg-muted text-foreground",
        )}
      >
        {compact ? label : term}
      </span>
      {position && (
        <TooltipSurface
          position={position}
          className={impact ? tooltipSeverityClass(severity) : "border-border text-popover-foreground"}
        >
          <span className="mb-1 flex items-center justify-between gap-2 text-[10px] font-black uppercase tracking-wide opacity-80">
            <span>VEP consequence</span>
            {impact && <ImpactBadge value={impact} />}
          </span>
          <span className="block font-mono font-bold text-foreground">{term}</span>
          <span className="mt-1 block text-[11px] leading-relaxed text-foreground/75">{description}</span>
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
  translations?: Record<string, any>
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
