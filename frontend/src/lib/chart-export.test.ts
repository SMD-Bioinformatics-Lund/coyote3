import { afterEach, describe, expect, it, vi } from "vitest"

import { chartSvgElement, exportChartAsPng, exportChartAsSvg, exportRowsAsCsv, rowsToCsv } from "./chart-export"

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

  it("downloads CSV and SVG files", () => {
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined)
    exportRowsAsCsv([{ gene: "TP53" }], "rows.csv")
    const container = document.createElement("div")
    container.innerHTML = '<svg viewBox="0 0 10 10"><circle cx="5" cy="5" r="2" /></svg>'
    expect(exportChartAsSvg(container, "chart.svg")).toBe(true)
    expect(click).toHaveBeenCalledTimes(2)
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
    expect(context.fillRect).toHaveBeenCalledWith(0, 0, 21, 11)
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
