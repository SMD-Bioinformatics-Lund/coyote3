import { useEffect, useMemo, useRef, useState } from "react"

interface ImageSize {
  width: number
  height: number
}

interface RotatableImageProps {
  src: string
  alt: string
  href?: string
  rotation?: number
  fit?: "contain" | "width"
  className?: string
}

const VIEWPORT_PADDING = 16

export function RotatableImage({
  src,
  alt,
  href,
  rotation = 0,
  fit = "contain",
  className,
}: RotatableImageProps) {
  const viewportRef = useRef<HTMLDivElement>(null)
  const [naturalSize, setNaturalSize] = useState<ImageSize | null>(null)
  const [viewportSize, setViewportSize] = useState<ImageSize>({ width: 0, height: 0 })
  const [loadFailed, setLoadFailed] = useState(false)

  useEffect(() => {
    const viewport = viewportRef.current
    if (!viewport) return

    const updateViewportSize = () => {
      setViewportSize({ width: viewport.clientWidth, height: viewport.clientHeight })
    }

    updateViewportSize()
    const observer = new ResizeObserver(updateViewportSize)
    observer.observe(viewport)
    return () => observer.disconnect()
  }, [])

  const normalizedRotation = ((rotation % 360) + 360) % 360
  const layout = useMemo(() => {
    if (!naturalSize || !viewportSize.width || !viewportSize.height) return null

    const quarterTurn = normalizedRotation === 90 || normalizedRotation === 270
    const rotatedWidth = quarterTurn ? naturalSize.height : naturalSize.width
    const rotatedHeight = quarterTurn ? naturalSize.width : naturalSize.height
    const availableWidth = Math.max(1, viewportSize.width - VIEWPORT_PADDING)
    const availableHeight = Math.max(1, viewportSize.height - VIEWPORT_PADDING)
    const widthScale = availableWidth / rotatedWidth
    const heightScale = availableHeight / rotatedHeight
    const scale = fit === "width" ? widthScale : Math.min(widthScale, heightScale)

    return {
      imageWidth: naturalSize.width * scale,
      imageHeight: naturalSize.height * scale,
      stageWidth: rotatedWidth * scale,
      stageHeight: rotatedHeight * scale,
    }
  }, [fit, naturalSize, normalizedRotation, viewportSize])

  const image = (
    <img
      src={src}
      alt={alt}
      draggable={false}
      onLoad={(event) => {
        setLoadFailed(false)
        setNaturalSize({
          width: event.currentTarget.naturalWidth,
          height: event.currentTarget.naturalHeight,
        })
      }}
      onError={() => setLoadFailed(true)}
      className={layout
        ? "absolute left-1/2 top-1/2 block max-w-none select-none rounded border border-border bg-background shadow-sm transition-transform duration-100"
        : "block max-h-full max-w-full select-none rounded border border-border bg-background object-contain shadow-sm"}
      style={layout ? {
        width: layout.imageWidth,
        height: layout.imageHeight,
        transform: `translate(-50%, -50%) rotate(${normalizedRotation}deg)`,
      } : undefined}
    />
  )

  const frameClassName = layout
    ? "relative block shrink-0"
    : "flex h-full min-h-64 w-full items-center justify-center"
  const frameStyle = layout
    ? { width: layout.stageWidth, height: layout.stageHeight }
    : undefined

  const frame = href ? (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className={frameClassName}
      style={frameStyle}
      title="Open the full image"
    >
      {image}
    </a>
  ) : (
    <div className={frameClassName} style={frameStyle}>{image}</div>
  )

  return (
    <div
      ref={viewportRef}
      className={`flex justify-center ${fit === "width" ? "min-h-64 w-full flex-none items-start overflow-visible" : "min-h-0 flex-1 items-center overflow-auto"} ${className || ""}`}
    >
      {loadFailed ? (
        <div className="rounded-md border border-dashed border-destructive/40 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          The CNV profile image could not be loaded.
        </div>
      ) : frame}
    </div>
  )
}
