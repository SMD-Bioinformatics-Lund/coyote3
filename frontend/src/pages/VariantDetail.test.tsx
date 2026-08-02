import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { api } from "@/lib/api"
import { VariantDetail } from "./VariantDetail"

vi.mock("@/lib/api", () => ({
  api: { get: vi.fn(), patch: vi.fn() },
}))

vi.mock("@/lib/notifications", () => ({ notifyActionError: vi.fn() }))

vi.mock("@/components/comments/CommentsPanel", () => ({
  CommentsPanel: ({ title, onUseAsDraft }: { title: string; onUseAsDraft?: (text: string) => void }) => (
    <section>
      <h3>{title}</h3>
      {onUseAsDraft ? <button onClick={() => onUseAsDraft("Existing annotation")}>Use annotation</button> : null}
    </section>
  ),
}))

vi.mock("@/components/detail/VariantActionButtons", () => ({
  VariantActionButtons: ({ sampleId }: { sampleId: string }) => <div>Actions for {sampleId}</div>,
}))

vi.mock("@/components/detail/FindingDetailCards", () => ({
  ClassificationsCard: ({ latest }: { latest?: { class?: number } }) => (
    <div>Latest tier {latest?.class ?? "none"}</div>
  ),
}))

vi.mock("@/components/knowledgebase/OncoKbGeneBadge", () => ({
  GeneWithOncoKbBadge: ({ displayGene, gene }: { displayGene?: string; gene?: string }) => (
    <span>{displayGene || gene || "-"}</span>
  ),
}))

const detailPayload = {
  sample: { name: "CASE_001", assay: "hema_gmsv1", subpanel: "hem" },
  assay_group: "hematology",
  subpanel: "hem",
  latest_classification: { class: 2 },
  variant: {
    _id: "variant-1",
    CHROM: "17",
    POS: 76736896,
    REF: "T",
    ALT: ["C"],
    FILTER: ["PASS"],
    variant_class: "SNV",
    callers: ["freebayes"],
    GT: [{ type: "case", AF: 0.123, AO: 123, DP: 1000 }],
    INFO: {
      selected_CSQ: {
        SYMBOL: "SRSF2",
        VEP_SYMBOL: "SRSF2",
        HGNC_ID: "HGNC:10783",
        Feature: "NM_003016.4",
        HGVSc: "NM_003016.4:c.265A>G",
        HGVSp: "p.Met89Val",
        Consequence: ["missense_variant"],
        IMPACT: "MODERATE",
        EXON: "1/2",
      },
    },
  },
  transcripts: [
    {
      Feature: "ENST00000359995",
      SYMBOL: "SRSF2",
      HGVSc: "ENST00000359995:c.265A>G",
      HGVSp: "p.Met89Val",
      Consequence: ["missense_variant"],
      IMPACT: "MODERATE",
      transcript_tags: ["ensembl_mane_select"],
      is_canonical: true,
      canonical_source: "vep_canonical",
    },
  ],
  annotations: [],
  other_classifications: [],
  in_other_samples: [],
  pon: [],
  oncokb_gene: { oncokb_annotated: true, gene_type: "ONCOGENE" },
  clinpgx_gene: { pharmgkb_accession_id: "PA35699", is_vip: true },
  vep_conseq_translations: {
    missense_variant: { display_name: "missense", description: "A protein-changing substitution." },
  },
}

function CurrentPath() {
  return <output data-testid="path">{useLocation().pathname}</output>
}

function renderDetail(path = "/samples/legacy-id/variant/variant-1") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[{ pathname: path, state: { from: "/samples/CASE_001/snvs" } }]}>
        <CurrentPath />
        <Routes>
          <Route path="/samples/:id/variant/:varId" element={<VariantDetail />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe("VariantDetail", () => {
  beforeEach(() => {
    vi.mocked(api.get).mockReset()
    vi.mocked(api.patch).mockReset()
  })

  it("shows a loading state while the finding request is pending", () => {
    vi.mocked(api.get).mockImplementation(() => new Promise(() => undefined) as never)
    renderDetail()
    expect(screen.getByRole("status", { name: "Loading finding" })).toBeVisible()
  })

  it("shows the backend error and a sample return link", async () => {
    vi.mocked(api.get).mockRejectedValue(new Error("Variant was not found"))
    renderDetail()
    expect(await screen.findByText("Error loading variant")).toBeVisible()
    expect(screen.getByText("Variant was not found")).toBeVisible()
  })

  it("renders clinical identity and normalizes an object-id route to the sample name", async () => {
    vi.mocked(api.get).mockImplementation(async (url: string) => {
      if (url === "/public/filter-flags/metadata") return { data: {} } as never
      return { data: detailPayload } as never
    })
    renderDetail()

    await waitFor(() => expect(screen.getByTestId("path")).toHaveTextContent("/samples/CASE_001/variant/variant-1"))
    expect(await screen.findByRole("heading", { name: "SRSF2" })).toBeVisible()
    expect(screen.getAllByText("p.Met89Val").length).toBeGreaterThan(0)
    expect(screen.getAllByText("SRSF2").length).toBeGreaterThan(0)
    expect(screen.getByText("17:76736896 T>C")).toBeVisible()
    expect(screen.getByText("Latest tier 2")).toBeVisible()
    expect(screen.getByText("Actions for CASE_001")).toBeVisible()
  })

  it("persists a selected alternate transcript and refreshes the detail", async () => {
    vi.mocked(api.get).mockImplementation(async (url: string) => {
      if (url === "/public/filter-flags/metadata") return { data: {} } as never
      return { data: detailPayload } as never
    })
    vi.mocked(api.patch).mockResolvedValue({ data: { ok: true } } as never)
    renderDetail("/samples/CASE_001/variant/variant-1")

    const selectButton = await screen.findByRole("button", { name: "Use transcript" })
    fireEvent.click(selectButton)
    await waitFor(() => {
      expect(api.patch).toHaveBeenCalledWith(
        "/samples/CASE_001/small-variants/variant-1/selected-transcript",
        { feature_id: "ENST00000359995" },
      )
    })
  })

  it("fetches and presents public OncoKB and ClinPGx context on demand", async () => {
    vi.mocked(api.get).mockImplementation(async (url: string) => {
      if (url === "/public/filter-flags/metadata") return { data: {} } as never
      if (url.endsWith("/oncokb-public")) {
        return {
          data: {
            status: "ok",
            query: { hgvsg: "17:g.76736896T>C", referenceGenome: "GRCh38" },
            response: { dataVersion: "v7.3", geneExist: true, variantExist: false, geneSummary: "SRSF2 summary" },
          },
        } as never
      }
      if (url.endsWith("/clinpgx-public")) {
        return {
          data: {
            status: "ok",
            query: { clinpgx_id: "PA35699" },
            response: { clinpgx_id: "PA35699", symbol: "SRSF2", counts: { guidelines: 2 }, flags: { cpic_gene: true } },
          },
        } as never
      }
      return { data: detailPayload } as never
    })
    renderDetail("/samples/CASE_001/variant/variant-1")

    fireEvent.click(await screen.findByText("OncoKB API"))
    fireEvent.click(screen.getByRole("button", { name: "Fetch public OncoKB" }))
    expect(await screen.findByText("SRSF2 summary")).toBeVisible()

    fireEvent.click(screen.getByText("ClinPGx"))
    fireEvent.click(screen.getByRole("button", { name: "Fetch ClinPGx" }))
    expect(await screen.findAllByText("PA35699")).not.toHaveLength(0)
  })
})
