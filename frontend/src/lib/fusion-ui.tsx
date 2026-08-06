import { normalizedCallerList } from "@/lib/variant-helpers"
import { InfoTooltipBadge } from "@/lib/variant-ui"

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
