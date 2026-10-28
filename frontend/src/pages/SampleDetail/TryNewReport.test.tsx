import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, expect, it, vi } from "vitest"
import { api } from "@/lib/api"
import { downloadBlob, downloadText } from "@/lib/browser-download"
import { TryNewReport } from "./TryNewReport"

vi.mock("@/lib/api", () => ({ api: { get: vi.fn(), post: vi.fn() } }))
vi.mock("@/lib/browser-download", () => ({ downloadBlob: vi.fn(), downloadText: vi.fn() }))
const revoke = vi.fn()
const trial = { html: "<html><style>body{color:black}</style><body>Synthetic findings</body></html>",
  pdf_base64: btoa("%PDF-synthetic\n%%EOF"), filename: "synthetic_trial", snapshot_count: 3 }

beforeEach(() => {
  vi.resetAllMocks()
  vi.stubGlobal("URL", { createObjectURL: vi.fn(() => "blob:synthetic-pdf"), revokeObjectURL: revoke })
  vi.mocked(api.get).mockResolvedValue({ data: trial, status: 200 })
})
afterEach(() => vi.unstubAllGlobals())

it("previews and downloads the same temporary HTML/PDF without a save request", async () => {
  const close = vi.fn()
  const view = render(<TryNewReport sampleId="SYNTHETIC" reportType="dna" onClose={close} />)
  await screen.findByText(/3 included findings/)
  expect(api.get).toHaveBeenCalledWith("/samples/SYNTHETIC/reports/dna/try-new", expect.objectContaining({ cache: "no-store" }))
  expect(screen.getByTitle("New report HTML preview")).toHaveAttribute("srcdoc", trial.html)
  fireEvent.click(screen.getByRole("button", { name: "Download HTML" }))
  expect(downloadText).toHaveBeenCalledWith(trial.html, "synthetic_trial.html", "text/html;charset=utf-8")
  fireEvent.click(screen.getByRole("tab", { name: "PDF preview" }))
  expect(screen.getByTitle("New report PDF preview")).toHaveAttribute("src", "blob:synthetic-pdf")
  fireEvent.click(screen.getByRole("button", { name: "Download PDF" }))
  expect(downloadBlob).toHaveBeenCalledWith(expect.objectContaining({ type: "application/pdf" }), "synthetic_trial.pdf")
  expect(screen.queryByRole("button", { name: /Save report/i })).not.toBeInTheDocument()
  expect(api.post).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole("button", { name: "Current report" }))
  expect(close).toHaveBeenCalledOnce()
  view.unmount()
  expect(revoke).toHaveBeenCalledWith("blob:synthetic-pdf")
})

it("warns about missing reporting rules while allowing report downloads", async () => {
  const warning = "No published reporting rules. The report has no automatic summary."
  vi.mocked(api.get).mockResolvedValue({ data: { ...trial, reporting_warning: warning }, status: 200 })
  render(<TryNewReport sampleId="SYNTHETIC" reportType="dna" onClose={vi.fn()} />)
  expect(await screen.findByRole("alert")).toHaveTextContent(warning)
  expect(screen.getByRole("button", { name: "Download PDF" })).toBeEnabled()
})

it("shows authorization and rendering failures without enabling downloads", async () => {
  vi.mocked(api.get).mockRejectedValue(new Error("Report preview permission required"))
  render(<TryNewReport sampleId="SYNTHETIC" reportType="rna" onClose={vi.fn()} />)
  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Report preview permission required"))
  expect(screen.getByRole("button", { name: "Download HTML" })).toBeDisabled()
  expect(screen.getByRole("button", { name: "Download PDF" })).toBeDisabled()
})
