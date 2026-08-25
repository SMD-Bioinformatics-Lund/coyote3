export type ChartDataRow = Record<string, unknown>

export type ChartExportOptions = {
  title?: string
  subtitle?: string
}

type ChartLegendEntry = {
  label: string
  color: string
}

const EXPORT_PADDING = 32
const EXPORT_TITLE_HEIGHT = 24
const EXPORT_SUBTITLE_HEIGHT = 20
const EXPORT_HEADER_GAP = 16
const EXPORT_LEGEND_GAP = 18
const EXPORT_LEGEND_ROW_HEIGHT = 22

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement("a")
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  // Keep the object URL alive until the browser has consumed the synthetic
  // download click. Immediate revocation can cancel downloads in Chromium.
  window.setTimeout(() => URL.revokeObjectURL(url), 0)
}

export function rowsToCsv(rows: ChartDataRow[]) {
  if (!rows.length) return ""
  const headers = Array.from(rows.reduce((keys, row) => {
    Object.keys(row).forEach((key) => keys.add(key))
    return keys
  }, new Set<string>()))
  const escape = (value: unknown) => {
    const text = value == null ? "" : String(value)
    return /[",\n\r]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text
  }
  return [
    headers.map(escape).join(","),
    ...rows.map((row) => headers.map((header) => escape(row[header])).join(",")),
  ].join("\n")
}

export function exportRowsAsCsv(rows: ChartDataRow[], filename: string) {
  downloadBlob(new Blob([rowsToCsv(rows)], { type: "text/csv;charset=utf-8" }), filename)
}

function svgDimensions(svg: SVGSVGElement) {
  const rect = svg.getBoundingClientRect()
  const viewBox = svg.getAttribute("viewBox")?.trim().split(/[\s,]+/).map(Number) ?? []
  const attrWidth = Number.parseFloat(svg.getAttribute("width") || "")
  const attrHeight = Number.parseFloat(svg.getAttribute("height") || "")
  const width = Math.max(0, rect.width || attrWidth || viewBox[2] || 0)
  const height = Math.max(0, rect.height || attrHeight || viewBox[3] || 0)
  return { width, height }
}

export function chartSvgElement(container: HTMLElement | null) {
  if (!container) return null
  const candidates = Array.from(container.querySelectorAll<SVGSVGElement>("svg"))
  if (!candidates.length) return null

  // Recharts may place small legend-symbol SVGs before the plot SVG. The main
  // chart is the largest rendered SVG in the chart container.
  return candidates.reduce((largest, candidate) => {
    const largestDimensions = svgDimensions(largest)
    const candidateDimensions = svgDimensions(candidate)
    return candidateDimensions.width * candidateDimensions.height
      > largestDimensions.width * largestDimensions.height
      ? candidate
      : largest
  })
}

const SVG_STYLE_PROPERTIES = [
  "color",
  "fill",
  "fill-opacity",
  "font-family",
  "font-size",
  "font-style",
  "font-weight",
  "letter-spacing",
  "opacity",
  "stroke",
  "stroke-dasharray",
  "stroke-linecap",
  "stroke-linejoin",
  "stroke-opacity",
  "stroke-width",
  "text-anchor",
  "visibility",
] as const

function isTransparent(color: string) {
  return !color || color === "transparent" || color === "rgba(0, 0, 0, 0)"
}

function resolvedBackground(element: HTMLElement) {
  let current: HTMLElement | null = element
  while (current) {
    const color = getComputedStyle(current).backgroundColor
    if (!isTransparent(color)) return color
    current = current.parentElement
  }
  const bodyColor = getComputedStyle(document.body).backgroundColor
  if (!isTransparent(bodyColor)) return bodyColor
  const rootStyles = getComputedStyle(document.documentElement)
  const rootColor = rootStyles.backgroundColor
  if (!isTransparent(rootColor)) return rootColor
  return rootStyles.getPropertyValue("--background").trim() || "rgb(255, 255, 255)"
}

function chartDimensions(svg: SVGSVGElement) {
  const dimensions = svgDimensions(svg)
  const width = Math.max(1, Math.ceil(dimensions.width || 1))
  const height = Math.max(1, Math.ceil(dimensions.height || 1))
  return { width, height }
}

function svgText(parent: SVGElement, value: string, attributes: Record<string, string>) {
  const text = document.createElementNS("http://www.w3.org/2000/svg", "text")
  text.textContent = value
  Object.entries(attributes).forEach(([name, attributeValue]) => text.setAttribute(name, attributeValue))
  parent.appendChild(text)
  return text
}

function chartLegendEntries(container: HTMLElement): ChartLegendEntry[] {
  const entries = Array.from(container.querySelectorAll<HTMLElement>(".recharts-legend-item"))
  return entries.flatMap((entry) => {
    const label = entry.textContent?.trim()
    if (!label) return []
    const icon = entry.querySelector<SVGElement>(".recharts-legend-icon")
    const iconStyles = icon ? getComputedStyle(icon) : null
    const color = iconStyles?.fill && iconStyles.fill !== "none"
      ? iconStyles.fill
      : iconStyles?.stroke && iconStyles.stroke !== "none"
        ? iconStyles.stroke
        : getComputedStyle(entry).color
    return [{ label, color }]
  })
}

function legendLayout(entries: ChartLegendEntry[], availableWidth: number) {
  const rows: Array<Array<ChartLegendEntry & { width: number }>> = []
  let row: Array<ChartLegendEntry & { width: number }> = []
  let rowWidth = 0
  entries.forEach((entry) => {
    const width = Math.max(48, 22 + entry.label.length * 7)
    if (row.length && rowWidth + EXPORT_LEGEND_GAP + width > availableWidth) {
      rows.push(row)
      row = []
      rowWidth = 0
    }
    row.push({ ...entry, width })
    rowWidth += (rowWidth ? EXPORT_LEGEND_GAP : 0) + width
  })
  if (row.length) rows.push(row)
  return rows
}

function inlineComputedSvgStyles(source: SVGSVGElement, clone: SVGSVGElement) {
  const sourceElements = [source, ...Array.from(source.querySelectorAll<SVGElement>("*"))]
  const clonedElements = [clone, ...Array.from(clone.querySelectorAll<SVGElement>("*"))]

  sourceElements.forEach((element, index) => {
    const clonedElement = clonedElements[index]
    if (!clonedElement) return
    const computed = getComputedStyle(element)
    SVG_STYLE_PROPERTIES.forEach((property) => {
      const value = computed.getPropertyValue(property)
      if (value) clonedElement.style.setProperty(property, value)
    })
  })
}

export function serializeChartSvg(container: HTMLElement | null, options: ChartExportOptions = {}) {
  const svg = chartSvgElement(container)
  if (!svg || !container) return null
  const { width, height } = chartDimensions(svg)
  const clone = svg.cloneNode(true) as SVGSVGElement
  clone.setAttribute("xmlns", "http://www.w3.org/2000/svg")
  clone.setAttribute("x", String(EXPORT_PADDING))
  clone.setAttribute("viewBox", svg.getAttribute("viewBox") || `0 0 ${width} ${height}`)
  clone.setAttribute("preserveAspectRatio", svg.getAttribute("preserveAspectRatio") || "xMidYMid meet")
  inlineComputedSvgStyles(svg, clone)

  const title = options.title?.trim() || ""
  const subtitle = options.subtitle?.trim() || ""
  const headerHeight = title
    ? EXPORT_TITLE_HEIGHT + (subtitle ? EXPORT_SUBTITLE_HEIGHT : 0) + EXPORT_HEADER_GAP
    : 0
  clone.setAttribute("y", String(EXPORT_PADDING + headerHeight))
  clone.setAttribute("width", String(width))
  clone.setAttribute("height", String(height))

  const legendRows = legendLayout(chartLegendEntries(container), width)
  const legendHeight = legendRows.length
    ? EXPORT_HEADER_GAP + legendRows.length * EXPORT_LEGEND_ROW_HEIGHT
    : 0
  const exportWidth = width + EXPORT_PADDING * 2
  const exportHeight = height + headerHeight + legendHeight + EXPORT_PADDING * 2
  const root = document.createElementNS("http://www.w3.org/2000/svg", "svg")
  root.setAttribute("xmlns", "http://www.w3.org/2000/svg")
  root.setAttribute("width", String(exportWidth))
  root.setAttribute("height", String(exportHeight))
  root.setAttribute("viewBox", `0 0 ${exportWidth} ${exportHeight}`)

  const backgroundColor = resolvedBackground(container)
  const background = document.createElementNS("http://www.w3.org/2000/svg", "rect")
  background.setAttribute("x", "0")
  background.setAttribute("y", "0")
  background.setAttribute("width", "100%")
  background.setAttribute("height", "100%")
  background.setAttribute("fill", backgroundColor)
  root.appendChild(background)

  const containerStyles = getComputedStyle(container)
  const textColor = containerStyles.color || "rgb(15, 23, 42)"
  const fontFamily = containerStyles.fontFamily || "Arial, sans-serif"
  if (title) {
    svgText(root, title, {
      x: String(EXPORT_PADDING),
      y: String(EXPORT_PADDING + 17),
      fill: textColor,
      "font-family": fontFamily,
      "font-size": "18",
      "font-weight": "600",
    })
  }
  if (subtitle) {
    svgText(root, subtitle, {
      x: String(EXPORT_PADDING),
      y: String(EXPORT_PADDING + EXPORT_TITLE_HEIGHT + 14),
      fill: containerStyles.getPropertyValue("--muted-foreground").trim() || textColor,
      "fill-opacity": "0.72",
      "font-family": fontFamily,
      "font-size": "12",
      "font-weight": "400",
    })
  }

  root.appendChild(clone)

  const legendTop = EXPORT_PADDING + headerHeight + height + EXPORT_HEADER_GAP
  legendRows.forEach((row, rowIndex) => {
    const rowWidth = row.reduce((total, entry) => total + entry.width, 0)
      + Math.max(0, row.length - 1) * EXPORT_LEGEND_GAP
    let x = Math.max(EXPORT_PADDING, (exportWidth - rowWidth) / 2)
    const y = legendTop + rowIndex * EXPORT_LEGEND_ROW_HEIGHT
    row.forEach((entry) => {
      const swatch = document.createElementNS("http://www.w3.org/2000/svg", "rect")
      swatch.setAttribute("x", String(x))
      swatch.setAttribute("y", String(y + 2))
      swatch.setAttribute("width", "12")
      swatch.setAttribute("height", "12")
      swatch.setAttribute("rx", "2")
      swatch.setAttribute("fill", entry.color)
      root.appendChild(swatch)
      svgText(root, entry.label, {
        x: String(x + 18),
        y: String(y + 13),
        fill: textColor,
        "font-family": fontFamily,
        "font-size": "11",
        "font-weight": "400",
      })
      x += entry.width + EXPORT_LEGEND_GAP
    })
  })

  return {
    serialized: new XMLSerializer().serializeToString(root),
    width: exportWidth,
    height: exportHeight,
    background: backgroundColor,
  }
}

export function exportChartAsSvg(container: HTMLElement | null, filename: string, options: ChartExportOptions = {}) {
  const prepared = serializeChartSvg(container, options)
  if (!prepared) return false
  downloadBlob(new Blob([prepared.serialized], { type: "image/svg+xml;charset=utf-8" }), filename)
  return true
}

export async function exportChartAsPng(container: HTMLElement | null, filename: string, options: ChartExportOptions = {}) {
  const prepared = serializeChartSvg(container, options)
  if (!prepared) return false
  await document.fonts?.ready
  const { serialized, width, height, background } = prepared
  const imageUrl = URL.createObjectURL(new Blob([serialized], { type: "image/svg+xml;charset=utf-8" }))
  try {
    const image = new Image()
    image.decoding = "async"
    await new Promise<void>((resolve, reject) => {
      image.onload = () => resolve()
      image.onerror = () => reject(new Error("Unable to render chart image."))
      image.src = imageUrl
    })
    const canvas = document.createElement("canvas")
    const pixelRatio = Math.min(3, Math.max(1, window.devicePixelRatio || 1))
    canvas.width = width * pixelRatio
    canvas.height = height * pixelRatio
    const context = canvas.getContext("2d")
    if (!context) return false
    context.scale(pixelRatio, pixelRatio)
    context.fillStyle = background
    context.fillRect(0, 0, width, height)
    context.drawImage(image, 0, 0, width, height)
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/png"))
    if (!blob) return false
    downloadBlob(blob, filename)
    return true
  } finally {
    URL.revokeObjectURL(imageUrl)
  }
}
