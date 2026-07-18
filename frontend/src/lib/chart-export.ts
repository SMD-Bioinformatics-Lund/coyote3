export type ChartDataRow = Record<string, unknown>

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement("a")
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
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

export function chartSvgElement(container: HTMLElement | null) {
  return container?.querySelector("svg")
}

export function exportChartAsSvg(container: HTMLElement | null, filename: string) {
  const svg = chartSvgElement(container)
  if (!svg) return false
  const clone = svg.cloneNode(true) as SVGSVGElement
  clone.setAttribute("xmlns", "http://www.w3.org/2000/svg")
  const serialized = new XMLSerializer().serializeToString(clone)
  downloadBlob(new Blob([serialized], { type: "image/svg+xml;charset=utf-8" }), filename)
  return true
}

export async function exportChartAsPng(container: HTMLElement | null, filename: string) {
  const svg = chartSvgElement(container)
  if (!svg) return false
  const clone = svg.cloneNode(true) as SVGSVGElement
  clone.setAttribute("xmlns", "http://www.w3.org/2000/svg")
  const rect = svg.getBoundingClientRect()
  const width = Math.max(1, Math.ceil(rect.width))
  const height = Math.max(1, Math.ceil(rect.height))
  clone.setAttribute("width", String(width))
  clone.setAttribute("height", String(height))
  const serialized = new XMLSerializer().serializeToString(clone)
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
    canvas.width = width * window.devicePixelRatio
    canvas.height = height * window.devicePixelRatio
    const context = canvas.getContext("2d")
    if (!context) return false
    context.scale(window.devicePixelRatio, window.devicePixelRatio)
    context.fillStyle = getComputedStyle(document.documentElement).getPropertyValue("--background") || "#ffffff"
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
