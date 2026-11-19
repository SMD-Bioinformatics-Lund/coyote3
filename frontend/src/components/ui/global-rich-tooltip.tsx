// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import { useEffect, useRef, useState } from "react"
import { TooltipSurface } from "@/components/ui/app-tooltip"
import { tooltipElementPosition, tooltipToneClass, type TooltipPosition } from "@/components/ui/app-tooltip-meta"
import { GLOBAL_TOOLTIP_ID, tooltipContent, tooltipTarget } from "./tooltip-target"

type TooltipState = NonNullable<ReturnType<typeof tooltipContent>> & {
  position: TooltipPosition
}

/** Shared extra help and icon/clipped-label hints; rich badges retain their descriptions. */
export function GlobalRichTooltip() {
  const [tooltip, setTooltip] = useState<TooltipState | null>(null)
  const activeTarget = useRef<HTMLElement | null>(null)

  useEffect(() => {
    const enhancedTitles = new Map<HTMLElement, { title: string; originalContent?: string }>()
    let hoveredTarget: HTMLElement | null = null
    let dismissedTarget: HTMLElement | null = null
    let pointerActive = false
    let touchInteraction = false

    const restoreTarget = () => {
      const target = activeTarget.current
      if (!target) return
      const descriptions = (target.getAttribute("aria-describedby") || "").split(/\s+/)
        .filter(id => id && id !== GLOBAL_TOOLTIP_ID)
      if (descriptions.length) target.setAttribute("aria-describedby", descriptions.join(" "))
      else target.removeAttribute("aria-describedby")
      activeTarget.current = null
    }
    const close = () => {
      pointerActive = false
      setTooltip(null)
      restoreTarget()
    }
    const refreshContent = () => {
      const target = activeTarget.current
      if (!target) return
      const content = target.isConnected && tooltipContent(target)
      if (!content) { close(); return }
      setTooltip(current => current && Object.entries(content).some(([key, value]) => current[key as keyof typeof content] !== value)
        ? { ...current, ...content } : current)
    }
    const enhanceTitle = (target: HTMLElement) => {
      if (target instanceof HTMLIFrameElement || target.closest('[data-native-title="true"], [data-tooltip-disabled="true"]')) return
      const title = target.getAttribute("title")
      if (!title) return
      const previous = enhancedTitles.get(target)
      const originalContent = previous ? previous.originalContent : target.dataset.tooltipContent
      enhancedTitles.set(target, { title, originalContent })
      if (originalContent === undefined) target.dataset.tooltipContent = title
      target.removeAttribute("title")
    }
    const enhanceTree = (root: ParentNode) => {
      if (root instanceof HTMLElement && root.hasAttribute("title")) enhanceTitle(root)
      root.querySelectorAll<HTMLElement>("[title]:not(iframe)").forEach(enhanceTitle)
    }
    enhanceTree(document)
    const observer = new MutationObserver(mutations => {
      mutations.forEach(mutation => {
        if (mutation.type === "attributes" && mutation.attributeName === "title" && mutation.target instanceof HTMLElement) enhanceTitle(mutation.target)
        mutation.addedNodes.forEach(node => { if (node instanceof HTMLElement) enhanceTree(node) })
      })
      refreshContent()
    })
    observer.observe(document.body, {
      subtree: true, childList: true, characterData: true, attributes: true,
      attributeFilter: ["title", "aria-label", "aria-labelledby", "aria-describedby", "placeholder", "data-tooltip-content", "data-tooltip-label", "data-tooltip-context", "data-tooltip-tone"],
    })

    const activate = (target: HTMLElement, position: TooltipPosition) => {
      enhanceTitle(target)
      const content = tooltipContent(target)
      if (!content) { close(); return }
      if (activeTarget.current !== target) {
        restoreTarget()
        activeTarget.current = target
        const describedBy = target.getAttribute("aria-describedby")
        target.setAttribute("aria-describedby", [describedBy, GLOBAL_TOOLTIP_ID].filter(Boolean).join(" "))
      }
      pointerActive = position.anchor === "pointer"
      setTooltip({ ...content, position })
    }
    const retainFocusedOrClose = () => {
      const target = activeTarget.current
      if (target && target.contains(document.activeElement)) activate(target, tooltipElementPosition(target))
      else close()
    }
    const onPointerOver = (event: PointerEvent) => {
      touchInteraction = event.pointerType === "touch"
      if (touchInteraction) { close(); return }
      const target = tooltipTarget(event.target)
      hoveredTarget = target
      if (target && target !== dismissedTarget) activate(target, { left: event.clientX, top: event.clientY, anchor: "pointer" })
      else if (!target) retainFocusedOrClose()
    }
    const onPointerMove = (event: PointerEvent) => {
      // Only a hint actually hovered by this pointer follows it. Focus is element-anchored.
      if (!pointerActive || !activeTarget.current || event.pointerType === "touch") return
      if (tooltipTarget(event.target) !== activeTarget.current) { retainFocusedOrClose(); return }
      setTooltip(current => current ? {
        ...current, position: { left: event.clientX, top: event.clientY, anchor: "pointer" },
      } : current)
    }
    const onPointerOut = (event: PointerEvent) => {
      if (hoveredTarget && event.relatedTarget instanceof Node && hoveredTarget.contains(event.relatedTarget)) return
      hoveredTarget = null
      dismissedTarget = null
      retainFocusedOrClose()
    }
    const onPointerDown = (event: PointerEvent) => {
      touchInteraction = event.pointerType === "touch"
      if (touchInteraction) close()
    }
    const onFocusIn = (event: FocusEvent) => {
      if (touchInteraction) return
      const target = tooltipTarget(event.target)
      if (!target) { close(); return }
      if (pointerActive && activeTarget.current === target && hoveredTarget === target) return
      activate(target, tooltipElementPosition(target))
    }
    const onFocusOut = (event: FocusEvent) => {
      const target = activeTarget.current
      if (!target || (event.relatedTarget instanceof Node && target.contains(event.relatedTarget))) return
      if (!(pointerActive && hoveredTarget === target)) close()
    }
    const onKeyDown = (event: KeyboardEvent) => {
      touchInteraction = false
      if (event.key === "Escape") {
        dismissedTarget = hoveredTarget
        close()
      }
    }

    document.addEventListener("pointerover", onPointerOver, true)
    document.addEventListener("pointermove", onPointerMove, true)
    document.addEventListener("pointerout", onPointerOut, true)
    document.addEventListener("pointerdown", onPointerDown, true)
    document.addEventListener("focusin", onFocusIn, true)
    document.addEventListener("focusout", onFocusOut, true)
    document.addEventListener("keydown", onKeyDown, true)
    window.addEventListener("scroll", close, { capture: true, passive: true })
    window.addEventListener("resize", close)
    window.addEventListener("blur", close)
    return () => {
      observer.disconnect()
      document.removeEventListener("pointerover", onPointerOver, true)
      document.removeEventListener("pointermove", onPointerMove, true)
      document.removeEventListener("pointerout", onPointerOut, true)
      document.removeEventListener("pointerdown", onPointerDown, true)
      document.removeEventListener("focusin", onFocusIn, true)
      document.removeEventListener("focusout", onFocusOut, true)
      document.removeEventListener("keydown", onKeyDown, true)
      window.removeEventListener("scroll", close, true)
      window.removeEventListener("resize", close)
      window.removeEventListener("blur", close)
      restoreTarget()
      enhancedTitles.forEach(({ title, originalContent }, target) => {
        if (!target.hasAttribute("title")) target.setAttribute("title", title)
        if (originalContent === undefined && target.dataset.tooltipContent === title) delete target.dataset.tooltipContent
      })
    }
  }, [])

  if (!tooltip) return null
  return (
    <TooltipSurface id={GLOBAL_TOOLTIP_ID} position={tooltip.position} className={tooltipToneClass(tooltip.tone)}>
      <span className="mb-1 block type-label font-semibold uppercase tracking-wide opacity-80">{tooltip.context}</span>
      <span className="block font-bold text-foreground">{tooltip.label}</span>
      {tooltip.label !== tooltip.title && (
        <span className="mt-1 block type-meta leading-relaxed text-foreground/75">{tooltip.title}</span>
      )}
    </TooltipSurface>
  )
}
