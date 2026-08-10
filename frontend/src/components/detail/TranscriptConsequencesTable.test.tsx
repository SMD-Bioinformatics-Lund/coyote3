import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { TranscriptConsequencesTable } from "./TranscriptConsequencesTable"

describe("TranscriptConsequencesTable", () => {
  it("renders complete consequence labels without compact truncation", () => {
    render(
      <TranscriptConsequencesTable
        rows={[{ SYMBOL: "TP53", Feature: "NM_000546.6", Consequence: "coding_transcript_exon_variant", IMPACT: "MODIFIER" }]}
        selectedFeature=""
        selecting={false}
        onSelectTranscript={vi.fn()}
      />,
    )

    const consequence = screen.getByText("coding_transcript_exon_variant")
    expect(consequence).toBeVisible()
    expect(consequence).not.toHaveClass("truncate")
  })

  it("marks the selected transcript and selects another transcript", () => {
    const onSelectTranscript = vi.fn()
    render(
      <TranscriptConsequencesTable
        rows={[
          { SYMBOL: "TP53", Feature: "NM_000546.6", Consequence: "missense_variant" },
          { SYMBOL: "TP53", Feature: "ENST00000269305", Consequence: "missense_variant" },
        ]}
        selectedFeature="NM_000546.6"
        selecting={false}
        onSelectTranscript={onSelectTranscript}
      />,
    )

    expect(screen.getByText("Selected")).toBeVisible()
    fireEvent.click(screen.getByRole("button", { name: "Use transcript" }))
    expect(onSelectTranscript).toHaveBeenCalledWith("ENST00000269305")
  })
})
