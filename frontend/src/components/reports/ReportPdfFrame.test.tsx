import { act, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, expect, it, vi } from "vitest"
import { ReportPdfFrame } from "./ReportPdfFrame"

beforeEach(() => {
  vi.useFakeTimers()
  let sequence = 0
  vi.spyOn(URL, "createObjectURL").mockImplementation(() => `blob:report-${++sequence}`)
  vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined)
  vi.stubGlobal("navigator", { pdfViewerEnabled: true })
})
afterEach(() => vi.useRealTimers())
const first = new Blob(["%PDF-1.7\nFirst\n%%EOF"], { type: "application/pdf" })

it("reloads a failed viewer, cancels the timeout after load, and releases replaced URLs", () => {
  const view = render(<ReportPdfFrame blob={first} title="Synthetic PDF" filename="synthetic.pdf" />)
  expect(screen.getByTitle("Synthetic PDF")).toHaveAttribute("src", "blob:report-1")
  act(() => vi.advanceTimersByTime(15000))
  expect(screen.getByRole("status")).toHaveTextContent("could not finish loading")
  fireEvent.load(screen.getByTitle("Synthetic PDF"))
  expect(screen.queryByRole("status")).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole("button", { name: "Reload PDF viewer" }))
  expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:report-1")
  fireEvent.load(screen.getByTitle("Synthetic PDF"))
  act(() => vi.advanceTimersByTime(20000))
  expect(screen.getByTitle("Synthetic PDF")).toHaveAttribute("src", "blob:report-2")
  expect(screen.getByRole("link", { name: "Open PDF" })).toHaveAttribute("href", "blob:report-2")
  view.rerender(<ReportPdfFrame blob={new Blob(["%PDF-1.7\nSecond\n%%EOF"])} title="Synthetic PDF" filename="second.pdf" />)
  expect(screen.getByTitle("Synthetic PDF")).toHaveAttribute("src", "blob:report-3")
  expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:report-2")
  view.unmount()
  expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:report-3")
})

it("offers open and download controls when the browser cannot embed PDFs", () => {
  vi.stubGlobal("navigator", { pdfViewerEnabled: false })
  render(<ReportPdfFrame blob={first} title="Synthetic PDF" filename="synthetic.pdf" />)
  expect(screen.queryByTitle("Synthetic PDF")).not.toBeInTheDocument()
  expect(screen.getByRole("status")).toHaveTextContent("does not support embedded")
  expect(screen.getByRole("link", { name: "Open PDF" })).toHaveAttribute("href", "blob:report-1")
  expect(screen.getByRole("button", { name: "Download this PDF" })).toBeEnabled()
})
