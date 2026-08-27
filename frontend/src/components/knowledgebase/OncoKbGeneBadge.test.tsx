import { MemoryRouter } from "react-router-dom"
import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { GeneWithOncoKbBadge, OncoKbGeneBadge } from "./OncoKbGeneBadge"

describe("OncoKB gene badges", () => {
  it("links to OncoKB with record-derived context", () => {
    render(<OncoKbGeneBadge gene="TP53" record={{ description: "Tumor suppressor context" }} />)
    const link = screen.getByRole("link", { name: "TP53 is an OncoKB gene" })
    expect(link).toHaveAttribute("href", "https://www.oncokb.org/gene/TP53")
    expect(link).toHaveAttribute("title", "Tumor suppressor context")
    expect(link).toHaveAttribute("target", "_blank")
  })

  it("preserves displayed historical symbols while linking by HGNC identity", () => {
    render(
      <MemoryRouter>
        <GeneWithOncoKbBadge
          gene="OLD1"
          displayGene="OLD1"
          resolvedGene="NEW1"
          hgncId="HGNC:123"
          matchSource="previous_symbol"
          oncokbGenes={["NEW1"]}
        />
      </MemoryRouter>,
    )
    expect(screen.getByRole("link", { name: "OLD1" })).toHaveAttribute("href", "/public/gene/123/info")
    expect(screen.getByLabelText(/previous HGNC symbol/)).toBeVisible()
    expect(screen.getByRole("link", { name: "NEW1 is an OncoKB gene" })).toBeVisible()
  })

  it("does not add a marker for genes outside the cache", () => {
    render(
      <MemoryRouter>
        <GeneWithOncoKbBadge gene="GENE1" oncokbGenes={[]} />
      </MemoryRouter>,
    )
    expect(screen.getByRole("link", { name: "GENE1" })).toBeVisible()
    expect(screen.queryByText("OncoKB")).not.toBeInTheDocument()
  })
})
