import { render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { describe, expect, it } from "vitest"
import {
  DetailCard,
  DetailField,
  DetailFieldGrid,
  FindingDetailShell,
  FindingError,
  FindingHero,
  FindingLoading,
  FindingMainGrid,
} from "./FindingDetailLayout"

describe("finding detail layout", () => {
  it("renders loading and error states with a sample return route", () => {
    const { rerender } = render(
      <MemoryRouter>
        <FindingLoading />
      </MemoryRouter>,
    )
    expect(screen.getByRole("status", { name: "Loading finding" })).toBeInTheDocument()

    rerender(
      <MemoryRouter>
        <FindingError title="Finding unavailable" message="No result" backTo="/samples/S1?tab=variants" />
      </MemoryRouter>,
    )
    expect(screen.getByRole("heading", { name: "Finding unavailable" })).toBeInTheDocument()
    expect(screen.getByRole("link", { name: /Back to Sample/i })).toHaveAttribute("href", "/samples/S1?tab=variants")
  })

  it("composes hero, main, aside, cards, and fields", () => {
    render(
      <MemoryRouter>
        <FindingDetailShell>
          <FindingHero
            backTo="/samples/S1"
            title="TP53"
            subtitle="p.Arg175His"
            chips={<span>Called by caller</span>}
            actions={<button type="button">Report</button>}
            statLabel="Max VAF"
            statValue="42%"
          />
          <FindingMainGrid
            main={
              <DetailCard title="Identity" tone="success">
                <DetailFieldGrid>
                  <DetailField label="Gene">TP53</DetailField>
                  <DetailField label="HGVS" valueClassName="mono-value">p.Arg175His</DetailField>
                </DetailFieldGrid>
              </DetailCard>
            }
            aside={<DetailCard title="Evidence" tone="info">OncoKB</DetailCard>}
          />
        </FindingDetailShell>
      </MemoryRouter>,
    )

    expect(screen.getByRole("heading", { name: "TP53" })).toBeInTheDocument()
    expect(screen.getByText("Max VAF")).toBeInTheDocument()
    expect(screen.getByText("42%")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Report" })).toBeInTheDocument()
    expect(screen.getByRole("heading", { name: "Identity" })).toBeInTheDocument()
    expect(screen.getByRole("heading", { name: "Evidence" })).toBeInTheDocument()
    expect(screen.getByText("OncoKB")).toBeInTheDocument()
  })

  it("omits optional hero and aside regions", () => {
    render(
      <MemoryRouter>
        <FindingHero backTo="/samples/S1" title="CNV" />
        <FindingMainGrid main={<span>Main content</span>} />
      </MemoryRouter>,
    )
    expect(screen.getByText("Main content")).toBeInTheDocument()
    expect(screen.queryByText("Max VAF")).not.toBeInTheDocument()
  })
})
