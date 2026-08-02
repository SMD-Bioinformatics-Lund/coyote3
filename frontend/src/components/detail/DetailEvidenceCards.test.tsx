import { render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { describe, expect, it } from "vitest"

import { DetailDataTable, DetailMetricTable, EvidenceBadge, ExternalLinksCard } from "./DetailEvidenceCards"

describe("detail evidence components", () => {
  it("filters absent metrics while retaining linked evidence", () => {
    render(<DetailMetricTable metrics={[{ label: "Missing", value: null }, { label: "dbSNP", value: "rs1", href: "https://example.test/rs1" }, { label: "Depth", value: 450 }]} />)
    expect(screen.queryByText("Missing")).not.toBeInTheDocument()
    expect(screen.getByRole("link", { name: "rs1" })).toHaveAttribute("href", "https://example.test/rs1")
    expect(screen.getByText("450")).toBeInTheDocument()
  })

  it("renders empty and populated detail tables", () => {
    const { rerender } = render(<DetailDataTable rows={[]} columns={[]} empty="No transcripts." />)
    expect(screen.getByText("No transcripts.")).toBeInTheDocument()
    rerender(<DetailDataTable rows={[{ gene: "TP53" }]} columns={[{ key: "gene", header: "Gene", render: (row) => row.gene }]} />)
    expect(screen.getByRole("columnheader", { name: "Gene" })).toBeInTheDocument()
    expect(screen.getByText("TP53")).toBeInTheDocument()
  })

  it("renders semantic evidence badges and omits empty external-link cards", () => {
    const view = render(<MemoryRouter><><EvidenceBadge tone="warning">Moderate</EvidenceBadge><ExternalLinksCard links={[]} /></></MemoryRouter>)
    expect(screen.getByText("Moderate")).toHaveClass("text-warn")
    expect(screen.queryByText("External Evidence")).not.toBeInTheDocument()
    view.rerender(<MemoryRouter><ExternalLinksCard links={[{ label: "ClinVar", value: "record", href: "https://example.test" }]} /></MemoryRouter>)
    expect(screen.getByRole("link", { name: "ClinVar" })).toHaveAttribute("target", "_blank")
  })
})
