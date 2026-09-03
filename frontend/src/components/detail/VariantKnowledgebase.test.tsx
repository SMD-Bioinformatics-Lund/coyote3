import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import {
  CosmicKnowledgeBlock,
  VariantIdentifiersCard,
} from "./VariantKnowledgebase"

describe("variant knowledgebase presentation", () => {
  it("renders COSMIC evidence without source sample fields", () => {
    render(
      <CosmicKnowledgeBlock
        evidence={{
          match_count: 1,
          records: [{ id: "COSV123", gene: "DNMT3A", hgvsp: "p.Arg1Trp" }],
          hallmarks: [],
          actionability: [],
        }}
      />,
    )

    expect(screen.getByText("COSMIC")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "COSV123" })).toBeInTheDocument()
    expect(screen.getByText("DNMT3A · p.Arg1Trp")).toBeInTheDocument()
  })

  it("shows identifiers stored on the variant as separate linked lists", () => {
    render(
      <VariantIdentifiersCard
        variant={{
          cosmic_ids: ["COSV1", "COSV2"],
          dbsnp_id: "rs123",
          pubmed_ids: ["12345", "67890"],
        }}
      />,
    )

    expect(screen.getByRole("heading", { name: "Variant Identifiers" })).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "COSV1" })).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "rs123" })).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "12345" })).toBeInTheDocument()
  })

  it("does not infer absent source identifiers from knowledgebase evidence", () => {
    render(<VariantIdentifiersCard variant={{ cosmic_ids: [], pubmed_ids: [] }} />)

    expect(screen.getAllByText("Not available")).toHaveLength(3)
  })
})
