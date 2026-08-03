import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  put: vi.fn(),
  delete: vi.fn(),
  success: vi.fn(),
  error: vi.fn(),
}))

vi.mock("@/lib/api", () => ({ api: { put: mocks.put, delete: mocks.delete } }))
vi.mock("@/lib/notifications", () => ({
  notifySuccess: mocks.success,
  notifyActionError: mocks.error,
}))

import { FiltersSidebar } from "./FiltersSidebar"

const sample = {
  name: "CASE_001",
  filters: {
    somatic: {
      snv: {
        min_depth: 100,
        min_alt_reads: 5,
        min_freq: 0.02,
        max_freq: 1,
        max_control_freq: 0.05,
        max_popfreq: 0.01,
        vep_consequences: ["missense"],
        snvlists: ["heme"],
      },
      cnv: { min_cnv_size: 5000, cnvlists: ["heme_cnv"], cnveffects: ["gain"] },
      translocation: { fusionlists: ["fusion_core"] },
    },
    germline: {
      snv: { min_depth: 30, min_alt_reads: 3, min_freq: 0.3, max_freq: 1, max_popfreq: 0.001 },
    },
  },
}

const context = {
  snv_genelist_options: [
    { isgl_id: "heme", display_name: "Hematology" },
    { isgl_id: "myeloid", display_name: "Myeloid" },
  ],
  cnvlist_options: [{ isgl_id: "heme_cnv", display_name: "Hematology CNV" }],
  fusionlist_options: [{ isgl_id: "fusion_core", display_name: "Core fusions" }],
}

function renderSidebar(props: Partial<React.ComponentProps<typeof FiltersSidebar>> = {}) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  vi.spyOn(queryClient, "invalidateQueries").mockResolvedValue(undefined)
  vi.spyOn(queryClient, "refetchQueries").mockResolvedValue(undefined)
  const result = render(
    <QueryClientProvider client={queryClient}>
      <FiltersSidebar sampleId="CASE_001" sample={sample} context={context} activeTab="snvs" {...props} />
    </QueryClientProvider>,
  )
  return { ...result, queryClient }
}

async function expand(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByTitle("Expand filters"))
}

describe("FiltersSidebar", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.put.mockResolvedValue({ data: { ok: true } })
    mocks.delete.mockResolvedValue({ data: { ok: true } })
  })

  it("starts collapsed and exposes the active intent and table", () => {
    renderSidebar()
    expect(screen.getByText("somatic snvs filters")).toBeVisible()
    expect(screen.queryByText("Small Variant Thresholds")).not.toBeInTheDocument()
  })

  it("shows somatic SNV controls, configured gene lists, and selected consequences", async () => {
    const user = userEvent.setup()
    renderSidebar()
    await expand(user)

    expect(screen.getByLabelText("Min depth")).toHaveValue(100)
    expect(screen.getByLabelText("Max normal VAF")).toHaveValue(0.05)
    expect(screen.getByRole("checkbox", { name: "Missense" })).toBeChecked()
    expect(screen.getByRole("checkbox", { name: "Hematology" })).toBeChecked()
    expect(screen.getByRole("checkbox", { name: "Myeloid" })).not.toBeChecked()
  })

  it("isolates germline filters and omits the somatic control-frequency field", async () => {
    const user = userEvent.setup()
    renderSidebar({ intent: "germline" })
    await expand(user)

    expect(screen.getByLabelText("Min depth")).toHaveValue(30)
    expect(screen.queryByLabelText("Max normal VAF")).not.toBeInTheDocument()
  })

  it("merges edited values into the active intent and refreshes sample queries", async () => {
    const user = userEvent.setup()
    const { queryClient } = renderSidebar()
    await expand(user)
    const depth = screen.getByLabelText("Min depth")
    await user.clear(depth)
    await user.type(depth, "120")
    await user.click(screen.getByRole("checkbox", { name: "Myeloid" }))
    await user.click(screen.getByRole("button", { name: "Apply" }))

    await waitFor(() => expect(mocks.put).toHaveBeenCalledOnce())
    expect(mocks.put).toHaveBeenCalledWith("/samples/CASE_001/filters", {
      filters: expect.objectContaining({
        somatic: expect.objectContaining({
          snv: expect.objectContaining({ min_depth: 120, snvlists: ["heme", "myeloid"] }),
        }),
        germline: sample.filters.germline,
      }),
    })
    expect(queryClient.invalidateQueries).toHaveBeenCalledWith({ queryKey: ["sample", "CASE_001"] })
    expect(queryClient.refetchQueries).toHaveBeenCalledWith({ queryKey: ["sample-variants", "CASE_001"], type: "active" })
    expect(mocks.success).toHaveBeenCalledWith(
      "Filters applied",
      "snvs filters were saved for CASE_001.",
      "Sample filters",
      expect.objectContaining({ sampleName: "CASE_001" }),
    )
  })

  it("renders analysis-specific CNV controls", async () => {
    const user = userEvent.setup()
    renderSidebar({ activeTab: "cnvs" })
    await expand(user)

    expect(screen.getByLabelText("Min size")).toHaveValue(5000)
    expect(screen.getByRole("checkbox", { name: "Hematology CNV" })).toBeChecked()
    expect(screen.getByRole("checkbox", { name: "Gain" })).toBeChecked()
    expect(screen.queryByText("Consequences")).not.toBeInTheDocument()
  })

  it("edits DNA translocation gene lists independently", async () => {
    const user = userEvent.setup()
    renderSidebar({ activeTab: "translocations" })
    await expand(user)

    expect(screen.getByText("Fusion/Translocation Gene Lists")).toBeVisible()
    expect(screen.getByRole("checkbox", { name: "Core fusions" })).toBeChecked()
    await user.click(screen.getByRole("checkbox", { name: "Core fusions" }))
    await user.click(screen.getByRole("button", { name: "Apply" }))

    await waitFor(() => expect(mocks.put).toHaveBeenCalledOnce())
    expect(mocks.put).toHaveBeenCalledWith("/samples/CASE_001/filters", {
      filters: expect.objectContaining({
        somatic: expect.objectContaining({
          snv: sample.filters.somatic.snv,
          cnv: sample.filters.somatic.cnv,
          translocation: { fusionlists: [] },
        }),
      }),
    })
  })

  it("confirms reset success and reports update failures", async () => {
    const user = userEvent.setup()
    mocks.put.mockRejectedValueOnce(new Error("filter write failed"))
    renderSidebar()
    await expand(user)

    await user.click(screen.getByRole("button", { name: "Apply" }))
    await waitFor(() => expect(mocks.error).toHaveBeenCalledWith(
      "Unable to apply filters",
      expect.any(Error),
      "Sample filters",
      expect.objectContaining({ sampleName: "CASE_001" }),
    ))

    await user.click(screen.getByTitle("Reset filters"))
    await waitFor(() => expect(mocks.delete).toHaveBeenCalledWith("/samples/CASE_001/filters"))
    expect(mocks.success).toHaveBeenCalledWith(
      "Filters reset",
      expect.stringContaining("Default assay configuration filters were restored"),
      "Sample filters",
      expect.objectContaining({ sampleName: "CASE_001" }),
    )
  })
})
