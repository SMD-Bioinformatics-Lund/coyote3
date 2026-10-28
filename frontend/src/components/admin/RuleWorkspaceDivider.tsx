import {
  GripVertical
} from "lucide-react"
import { useRef, type KeyboardEvent, type PointerEvent } from "react"


export function ResizeDivider({
  label,
  width,
  setWidth,
  min,
  max,
  direction = 1,
}: {
  label: string
  width: number
  setWidth: (width: number) => void
  min: number
  max: number
  direction?: 1 | -1
}) {
  const start = useRef({ x: 0, width })
  const clamp = (value: number) => Math.min(max, Math.max(min, value))
  const update = (value: number) => {
    const nextWidth = clamp(value)
    setWidth(nextWidth)
    try {
      window.localStorage.setItem(`clinical-rules-width:${label}`, String(nextWidth))
    } catch {
      // Resizing remains available when browser storage is disabled.
    }
  }
  const finish = (event: PointerEvent<HTMLDivElement>) => {
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId)
  }
  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (!["ArrowLeft", "ArrowRight"].includes(event.key)) return
    event.preventDefault()
    const delta = event.key === 'ArrowRight' ? 16 : -16
    update(width + delta * direction)
  }
  return <div role="separator" aria-label={label} aria-orientation="vertical" aria-valuemin={min} aria-valuemax={max} aria-valuenow={Math.round(width)} tabIndex={0} className="clinical-rules-divider" onKeyDown={onKeyDown} onPointerDown={(event) => { if (event.pointerType === "mouse" && event.button !== 0) return; start.current = { x: event.clientX, width }; event.currentTarget.setPointerCapture(event.pointerId) }} onPointerMove={(event) => { if (event.currentTarget.hasPointerCapture(event.pointerId)) update(start.current.width + (event.clientX - start.current.x) * direction) }} onPointerUp={finish} onPointerCancel={finish}><GripVertical /></div>
}
