import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({ get: vi.fn(), patch: vi.fn(), post: vi.fn(), del: vi.fn() }))
vi.mock("@/lib/api", () => ({
  api: { get: mocks.get, patch: mocks.patch, post: mocks.post, delete: mocks.del },
}))

import { CNVDetail } from "./CNVDetail"
import { FusionDetail } from "./FusionDetail"
import { TranslocationDetail } from "./TranslocationDetail"

function mount(path: string, route: string, element: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes><Route path={route} element={element} /></Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe("structural finding detail pages", () => {
  beforeEach(() => vi.clearAllMocks())

  it("renders CNV identity, copy-number evidence, overlapping genes, and status", async () => {
    mocks.get.mockResolvedValue({ data: {
      sample: { name: "DNA_001" },
      assay_group: "solid",
      subpanel: "colon",
      cnv: {
        _id: "CNV1", chr: "7", start: 100, end: 1100, type: "gain", ratio: 1,
        callers: ["CNVKIT", "MANTA"], fp: true, interesting: true,
        PR: [20, 8], SR: [10, 4], AFRQ_PON: 0.12, ACOUNT_PON: 17,
        genes: [
          { gene: "EGFR", class: "panel", effect: "gain" },
          { gene: "LANCL2", effect: "overlap" },
        ],
      },
      annotations: [],
      latest_classification: { class: 2 },
    } })

    mount("/samples/DNA_001/cnv/CNV1", "/samples/:id/cnv/:varId", <CNVDetail />)

    expect(await screen.findByRole("link", { name: "EGFR" })).toBeVisible()
    expect(screen.getByText("GAIN · 7:100-1100")).toBeVisible()
    expect(screen.getAllByText("4.00").length).toBeGreaterThan(0)
    expect(screen.getByLabelText("False positive")).toBeVisible()
    expect(screen.getByLabelText("PON artefact frequency 12.0 percent")).toBeVisible()
    expect(screen.getByText("LANCL2")).toBeVisible()
    expect(screen.getByText("CNVKIT")).toBeVisible()
    expect(mocks.get).toHaveBeenCalledWith("/samples/DNA_001/cnvs/CNV1")
  })

  it("renders a selected fusion call and all caller alternatives", async () => {
    mocks.get.mockResolvedValue({ data: {
      sample: { name: "RNA_001" }, assay_group: "fusion", subpanel: "base",
      fusion: {
        _id: "F1", genes: ["BCR", "ABL1"], gene1: "BCR", gene2: "ABL1", callers: ["ARRIBA", "STARFUSION"],
        calls: [
          { selected: true, caller: "ARRIBA", breakpoint1: "22:100", breakpoint2: "9:200", spanpairs: 12, spanreads: 7, effect: "in-frame" },
          { selected: false, caller: "STARFUSION", breakpoint1: "22:101", breakpoint2: "9:201", spanpairs: 10, spanreads: 6 },
        ],
      },
      annotations: [], latest_classification: { class: 1 },
    } })

    mount("/samples/RNA_001/fusion/F1", "/samples/:id/fusion/:varId", <FusionDetail />)

    expect(await screen.findByRole("heading", { name: /^BCR--ABL1/ })).toBeVisible()
    expect(screen.getAllByText(/22:100 \| 9:200/).length).toBeGreaterThanOrEqual(2)
    expect(screen.getAllByText("arriba").length).toBeGreaterThanOrEqual(2)
    expect(screen.getAllByText("starfusion").length).toBeGreaterThanOrEqual(2)
    expect(screen.getByRole("button", { name: "Pick" })).toBeEnabled()
    expect(mocks.get).toHaveBeenCalledWith("/samples/RNA_001/fusions/F1")
  })

  it("renders translocation annotations and sample read support", async () => {
    const annotation = {
      Gene_Name: "KMT2A", Feature_ID: "ENST00000534358", HGVS_p: "p.Gly1Val",
      HGVS_c: "c.1G>T", Annotation: "transcript_ablation", Rank: "1/10", BioType: "protein_coding",
    }
    mocks.get.mockResolvedValue({ data: {
      sample: { name: "DNA_002" }, assay_group: "hematology", subpanel: "hem",
      translocation: {
        _id: "T1", CHROM: "11", POS: 118307000, ALT: "N[4:12345[", QUAL: 80,
        INFO: { SVTYPE: "BND", variant_callers: ["MANTA"], ANN: [annotation], UNIQUE_READS: 22 },
        GT: [{ type: "case", PR: [100, 20], SR: [50, 15] }],
      },
      annotations: [], latest_classification: { class: 2 },
      vep_conseq_translations: { transcript_ablation: { display_name: "Transcript ablation" } },
    } })

    mount("/samples/DNA_002/translocation/T1", "/samples/:id/translocation/:varId", <TranslocationDetail />)

    expect(await screen.findByText("Translocation Identity")).toBeVisible()
    expect(screen.getAllByText("KMT2A").length).toBeGreaterThan(0)
    expect(screen.getAllByText("ENST00000534358").length).toBeGreaterThan(0)
    expect(screen.getAllByText("Transcript ablation").length).toBeGreaterThan(0)
    expect(screen.getByText("100/20")).toBeVisible()
    expect(screen.getByText("50/15")).toBeVisible()
    expect(mocks.get).toHaveBeenCalledWith("/samples/DNA_002/translocations/T1")
  })

  it.each([
    ["CNV", "/samples/DNA_001/cnv/missing", "/samples/:id/cnv/:varId", <CNVDetail key="cnv" />, "Error loading CNV"],
    ["fusion", "/samples/RNA_001/fusion/missing", "/samples/:id/fusion/:varId", <FusionDetail key="fusion" />, "Error loading fusion"],
    ["translocation", "/samples/DNA_001/translocation/missing", "/samples/:id/translocation/:varId", <TranslocationDetail key="translocation" />, "Error loading translocation"],
  ])("shows a recoverable %s error state", async (_name, path, route, element, title) => {
    mocks.get.mockRejectedValue(new Error("Finding unavailable"))
    mount(path, route, element)

    expect(await screen.findByRole("heading", { name: title })).toBeVisible()
    expect(screen.getByText("Finding unavailable")).toBeVisible()
    expect(screen.getByRole("link", { name: "Back to Sample" })).toBeVisible()
  })
})
