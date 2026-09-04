import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { GeneKnowledgebaseSummary } from "./GeneKnowledgebaseSummary"

describe("GeneKnowledgebaseSummary", () => {
  it("shows configured sources and bounded COSMIC gene context", () => {
    render(
      <GeneKnowledgebaseSummary
        payload={{
          available_sources: ["cosmic", "civic_gene", "iarc_tp53"],
          sources: {
            civic_gene: { id: 1 },
            iarc_tp53: { applies_to_gene: false },
            cosmic: {
              availability: { cancer_gene_census: true, cgc_hallmarks: true },
              gene_census: [{ cosmic_gene_id: "COSG1", role_in_cancer: "TSG", tier: "1" }],
              hallmarks: [{ hallmark: "genome instability" }],
            },
          },
        }}
      />,
    )

    expect(screen.getByText("COSMIC")).toBeVisible()
    expect(screen.getByText("CIViC")).toBeVisible()
    expect(screen.queryByText("IARC TP53")).not.toBeInTheDocument()
    expect(screen.getByText("TSG")).toBeVisible()
    expect(screen.getAllByText("1")).toHaveLength(2)
    expect(screen.getByText("genome instability")).toBeVisible()
  })
})
