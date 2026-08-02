import { render, screen } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"

vi.mock("@/lib/runtime-paths", () => ({
  apiPath: (path: string) => `/coyote3/api/v1${path}`,
}))

import { SavedReportPage } from "./SavedReportPage"

function mount() {
  return render(
    <MemoryRouter initialEntries={["/samples/SAMPLE_001/reports/REPORT_7"]}>
      <Routes>
        <Route path="/samples/:id/reports/:reportId" element={<SavedReportPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe("SavedReportPage", () => {
  beforeEach(() => vi.stubGlobal("fetch", vi.fn()))

  it("loads saved HTML and exposes download and sample navigation", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response("<main>Clinical report</main>", { status: 200 }))
    mount()

    expect(screen.getByRole("status", { name: "Loading saved report" })).toBeVisible()
    const frame = await screen.findByTitle("SAMPLE_001 saved report")
    expect(frame).toHaveAttribute("srcdoc", "<main>Clinical report</main>")
    expect(screen.getByRole("link", { name: "Download" })).toHaveAttribute(
      "href",
      "/coyote3/api/v1/samples/SAMPLE_001/reports/REPORT_7/download",
    )
    expect(screen.getByRole("link", { name: "Sample" })).toHaveAttribute("href", "/samples/SAMPLE_001?tab=reports")
    expect(fetch).toHaveBeenCalledWith("/coyote3/api/v1/samples/SAMPLE_001/reports/REPORT_7/html")
  })

  it("shows the server response when report retrieval fails", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response("Report was retired", { status: 410 }))
    mount()

    expect(await screen.findByText("Report was retired")).toBeVisible()
    expect(screen.queryByTitle("SAMPLE_001 saved report")).not.toBeInTheDocument()
  })

  it("shows a safe fallback for network failures", async () => {
    vi.mocked(fetch).mockRejectedValue("offline")
    mount()

    expect(await screen.findByText("Unable to load report")).toBeVisible()
  })
})
