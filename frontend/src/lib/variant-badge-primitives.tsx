/* eslint-disable react/only-export-components -- shared badge primitives export components, styles, and positioning helpers together. */

import { useState, type FocusEvent, type MouseEvent, type ReactNode } from "react"
import { TooltipSurface } from "@/components/ui/app-tooltip"
import { InfoBadge } from "@/components/ui/table-badge"
import { cn } from "@/lib/utils"

type TooltipPosition = { left: number; top: number }

export function VariantTooltipBadge({
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
  const [position, setPosition] = useState<TooltipPosition | null>(null)
  const badgeClass = cn(
    !textBadge && "h-5 w-5 rounded-full p-0",
    "inline-flex cursor-help items-center justify-center border shadow-sm outline-none ring-offset-background transition-all duration-100 hover:-translate-y-0.5 hover:shadow-md focus:ring-2 focus:ring-ring/40",
    badgeSeverityClass(severity),
    className,
  )
  const handlers = {
    onMouseEnter: (event: MouseEvent<HTMLElement>) => setPosition(verticalTooltipPosition(event)),
    onMouseMove: (event: MouseEvent<HTMLElement>) => setPosition(verticalTooltipPosition(event)),
    onMouseLeave: () => setPosition(null),
    onFocus: (event: FocusEvent<HTMLElement>) => setPosition(verticalTooltipPosition(event)),
    onBlur: () => setPosition(null),
  }
  const content = textBadge ? (
    <InfoBadge
      as={href ? "a" : "span"}
      href={href}
      target={href ? "_blank" : undefined}
      rel={href ? "noreferrer" : undefined}
      className={badgeClass}
      aria-label={ariaLabel}
      tabIndex={0}
      {...handlers}
    >
      {children}
    </InfoBadge>
  ) : (
    <span className={badgeClass} aria-label={ariaLabel} tabIndex={0} {...handlers}>
      {children}
    </span>
  )

  return (
    <span className="inline-flex" data-tooltip-managed="true">
      {content}
      {position && (
        <TooltipSurface position={position} className={tooltipSeverityClass(severity)}>
          <span className="mb-1 block text-[10px] font-semibold uppercase tracking-wide opacity-80">{contextLabel}</span>
          <span className="block font-bold text-foreground">{label}</span>
          <span className="mt-1 block text-[11px] leading-relaxed text-foreground/75">{description}</span>
        </TooltipSurface>
      )}
    </span>
  )
}

export function badgeSeverityClass(severity: string) {
  if (severity === "pass" || severity === "success") return "matte-badge-pass"
  if (severity === "fail") return "matte-badge-fail"
  if (severity === "warn") return "matte-badge-warn"
  if (severity === "info") return "matte-badge-info"
  if (severity === "pgx") return "badge-pgx"
  if (severity === "neutral") return "matte-badge-neutral"
  return "border-primary/30 bg-primary/10 text-primary"
}

export function tooltipSeverityClass(severity: string) {
  if (severity === "pass" || severity === "success") return "border-pass/45 bg-popover text-pass"
  if (severity === "fail") return "border-fail/45 bg-popover text-fail"
  if (severity === "warn") return "border-warn/50 bg-popover text-warn"
  if (severity === "info") return "border-tier3/45 bg-popover text-tier3"
  if (severity === "pgx") return "badge-pgx"
  if (severity === "neutral") return "border-muted-foreground/35 bg-popover text-muted-foreground"
  return "border-primary/40 bg-popover text-primary"
}

export function inlineTooltipPosition(event: MouseEvent | FocusEvent): TooltipPosition {
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

export function verticalTooltipPosition(event: MouseEvent | FocusEvent): TooltipPosition {
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
