import { fireEvent, render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { describe, expect, it, vi } from "vitest"

import { TranscriptConsequencesTable } from "./TranscriptConsequencesTable"

describe("TranscriptConsequencesTable", () => {
  it("links each transcript gene to its public gene-information page", () => {
    render(
      <MemoryRouter>
        <TranscriptConsequencesTable
          rows={[{ SYMBOL: "TP53", Feature: "NM_000546.6", Consequence: "missense_variant" }]}
          selectedFeature=""
          selecting={false}
          onSelectTranscript={vi.fn()}
        />
      </MemoryRouter>,
    )

    expect(screen.getByRole("link", { name: "TP53" })).toHaveAttribute("href", "/public/gene/TP53/info")
  })

  it("renders complete consequence labels without compact truncation", () => {
    render(
      <MemoryRouter>
      <TranscriptConsequencesTable
        rows={[{ SYMBOL: "TP53", Feature: "NM_000546.6", Consequence: "coding_transcript_exon_variant", IMPACT: "MODIFIER" }]}
        selectedFeature=""
        selecting={false}
        onSelectTranscript={vi.fn()}
      />,
      </MemoryRouter>,
    )

    const consequence = screen.getByText("coding_transcript_exon_variant")
    expect(consequence).toBeVisible()
    expect(consequence).not.toHaveClass("truncate")
  })

  it("shows the latest tier for the exact alternate transcript", () => {
    render(
      <MemoryRouter>
        <TranscriptConsequencesTable
          rows={[{
            SYMBOL: "TP53",
            Feature: "NM_000546.6",
            Consequence: "missense_variant",
            tier: 2,
          }]}
          selectedFeature=""
          selecting={false}
          onSelectTranscript={vi.fn()}
        />
      </MemoryRouter>,
    )

    expect(screen.getByRole("columnheader", { name: "Tier" })).toBeVisible()
    expect(screen.getByText("2")).toBeVisible()
  })

  it("marks the selected transcript and selects another transcript", () => {
    const onSelectTranscript = vi.fn()
    render(
      <MemoryRouter>
      <TranscriptConsequencesTable
        rows={[
          { SYMBOL: "TP53", Feature: "NM_000546.6", Consequence: "missense_variant" },
          { SYMBOL: "TP53", Feature: "ENST00000269305", Consequence: "missense_variant" },
        ]}
        selectedFeature="NM_000546.6"
        selecting={false}
        onSelectTranscript={onSelectTranscript}
      />,
      </MemoryRouter>,
    )

    expect(screen.getByText("Selected")).toBeVisible()
    fireEvent.click(screen.getByRole("button", { name: "Use transcript" }))
    expect(onSelectTranscript).toHaveBeenCalledWith("ENST00000269305")
  })
})
