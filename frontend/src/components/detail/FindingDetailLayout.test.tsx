import { fireEvent, render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { describe, expect, it } from "vitest"
import {
  DetailCard,
  DetailField,
  DetailFieldGrid,
  FindingDetailShell,
  FindingError,
  DetailHero,
  DetailHeroSubtitle,
  FindingCallerMeta,
  FindingDetailHero,
  FindingIdentityCard,
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
    const { container } = render(
      <MemoryRouter>
        <FindingDetailShell>
          <DetailHero
            backTo="/samples/S1"
            eyebrow="hema_gmsv1 • production"
            title="S1"
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

    expect(screen.getByRole("heading", { name: "S1" })).toBeInTheDocument()
    expect(screen.getByText("hema_gmsv1 • production")).toBeInTheDocument()
    expect(screen.getByText("Max VAF")).toBeInTheDocument()
    expect(screen.getByText("42%")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Report" })).toBeInTheDocument()
    expect(screen.getByRole("heading", { name: "Identity" })).toBeInTheDocument()
    expect(screen.getByRole("heading", { name: "Evidence" })).toBeInTheDocument()
    expect(screen.getByText("OncoKB")).toBeInTheDocument()
    expect(container.firstElementChild).toHaveClass(
      "page-shell-fluid",
      "responsive-page-padding",
      "responsive-section-gap",
      "3xl:content-ultrawide",
    )
  })

  it("omits optional hero and aside regions", () => {
    render(
      <MemoryRouter>
        <DetailHero backTo="/samples/S1" title="CNV" />
        <FindingMainGrid main={<span>Main content</span>} />
      </MemoryRouter>,
    )
    expect(screen.getByText("Main content")).toBeInTheDocument()
    expect(screen.queryByText("Max VAF")).not.toBeInTheDocument()
  })

  it("renders the shared slim subtitle and sample badge", () => {
    render(
      <MemoryRouter>
        <DetailHeroSubtitle sampleHref="/samples/S1" sampleName="S1">
          p.Arg175His
        </DetailHeroSubtitle>
      </MemoryRouter>,
    )

    expect(screen.getByText("p.Arg175His")).toHaveClass("detail-hero-subtitle")
    expect(screen.getByRole("link", { name: "Sample S1" })).toHaveClass("detail-hero-sample-chip")
  })

  it("renders a branded gene eyebrow and expands a long finding identity", () => {
    const identity = "p.Val1060delinsAspGluAspTerLongClinicalFindingIdentityThatRequiresExpansion"
    render(
      <MemoryRouter>
        <FindingDetailHero
          backTo="/samples/S1"
          genes={["DNMT3A"]}
          identity={identity}
          sampleHref="/samples/S1"
          sampleName="S1"
        />
      </MemoryRouter>,
    )

    expect(screen.getByRole("link", { name: "DNMT3A" })).toHaveClass("brand-gradient-text")
    expect(screen.getByRole("link", { name: "Sample S1" })).toBeVisible()
    expect(screen.queryByText(identity)).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "Show full value" }))
    expect(screen.getByText(identity)).toBeVisible()
  })

  it("places compact caller provenance between the statistic and actions", () => {
    const { container } = render(
      <MemoryRouter>
        <FindingDetailHero
          backTo="/samples/S1"
          genes={["DNMT3A"]}
          identity="p.Ser714Cys"
          sampleHref="/samples/S1"
          sampleName="S1"
          statLabel="Max VAF"
          statValue="22.1%"
          callers={
            <FindingCallerMeta>
              <span className="type-badge">freebayes</span>
            </FindingCallerMeta>
          }
          actions={<button type="button">Interesting</button>}
        />
      </MemoryRouter>,
    )

    const callerMeta = container.querySelector(".detail-hero-caller-meta")
    expect(callerMeta).not.toBeNull()
    expect(callerMeta).toHaveTextContent("Called by")
    expect(callerMeta).toHaveTextContent("freebayes")

    const rightRail = callerMeta?.parentElement
    expect(rightRail?.children[0]).toHaveTextContent("Max VAF22.1%")
    expect(rightRail?.children[1]).toBe(callerMeta)
    expect(rightRail?.children[2]).toHaveTextContent("Interesting")
    expect(screen.getByRole("link", { name: "Sample S1" }).parentElement).not.toHaveTextContent("Called by")
  })

  it("renders a shared identity summary with labelled fields", () => {
    render(
      <MemoryRouter>
        <FindingIdentityCard title="CNV Identity">
          <DetailField label="Region">7:100-1100</DetailField>
          <DetailField label="Type">Gain</DetailField>
        </FindingIdentityCard>
      </MemoryRouter>,
    )

    expect(screen.getByRole("heading", { name: "CNV Identity" })).toBeVisible()
    expect(screen.getByText("Region")).toBeVisible()
    expect(screen.getByText("7:100-1100")).toBeVisible()
  })
})
