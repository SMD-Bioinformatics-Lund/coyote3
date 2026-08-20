import { Flame } from "lucide-react"

import { AppTooltip } from "@/components/ui/app-tooltip"
import { clinicalBadgeClassName, TableBadge } from "@/components/ui/table-badge"
import { variantHotspotEntries } from "@/lib/variant-table-format"
import { cn } from "@/lib/utils"

const HOTSPOT_SOURCE_LABELS: Record<string, string> = {
  cns: "CNS",
  co: "Colon",
  d: "DNA panel",
  gi: "Gastrointestinal",
  lu: "Lung",
  mm: "Melanoma",
}

export function HotspotIndicator({
  variant,
  showLabel = false,
  className,
}: {
  variant: any
  showLabel?: boolean
  className?: string
}) {
  const hotspots = variantHotspotEntries(variant)
  if (!hotspots.length) return <span className="type-table-value text-muted-foreground">-</span>

  const sourceCount = hotspots.length
  const identifierCount = hotspots.reduce((total, hotspot) => total + hotspot.identifiers.length, 0)
  const summary = `${sourceCount} hotspot source${sourceCount === 1 ? "" : "s"}${identifierCount ? `, ${identifierCount} identifier${identifierCount === 1 ? "" : "s"}` : ""}`

  return (
    <AppTooltip
      tone="warning"
      context="Hotspot evidence"
      label="Known hotspot"
      content={summary}
      details={(
        <div className="mt-2 space-y-2 border-t border-current/15 pt-2">
          {hotspots.map(({ source, identifiers }) => (
            <div key={source} className="grid grid-cols-[5.5rem_minmax(0,1fr)] gap-2">
              <span className="text-[10px] font-semibold uppercase tracking-wide opacity-70">
                {HOTSPOT_SOURCE_LABELS[source.toLowerCase()] || source}
              </span>
              <div className="flex min-w-0 flex-wrap gap-1">
                {identifiers.length ? identifiers.map((identifier) => (
                  <span
                    key={identifier}
                    className="rounded border border-current/20 bg-background/65 px-1.5 py-0.5 text-[10px] font-medium text-foreground"
                  >
                    {identifier}
                  </span>
                )) : (
                  <span className="text-[10px] text-popover-foreground/70">Source match</span>
                )}
              </div>
            </div>
          ))}
          <p className="text-[10px] leading-relaxed opacity-70">
            Only the latest COSMIC identifier is shown for each source.
          </p>
        </div>
      )}
    >
      <TableBadge
        tabIndex={0}
        aria-label="Known hotspot"
        className={cn(clinicalBadgeClassName, "matte-badge-warn gap-1", className)}
      >
        <Flame className="h-3.5 w-3.5" aria-hidden="true" />
        {showLabel ? <span>Hotspot</span> : null}
      </TableBadge>
    </AppTooltip>
  )
}
