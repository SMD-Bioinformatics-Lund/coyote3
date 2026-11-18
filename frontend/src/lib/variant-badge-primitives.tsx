// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

/* eslint-disable react/only-export-components -- shared badge primitives export components, styles, and positioning helpers together. */

import { useState, type FocusEvent, type MouseEvent, type ReactNode } from "react"
import { TooltipSurface } from "@/components/ui/app-tooltip"
import { tooltipToneClass, tooltipEventPosition, type TooltipPosition } from "@/components/ui/app-tooltip-meta"
import {
  clinicalBadgeClassName,
  InfoBadge,
  TableBadge,
} from "@/components/ui/table-badge"
import { cn } from "@/lib/utils"


export function VariantTooltipBadge({
  children,
  label,
  description,
  severity,
  href,
  ariaLabel,
  textBadge = false,
  textBadgeSize = "info",
  className,
  appearanceClassName,
  contextLabel = "Finding marker",
}: {
  children: ReactNode
  label: string
  description: string
  severity: string
  href?: string
  ariaLabel: string
  textBadge?: boolean
  textBadgeSize?: "info" | "clinical"
  className?: string
  appearanceClassName?: string
  contextLabel?: string
}) {
  const [position, setPosition] = useState<TooltipPosition | null>(null)
  const badgeClass = cn(
    !textBadge && "h-5 w-5 rounded-full p-0",
    "interaction-transition inline-flex cursor-help items-center justify-center border shadow-[var(--material-badge-shadow)] outline-none ring-offset-background hover:-translate-y-0.5 hover:shadow-md focus:ring-2 focus:ring-ring/40",
    appearanceClassName || badgeSeverityClass(severity),
    className,
  )
  const handlers = {
    onMouseEnter: (event: MouseEvent<HTMLElement>) => setPosition(tooltipEventPosition(event)),
    onMouseMove: (event: MouseEvent<HTMLElement>) => { if (position) setPosition(tooltipEventPosition(event)) },
    onMouseLeave: () => setPosition(null),
    onFocus: (event: FocusEvent<HTMLElement>) => setPosition(tooltipEventPosition(event)),
    onBlur: () => setPosition(null),
  }
  const TextBadge = textBadgeSize === "clinical" ? TableBadge : InfoBadge
  const content = textBadge ? (
    <TextBadge
      as={href ? "a" : "span"}
      href={href}
      target={href ? "_blank" : undefined}
      rel={href ? "noreferrer" : undefined}
      className={cn(textBadgeSize === "clinical" && clinicalBadgeClassName, badgeClass)}
      aria-label={ariaLabel}
      tabIndex={0}
      {...handlers}
    >
      {children}
    </TextBadge>
  ) : (
    <span data-slot="table-badge" className={badgeClass} aria-label={ariaLabel} tabIndex={0} {...handlers}>
      {children}
    </span>
  )

  return (
    <span className="inline-flex" data-tooltip-managed="true">
      {content}
      {position && (
        <TooltipSurface position={position} onDismiss={() => setPosition(null)} className={tooltipSeverityClass(severity)}>
          <span className="mb-1 block type-label font-semibold uppercase tracking-wide opacity-80">{contextLabel}</span>
          <span className="block font-bold text-foreground">{label}</span>
          <span className="mt-1 block type-meta leading-relaxed text-foreground/75">{description}</span>
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
  if (severity === "pgx") return "badge-pgx"
  if (["pass", "success", "fail", "danger", "warn", "warning", "info", "neutral"].includes(severity)) {
    return `bg-popover ${tooltipToneClass(severity)}`
  }
  return "border-primary/40 bg-popover text-primary"
}
