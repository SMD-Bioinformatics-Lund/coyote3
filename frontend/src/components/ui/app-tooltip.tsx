import {
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
  type TooltipPosition,
  type TooltipTone,
} from "@/components/ui/app-tooltip-meta"

export function TooltipSurface({
  position,
  children,
  className,
  id,
}: {
  position: TooltipPosition
  children: ReactNode
  className?: string
  id?: string
}) {
  const surfaceRef = useRef<HTMLDivElement | null>(null)
  const [adjustedPosition, setAdjustedPosition] = useState(position)

  useLayoutEffect(() => {
    const surface = surfaceRef.current
    if (!surface) return
    const margin = 12
    const rect = surface.getBoundingClientRect()
    setAdjustedPosition({
      left: Math.max(margin, Math.min(position.left, window.innerWidth - rect.width - margin)),
      top: Math.max(margin, Math.min(position.top, window.innerHeight - rect.height - margin)),
    })
  }, [position.left, position.top, children])

  return createPortal(
    <div
      ref={surfaceRef}
      id={id}
      role="tooltip"
      className={cn(
        "pointer-events-none fixed z-[10000] min-w-44 max-w-[min(18rem,calc(100vw-1.5rem))] rounded-lg border bg-popover px-3 py-2 text-left text-xs shadow-xl",
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
  label,
  context = "More information",
  tone = "info",
  persistOnClick = false,
}: {
  children: ReactNode
  content: string
  label?: string
  context?: string
  tone?: TooltipTone
  persistOnClick?: boolean
}) {
  const [position, setPosition] = useState<TooltipPosition | null>(null)
  const [pinned, setPinned] = useState(false)

  const place = (event: MouseEvent<HTMLElement> | FocusEvent<HTMLElement>) => {
    const rect = event.currentTarget.getBoundingClientRect()
    const width = 288
    const estimatedHeight = 112
    const gap = 8
    const margin = 12
    const left = Math.max(margin, Math.min(
      rect.left + rect.width / 2 - width / 2,
      window.innerWidth - width - margin,
    ))
    const top = rect.bottom + gap + estimatedHeight <= window.innerHeight - margin
      ? rect.bottom + gap
      : Math.max(margin, rect.top - estimatedHeight - gap)
    setPosition({ left, top })
  }

  const close = () => {
    setPinned(false)
    setPosition(null)
  }

  return (
    <span
      className="inline-flex"
      data-tooltip-managed="true"
      data-tooltip-content={content}
      data-tooltip-label={label || content}
      data-tooltip-context={context}
      data-tooltip-tone={tone}
      onMouseEnter={place}
      onMouseMove={(event) => {
        if (!pinned) place(event)
      }}
      onMouseLeave={() => {
        if (!pinned) setPosition(null)
      }}
      onFocus={place}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) close()
      }}
      onClick={(event) => {
        if (!persistOnClick) return
        if (pinned) close()
        else {
          place(event)
          setPinned(true)
        }
      }}
      onKeyDown={(event) => {
        if (event.key === "Escape") close()
      }}
    >
      {children}
      {position && (
        <TooltipSurface position={position} className={tooltipToneClass(tone)}>
          <span className="mb-1 block text-[10px] font-semibold uppercase tracking-wide opacity-80">{context}</span>
          <span className="block text-xs font-semibold text-popover-foreground">{label || content}</span>
          {label && label !== content ? (
            <span className="mt-1 block text-[11px] leading-relaxed text-popover-foreground/75">{content}</span>
          ) : null}
        </TooltipSurface>
      )}
    </span>
  )
}
