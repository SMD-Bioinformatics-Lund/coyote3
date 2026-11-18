// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import type { FocusEvent, MouseEvent } from "react"

export type TooltipPosition = {
  left: number
  top: number
  anchor?: "pointer"
  bounds?: Pick<DOMRect, "left" | "right" | "top" | "bottom">
}

export type TooltipTone = "info" | "success" | "warning" | "danger" | "neutral"

export function tooltipToneClass(tone: string) {
  if (tone === "success" || tone === "pass") return "border-pass/45 text-pass"
  if (tone === "warning" || tone === "warn") return "border-warn/50 text-warn"
  if (tone === "danger" || tone === "fail") return "border-fail/45 text-fail"
  if (tone === "neutral") return "border-muted-foreground/35 text-muted-foreground"
  return "border-tier3/45 text-tier3"
}

/** Use viewport coordinates for both pointer and keyboard-triggered hints. */
export function tooltipElementPosition(target: HTMLElement): TooltipPosition {
  const { left, right, top, bottom } = target.getBoundingClientRect()
  return { left, top: bottom, bounds: { left, right, top, bottom } }
}

export function tooltipEventPosition(event: MouseEvent<HTMLElement> | FocusEvent<HTMLElement>): TooltipPosition {
  return "clientX" in event
    ? { left: event.clientX, top: event.clientY, anchor: "pointer" }
    : tooltipElementPosition(event.currentTarget)
}
