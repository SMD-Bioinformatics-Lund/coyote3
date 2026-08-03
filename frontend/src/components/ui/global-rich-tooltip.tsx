import { useEffect, useRef, useState } from "react"
import { createPortal } from "react-dom"
import { cn } from "@/lib/utils"

type TooltipState = {
  target: HTMLElement
  title: string
  label: string
  context: string
  left: number
  top: number
  tone: string
}

const TOOLTIP_WIDTH = 288
const TOOLTIP_HEIGHT = 96
const CURSOR_GAP = 14
const VIEWPORT_MARGIN = 12
const TOOLTIP_ID = "global-rich-tooltip"

function isTooltipTarget(value: EventTarget | null): value is HTMLElement {
  return value instanceof HTMLElement
}

function eligibleTarget(value: EventTarget | null) {
  if (!isTooltipTarget(value)) return null
  const target = value.closest<HTMLElement>("[title]:not(iframe)")
  if (!target || target.dataset.nativeTitle === "true") return null
  return target
}

function tooltipPosition(clientX: number, clientY: number) {
  const rightSpace = window.innerWidth - clientX
  const bottomSpace = window.innerHeight - clientY
  const left = rightSpace >= TOOLTIP_WIDTH + CURSOR_GAP + VIEWPORT_MARGIN
    ? clientX + CURSOR_GAP
    : Math.max(VIEWPORT_MARGIN, clientX - TOOLTIP_WIDTH - CURSOR_GAP)
  const top = bottomSpace >= TOOLTIP_HEIGHT + CURSOR_GAP + VIEWPORT_MARGIN
    ? clientY + CURSOR_GAP
    : Math.max(VIEWPORT_MARGIN, clientY - TOOLTIP_HEIGHT - CURSOR_GAP)
  return { left, top }
}

function focusPosition(target: HTMLElement) {
  const rect = target.getBoundingClientRect()
  return tooltipPosition(rect.left + Math.min(rect.width / 2, 24), rect.bottom)
}

function tooltipToneClass(tone: string) {
  if (tone === "success") return "border-pass/45 text-pass"
  if (tone === "warning") return "border-warn/50 text-warn"
  if (tone === "danger") return "border-fail/45 text-fail"
  if (tone === "neutral") return "border-muted-foreground/35 text-muted-foreground"
  return "border-info/45 text-info"
}

function tooltipLabel(target: HTMLElement, title: string) {
  return target.dataset.tooltipLabel || target.getAttribute("aria-label") || title
}

function tooltipContext(target: HTMLElement) {
  return target.dataset.tooltipContext || "More information"
}

/**
 * Upgrades concise native title hints to the shared application tooltip surface.
 * Rich clinical badges continue to render their domain-specific descriptions.
 */
export function GlobalRichTooltip() {
  const [tooltip, setTooltip] = useState<TooltipState | null>(null)
  const activeTarget = useRef<HTMLElement | null>(null)
  const previousDescribedBy = useRef<string | null>(null)

  useEffect(() => {
    const restoreTarget = () => {
      const target = activeTarget.current
      if (!target) return
      const originalTitle = target.dataset.richTooltipTitle
      if (originalTitle && !target.hasAttribute("title")) target.setAttribute("title", originalTitle)
      delete target.dataset.richTooltipTitle
      if (previousDescribedBy.current) target.setAttribute("aria-describedby", previousDescribedBy.current)
      else target.removeAttribute("aria-describedby")
      activeTarget.current = null
      previousDescribedBy.current = null
    }

    const activate = (target: HTMLElement, left: number, top: number) => {
      if (activeTarget.current !== target) {
        restoreTarget()
        const title = target.getAttribute("title")
        if (!title) return
        activeTarget.current = target
        previousDescribedBy.current = target.getAttribute("aria-describedby")
        target.dataset.richTooltipTitle = title
        target.removeAttribute("title")
        target.setAttribute("aria-describedby", TOOLTIP_ID)
      }
      const title = target.dataset.richTooltipTitle
      if (!title) return
      setTooltip({
        target,
        title,
        label: tooltipLabel(target, title),
        context: tooltipContext(target),
        left,
        top,
        tone: target.dataset.tooltipTone || "info",
      })
    }

    const close = () => {
      setTooltip(null)
      restoreTarget()
    }

    const onPointerOver = (event: PointerEvent) => {
      const target = eligibleTarget(event.target)
      if (!target) return
      const position = tooltipPosition(event.clientX, event.clientY)
      activate(target, position.left, position.top)
    }
    const onPointerMove = (event: PointerEvent) => {
      if (!activeTarget.current) return
      const position = tooltipPosition(event.clientX, event.clientY)
      setTooltip((current) => current ? { ...current, ...position } : current)
    }
    const onPointerOut = (event: PointerEvent) => {
      const target = activeTarget.current
      if (!target) return
      if (isTooltipTarget(event.relatedTarget) && target.contains(event.relatedTarget)) return
      close()
    }
    const onFocusIn = (event: FocusEvent) => {
      const target = eligibleTarget(event.target)
      if (!target) return
      const position = focusPosition(target)
      activate(target, position.left, position.top)
    }
    const onFocusOut = (event: FocusEvent) => {
      const target = activeTarget.current
      if (!target) return
      if (isTooltipTarget(event.relatedTarget) && target.contains(event.relatedTarget)) return
      close()
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") close()
    }

    document.addEventListener("pointerover", onPointerOver, true)
    document.addEventListener("pointermove", onPointerMove, true)
    document.addEventListener("pointerout", onPointerOut, true)
    document.addEventListener("focusin", onFocusIn, true)
    document.addEventListener("focusout", onFocusOut, true)
    document.addEventListener("keydown", onKeyDown, true)
    window.addEventListener("scroll", close, true)
    window.addEventListener("resize", close)
    return () => {
      document.removeEventListener("pointerover", onPointerOver, true)
      document.removeEventListener("pointermove", onPointerMove, true)
      document.removeEventListener("pointerout", onPointerOut, true)
      document.removeEventListener("focusin", onFocusIn, true)
      document.removeEventListener("focusout", onFocusOut, true)
      document.removeEventListener("keydown", onKeyDown, true)
      window.removeEventListener("scroll", close, true)
      window.removeEventListener("resize", close)
      restoreTarget()
    }
  }, [])

  if (!tooltip) return null

  return createPortal(
    <div
      id={TOOLTIP_ID}
      role="tooltip"
      className={cn(
        "pointer-events-none fixed z-[10000] w-72 rounded-lg border bg-popover px-3 py-2 text-left shadow-xl",
        tooltipToneClass(tooltip.tone),
      )}
      style={{ left: tooltip.left, top: tooltip.top }}
      data-tooltip-for={tooltip.target.tagName.toLowerCase()}
    >
      <span className="mb-1 block text-[10px] font-black uppercase tracking-wide opacity-80">{tooltip.context}</span>
      <span className="block text-xs font-bold text-popover-foreground">{tooltip.label}</span>
      {tooltip.label !== tooltip.title && (
        <span className="mt-1 block text-[11px] leading-relaxed text-popover-foreground/75">{tooltip.title}</span>
      )}
    </div>,
    document.body,
  )
}
