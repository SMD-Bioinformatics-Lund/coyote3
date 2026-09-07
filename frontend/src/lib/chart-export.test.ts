import { afterEach, describe, expect, it, vi } from "vitest"

import { chartSvgElement, exportChartAsPng, exportChartAsSvg, exportRowsAsCsv, rowsToCsv, serializeChartSvg } from "./chart-export"

class LoadableImage {
  decoding = ""
  onload: null | (() => void) = null
  onerror: null | (() => void) = null

  set src(_value: string) {
    queueMicrotask(() => this.onload?.())
  }
}

describe("chart export utilities", () => {
  afterEach(() => vi.restoreAllMocks())

  it("serializes heterogeneous rows and escapes CSV values", () => {
    expect(rowsToCsv([{ gene: "TP53", note: "one, two" }, { gene: "SRSF2", detail: 'A "quote"' }])).toBe(
      'gene,note,detail\nTP53,"one, two",\nSRSF2,,"A ""quote"""',
    )
    expect(rowsToCsv([])).toBe("")
  })

  it("finds SVG content and declines SVG export when no chart exists", () => {
    const container = document.createElement("div")
    expect(chartSvgElement(container)).toBeNull()
    expect(exportChartAsSvg(container, "empty.svg")).toBe(false)
  })

  it("selects the main plot instead of an earlier Recharts legend symbol", () => {
    const container = document.createElement("div")
    container.innerHTML = [
      '<svg class="recharts-surface" width="14" height="14" viewBox="0 0 32 32" aria-label="legend symbol" />',
      '<svg class="recharts-surface" width="720" height="280" viewBox="0 0 720 280" aria-label="main plot"><text>TP53</text></svg>',
    ].join("")

    expect(chartSvgElement(container)?.getAttribute("aria-label")).toBe("main plot")
    expect(serializeChartSvg(container)).toMatchObject({ width: 784, height: 344 })
  })

  it("downloads CSV and SVG files", () => {
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined)
    exportRowsAsCsv([{ gene: "TP53" }], "rows.csv")
    const container = document.createElement("div")
    container.innerHTML = '<svg viewBox="0 0 10 10"><circle cx="5" cy="5" r="2" /></svg>'
    expect(exportChartAsSvg(container, "chart.svg")).toBe(true)
    expect(click).toHaveBeenCalledTimes(2)
  })

  it("creates a standalone SVG with resolved dimensions, background, and presentation styles", () => {
    const container = document.createElement("div")
    container.style.backgroundColor = "rgb(240, 241, 242)"
    container.innerHTML = '<svg viewBox="0 0 20 10"><text style="fill: rgb(12, 34, 56); font-size: 11px">TP53</text></svg>'
    const prepared = serializeChartSvg(container, { title: "Gene findings", subtitle: "Reported cohort" })

    expect(prepared).toMatchObject({ width: 84, height: 134, background: "rgb(240, 241, 242)" })
    expect(prepared?.serialized).toContain('width="84"')
    expect(prepared?.serialized).toContain('height="134"')
    expect(prepared?.serialized).toContain("rgb(240, 241, 242)")
    expect(prepared?.serialized).toContain("rgb(12, 34, 56)")
    expect(prepared?.serialized).toContain("Gene findings")
    expect(prepared?.serialized).toContain("Reported cohort")
  })

  it("adds a native wrapped legend below the chart", () => {
    const container = document.createElement("div")
    container.innerHTML = [
      '<svg viewBox="0 0 240 100"><rect width="240" height="100" /></svg>',
      '<ul class="recharts-default-legend">',
      '<li class="recharts-legend-item" style="color: rgb(12, 98, 61)"><svg class="recharts-legend-icon" style="fill: rgb(12, 98, 61)"></svg><span>Somatic</span></li>',
      '<li class="recharts-legend-item" style="color: rgb(157, 93, 24)"><svg class="recharts-legend-icon" style="fill: rgb(157, 93, 24)"></svg><span>Germline</span></li>',
      '</ul>',
    ].join("")

    const prepared = serializeChartSvg(container, { title: "Findings" })
    expect(prepared).toMatchObject({ width: 304, height: 242 })
    expect(prepared?.serialized).toContain("Somatic")
    expect(prepared?.serialized).toContain("Germline")
    expect(prepared?.serialized).toContain('rx="2"')
  })

  it("exports a chart as a scaled PNG using the configured page background", async () => {
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined)
    vi.stubGlobal("Image", LoadableImage)
    const context = {
      scale: vi.fn(),
      fillRect: vi.fn(),
      drawImage: vi.fn(),
      fillStyle: "",
    }
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(context as any)
    vi.spyOn(HTMLCanvasElement.prototype, "toBlob").mockImplementation((callback) => callback(new Blob(["png"])))
    document.documentElement.style.setProperty("--background", "rgb(245 245 245)")
    const container = document.createElement("div")
    container.innerHTML = '<svg viewBox="0 0 20 10"></svg>'
    vi.spyOn(container.querySelector("svg")!, "getBoundingClientRect").mockReturnValue({
      width: 20.2,
      height: 10.1,
    } as DOMRect)

    await expect(exportChartAsPng(container, "chart.png")).resolves.toBe(true)
    expect(context.fillStyle).toBe("rgb(245 245 245)")
    expect(context.fillRect).toHaveBeenCalledWith(0, 0, 85, 75)
    expect(context.drawImage).toHaveBeenCalled()
    expect(click).toHaveBeenCalledOnce()
    vi.unstubAllGlobals()
  })

  it("declines PNG export without an SVG, canvas context, or encoded blob", async () => {
    await expect(exportChartAsPng(document.createElement("div"), "empty.png")).resolves.toBe(false)

    vi.stubGlobal("Image", LoadableImage)
    const container = document.createElement("div")
    container.innerHTML = "<svg></svg>"
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null)
    await expect(exportChartAsPng(container, "no-context.png")).resolves.toBe(false)

    vi.restoreAllMocks()
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({
      scale: vi.fn(), fillRect: vi.fn(), drawImage: vi.fn(), fillStyle: "",
    } as any)
    vi.spyOn(HTMLCanvasElement.prototype, "toBlob").mockImplementation((callback) => callback(null))
    await expect(exportChartAsPng(container, "no-blob.png")).resolves.toBe(false)
    vi.unstubAllGlobals()
  })
})
