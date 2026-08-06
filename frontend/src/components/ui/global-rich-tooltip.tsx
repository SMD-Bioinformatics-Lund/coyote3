import { useEffect, useRef, useState } from "react"
import { TooltipSurface } from "@/components/ui/app-tooltip"
import { tooltipToneClass } from "@/components/ui/app-tooltip-meta"

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

function isTooltipTarget(value: EventTarget | null): value is Element {
  return value instanceof Element
}

function eligibleTarget(value: EventTarget | null) {
  if (!isTooltipTarget(value)) return null
  // A domain component inside this subtree owns the complete tooltip lifecycle.
  // Do not climb past it and activate a title on an ancestor as a second tooltip.
  if (value.closest<HTMLElement>('[data-tooltip-managed="true"]')) return null
  const target = value.closest<HTMLElement>("[data-tooltip-content], [title]:not(iframe)")
  if (!target || target.dataset.nativeTitle === "true" || target.dataset.tooltipManaged === "true") return null
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
    const enhancedTitles = new Map<HTMLElement, string>()
    const enhanceTitle = (target: HTMLElement) => {
      if (target instanceof HTMLIFrameElement || target.dataset.nativeTitle === "true") return
      const title = target.getAttribute("title")
      if (!title) return
      enhancedTitles.set(target, title)
      target.dataset.tooltipContent = title
      target.removeAttribute("title")
    }
    const enhanceTree = (root: ParentNode) => {
      if (root instanceof HTMLElement && root.hasAttribute("title")) enhanceTitle(root)
      root.querySelectorAll<HTMLElement>("[title]:not(iframe)").forEach(enhanceTitle)
    }
    enhanceTree(document)
    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        if (mutation.type === "attributes" && mutation.target instanceof HTMLElement) {
          enhanceTitle(mutation.target)
        }
        mutation.addedNodes.forEach((node) => {
          if (node instanceof HTMLElement) enhanceTree(node)
        })
      })
    })
    observer.observe(document.body, { subtree: true, childList: true, attributes: true, attributeFilter: ["title"] })

    const restoreTarget = () => {
      const target = activeTarget.current
      if (!target) return
      if (previousDescribedBy.current) target.setAttribute("aria-describedby", previousDescribedBy.current)
      else target.removeAttribute("aria-describedby")
      activeTarget.current = null
      previousDescribedBy.current = null
    }

    const activate = (target: HTMLElement, left: number, top: number) => {
      if (activeTarget.current !== target) {
        restoreTarget()
        enhanceTitle(target)
        const title = target.dataset.tooltipContent
        if (!title) return
        activeTarget.current = target
        previousDescribedBy.current = target.getAttribute("aria-describedby")
        target.setAttribute("aria-describedby", TOOLTIP_ID)
      }
      const title = target.dataset.tooltipContent
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
      if (document.activeElement instanceof HTMLElement && target.contains(document.activeElement)) return
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
      observer.disconnect()
      document.removeEventListener("pointerover", onPointerOver, true)
      document.removeEventListener("pointermove", onPointerMove, true)
      document.removeEventListener("pointerout", onPointerOut, true)
      document.removeEventListener("focusin", onFocusIn, true)
      document.removeEventListener("focusout", onFocusOut, true)
      document.removeEventListener("keydown", onKeyDown, true)
      window.removeEventListener("scroll", close, true)
      window.removeEventListener("resize", close)
      restoreTarget()
      enhancedTitles.forEach((title, target) => {
        if (!target.hasAttribute("title")) target.setAttribute("title", title)
        if (target.dataset.tooltipContent === title) delete target.dataset.tooltipContent
      })
    }
  }, [])

  if (!tooltip) return null

  return (
    <TooltipSurface
      id={TOOLTIP_ID}
      position={{ left: tooltip.left, top: tooltip.top }}
      className={tooltipToneClass(tooltip.tone)}
    >
      <span className="mb-1 block text-[10px] font-black uppercase tracking-wide opacity-80">{tooltip.context}</span>
      <span className="block text-xs font-bold text-popover-foreground">{tooltip.label}</span>
      {tooltip.label !== tooltip.title && (
        <span className="mt-1 block text-[11px] leading-relaxed text-popover-foreground/75">{tooltip.title}</span>
      )}
    </TooltipSurface>
  )
}
