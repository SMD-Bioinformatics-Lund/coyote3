import { useCallback, useEffect, useRef, useState } from "react"

type ReportHtmlFrameProps = {
  title: string
  html: string
  minHeight?: number
  className?: string
}

export function ReportHtmlFrame({ title, html, minHeight = 320, className = "" }: ReportHtmlFrameProps) {
  const iframeRef = useRef<HTMLIFrameElement | null>(null)
  const resizeObserverRef = useRef<ResizeObserver | null>(null)
  const [height, setHeight] = useState(minHeight)

  const updateHeight = useCallback(() => {
    const iframe = iframeRef.current
    const doc = iframe?.contentDocument
    if (!doc) return

    const body = doc.body
    const root = doc.documentElement
    const nextHeight = Math.max(
      minHeight,
      body?.scrollHeight ?? 0,
      body?.offsetHeight ?? 0,
      root?.scrollHeight ?? 0,
      root?.offsetHeight ?? 0,
    )
    setHeight(nextHeight + 4)
  }, [minHeight])

  const handleLoad = useCallback(() => {
    resizeObserverRef.current?.disconnect()
    updateHeight()

    const iframe = iframeRef.current
    const doc = iframe?.contentDocument
    if (!doc || typeof ResizeObserver === "undefined") return

    resizeObserverRef.current = new ResizeObserver(updateHeight)
    if (doc.body) resizeObserverRef.current.observe(doc.body)
    if (doc.documentElement) resizeObserverRef.current.observe(doc.documentElement)
  }, [updateHeight])

  useEffect(() => {
    setHeight(minHeight)
    return () => resizeObserverRef.current?.disconnect()
  }, [html, minHeight])

  return (
    <iframe
      ref={iframeRef}
      title={title}
      srcDoc={html}
      scrolling="no"
      onLoad={handleLoad}
      className={`w-full rounded-lg border border-border bg-white ${className}`}
      style={{ height }}
    />
  )
}
