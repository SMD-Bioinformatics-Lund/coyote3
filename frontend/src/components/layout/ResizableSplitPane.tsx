import { type CSSProperties, type KeyboardEvent, type PointerEvent, type ReactNode, useRef, useState } from "react"
import { GripVertical } from "lucide-react"

import { cn } from "@/lib/utils"

type SplitPaneStyle = CSSProperties & { "--split-primary-size": string }

interface ResizableSplitPaneProps {
  primary: ReactNode
  secondary: ReactNode
  storageKey: string
  initialPrimarySize?: number
  minPrimarySize?: number
  maxPrimarySize?: number
  separatorLabel?: string
  className?: string
}

function storedSize(storageKey: string, fallback: number, min: number, max: number) {
  if (typeof window === "undefined") return fallback
  try {
    const stored = window.localStorage.getItem(storageKey)
    if (stored === null || stored.trim() === "") return fallback
    const value = Number(stored)
    return Number.isFinite(value) ? Math.min(max, Math.max(min, value)) : fallback
  } catch {
    return fallback
  }
}

export function ResizableSplitPane({
  primary,
  secondary,
  storageKey,
  initialPrimarySize = 65,
  minPrimarySize = 35,
  maxPrimarySize = 80,
  separatorLabel = "Resize panes",
  className,
}: ResizableSplitPaneProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [primarySize, setPrimarySize] = useState(() =>
    storedSize(storageKey, initialPrimarySize, minPrimarySize, maxPrimarySize),
  )
  const [dragging, setDragging] = useState(false)
  const primarySizeRef = useRef(primarySize)
  const draggingRef = useRef(false)

  const updateSize = (value: number) => {
    primarySizeRef.current = value
    setPrimarySize(value)
  }

  const updateFromClientX = (clientX: number) => {
    const bounds = containerRef.current?.getBoundingClientRect()
    if (!bounds?.width) return
    const next = ((clientX - bounds.left) / bounds.width) * 100
    updateSize(Math.min(maxPrimarySize, Math.max(minPrimarySize, next)))
  }

  const persist = (value: number) => {
    try {
      window.localStorage.setItem(storageKey, String(Math.round(value * 10) / 10))
    } catch {
      // Resizing remains available when browser storage is disabled.
    }
  }

  const finishDrag = (event: PointerEvent<HTMLDivElement>) => {
    if (!draggingRef.current) return
    draggingRef.current = false
    setDragging(false)
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId)
    }
    persist(primarySizeRef.current)
  }

  const resizeWithKeyboard = (event: KeyboardEvent<HTMLDivElement>) => {
    let next = primarySize
    if (event.key === "ArrowLeft") next -= 2
    else if (event.key === "ArrowRight") next += 2
    else if (event.key === "Home") next = minPrimarySize
    else if (event.key === "End") next = maxPrimarySize
    else return
    event.preventDefault()
    next = Math.min(maxPrimarySize, Math.max(minPrimarySize, next))
    updateSize(next)
    persist(next)
  }

  const style: SplitPaneStyle = { "--split-primary-size": `${primarySize}%` }

  return (
    <div ref={containerRef} className={cn("resizable-split-pane", className)} style={style}>
      <div className="resizable-split-primary min-w-0">{primary}</div>
      <div
        role="separator"
        aria-label={separatorLabel}
        aria-orientation="vertical"
        aria-valuemin={minPrimarySize}
        aria-valuemax={maxPrimarySize}
        aria-valuenow={Math.round(primarySize)}
        tabIndex={0}
        className={cn("resizable-split-handle group", dragging && "is-dragging")}
        onPointerDown={(event) => {
          if (event.pointerType === "mouse" && event.button !== 0) return
          event.currentTarget.setPointerCapture(event.pointerId)
          draggingRef.current = true
          setDragging(true)
          updateFromClientX(event.clientX)
        }}
        onPointerMove={(event) => {
          if (draggingRef.current) updateFromClientX(event.clientX)
        }}
        onPointerUp={finishDrag}
        onPointerCancel={finishDrag}
        onKeyDown={resizeWithKeyboard}
      >
        <span title="Drag to resize panes">
          <GripVertical aria-hidden="true" />
        </span>
      </div>
      <div className="resizable-split-secondary min-w-0">{secondary}</div>
    </div>
  )
}
