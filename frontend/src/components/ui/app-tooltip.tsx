// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import {
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type FocusEvent,
  type MouseEvent,
  type ReactNode,
} from "react"
import { createPortal } from "react-dom"
import { cn } from "@/lib/utils"
import {
  tooltipToneClass,
  tooltipElementPosition,
  tooltipEventPosition,
  type TooltipPosition,
  type TooltipTone,
} from "@/components/ui/app-tooltip-meta"

export function TooltipSurface({
  position,
  children,
  className,
  id,
  onDismiss,
  onScroll,
}: {
  position: TooltipPosition
  children: ReactNode
  className?: string
  id?: string
  onDismiss?: () => void
  onScroll?: () => void
}) {
  const surfaceRef = useRef<HTMLDivElement | null>(null)
  const [adjustedPosition, setAdjustedPosition] = useState(position)

  useLayoutEffect(() => {
    const surface = surfaceRef.current
    if (!surface) return
    const margin = 12
    const gap = 14
    const rect = surface.getBoundingClientRect()
    const pointer = position.anchor === "pointer"
    const bounds = position.bounds
    const left = pointer
      ? position.left + gap + rect.width <= window.innerWidth - margin
        ? position.left + gap
        : position.left - rect.width - gap
      : bounds ? (bounds.left + bounds.right - rect.width) / 2 : position.left
    const top = pointer
      ? position.top + gap + rect.height <= window.innerHeight - margin
        ? position.top + gap
        : position.top - rect.height - gap
      : bounds
        ? bounds.bottom + gap + rect.height <= window.innerHeight - margin
          ? bounds.bottom + gap
          : bounds.top - rect.height - gap
        : position.top
    setAdjustedPosition({
      left: Math.max(margin, Math.min(left, window.innerWidth - rect.width - margin)),
      top: Math.max(margin, Math.min(top, window.innerHeight - rect.height - margin)),
    })
  }, [position, children])

  useEffect(() => {
    if (!onDismiss) return
    const onKeyDown = (event: KeyboardEvent) => { if (event.key === "Escape") onDismiss() }
    document.addEventListener("keydown", onKeyDown, true)
    const handleScroll = onScroll || onDismiss
    window.addEventListener("scroll", handleScroll, { capture: true, passive: true })
    window.addEventListener("resize", onDismiss)
    window.addEventListener("blur", onDismiss)
    return () => {
      document.removeEventListener("keydown", onKeyDown, true)
      window.removeEventListener("scroll", handleScroll, true)
      window.removeEventListener("resize", onDismiss)
      window.removeEventListener("blur", onDismiss)
    }
  }, [onDismiss, onScroll])

  return createPortal(
    <div
      ref={surfaceRef}
      id={id}
      role="tooltip"
      className={cn(
        "app-tooltip-surface pointer-events-none fixed z-[10000] w-max min-w-44 max-w-[min(18rem,calc(100vw-1.5rem))] rounded-lg border px-3 py-2 text-left text-xs",
        className,
      )}
      style={{ left: adjustedPosition.left, top: adjustedPosition.top }}
    >
      {children}
    </div>,
    document.body,
  )
}

export function AppTooltip({
  children,
  content,
  details,
  label,
  context = "More information",
  tone = "info",
  persistOnClick = false,
}: {
  children: ReactNode
  content: string
  details?: ReactNode
  label?: string
  context?: string
  tone?: TooltipTone
  persistOnClick?: boolean
}) {
  const [position, setPosition] = useState<TooltipPosition | null>(null)
  const [pinned, setPinned] = useState(false)
  const triggerRef = useRef<HTMLSpanElement>(null)

  const place = (event: MouseEvent<HTMLElement> | FocusEvent<HTMLElement>) => {
    setPosition(tooltipEventPosition(event))
  }

  const close = () => {
    setPinned(false)
    setPosition(null)
  }

  const handleScroll = () => {
    const trigger = triggerRef.current
    if (trigger?.contains(document.activeElement)) {
      // Keyboard focus can scroll a nested table after the focus event fires.
      // Keep its explanation attached while the focused trigger is visible.
      const rect = trigger.getBoundingClientRect()
      if (rect.bottom > 0 && rect.top < window.innerHeight && rect.right > 0 && rect.left < window.innerWidth) {
        setPosition(tooltipElementPosition(trigger))
        return
      }
    }
    close()
  }

  return (
    <span
      ref={triggerRef}
      className="inline-flex"
      data-tooltip-managed="true"
      data-tooltip-content={content}
      data-tooltip-label={label || content}
      data-tooltip-context={context}
      data-tooltip-tone={tone}
      onMouseEnter={place}
      onMouseMove={(event) => { if (position && !pinned) place(event) }}
      onMouseLeave={(event) => {
        if (pinned || event.currentTarget.contains(document.activeElement)) {
          setPosition(tooltipElementPosition(event.currentTarget))
        } else setPosition(null)
      }}
      onFocus={place}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) close()
      }}
      onClick={(event) => {
        if (!persistOnClick) return
        if (pinned) close()
        else {
          setPosition(event.detail === 0 ? tooltipElementPosition(event.currentTarget) : tooltipEventPosition(event))
          setPinned(true)
        }
      }}
      onKeyDown={(event) => {
        if (event.key === "Escape") close()
      }}
    >
      {children}
      {position && (
        <TooltipSurface position={position} onDismiss={close} onScroll={handleScroll} className={tooltipToneClass(tone)}>
          <span className="mb-1 block type-label font-semibold uppercase tracking-wide opacity-80">{context}</span>
          <span className="block font-bold text-foreground">{label || content}</span>
          {label && label !== content ? (
            <span className="mt-1 block type-meta leading-relaxed text-foreground/75">{content}</span>
          ) : null}
          {details}
        </TooltipSurface>
      )}
    </span>
  )
}
