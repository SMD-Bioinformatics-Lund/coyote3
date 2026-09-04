import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
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

  it("reveals table rows beyond the configured initial limit", async () => {
    const user = userEvent.setup()
    const rows = Array.from({ length: 12 }, (_, index) => ({ value: `Row ${index + 1}` }))

    render(
      <DetailDataTable
        rows={rows}
        initialRows={10}
        columns={[{ key: "value", header: "Value", render: (row) => row.value }]}
      />,
    )

    expect(screen.getByText("Row 10")).toBeInTheDocument()
    expect(screen.queryByText("Row 11")).not.toBeInTheDocument()
    expect(screen.getByText("Showing 10 of 12")).toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: "Show all 12" }))

    expect(screen.getByText("Row 11")).toBeInTheDocument()
    expect(screen.getByText("Showing 12 of 12")).toBeInTheDocument()
  })

  it("applies the same row disclosure to metric tables", async () => {
    const user = userEvent.setup()
    const metrics = Array.from({ length: 11 }, (_, index) => ({
      label: `Metric ${index + 1}`,
      value: index + 1,
    }))

    render(<DetailMetricTable metrics={metrics} initialRows={10} />)

    expect(screen.queryByText("Metric 11")).not.toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Show all 11" }))
    expect(screen.getByText("Metric 11")).toBeInTheDocument()
  })

  it("renders semantic evidence badges and omits empty external-link cards", () => {
    const view = render(<MemoryRouter><><EvidenceBadge tone="warning">Moderate</EvidenceBadge><ExternalLinksCard links={[]} /></></MemoryRouter>)
    expect(screen.getByText("Moderate")).toHaveClass("text-warn")
    expect(screen.queryByText("External Evidence")).not.toBeInTheDocument()
    view.rerender(<MemoryRouter><ExternalLinksCard links={[{ label: "ClinVar", value: "record", href: "https://example.test" }]} /></MemoryRouter>)
    expect(screen.getByRole("link", { name: "ClinVar" })).toHaveAttribute("target", "_blank")
  })

  it("keeps an external evidence card when it contains identifier content", () => {
    render(<ExternalLinksCard links={[]}><span>Stored identifiers</span></ExternalLinksCard>)
    expect(screen.getByRole("heading", { name: "External Evidence" })).toBeInTheDocument()
    expect(screen.getByText("Stored identifiers")).toBeInTheDocument()
  })
})
