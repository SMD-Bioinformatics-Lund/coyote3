import { render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { describe, expect, it } from "vitest"

import { KnowledgebaseOnline } from "./KnowledgebaseOnline"
import { summarizeKnowledgebaseFamilies } from "@/lib/knowledgebase-status"

const releases = [
  { source: "cosmic_cancer_gene_census", release: "104", status: "active", records: 768 },
  { source: "cosmic_mutation_census", release: "104", status: "active", records: 2000 },
  { source: "oncokb_public", release: "Remote service", status: "configured", records: 0 },
]

describe("knowledgebase online summary", () => {
  it("groups products by top-level source and de-duplicates releases", () => {
    expect(summarizeKnowledgebaseFamilies(releases)).toEqual([
      {
        key: "cosmic",
        family: "COSMIC",
        releases: ["104"],
        products: 2,
        records: 2768,
        configured: false,
      },
      {
        key: "oncokb",
        family: "OncoKB",
        releases: ["Remote service"],
        products: 1,
        records: 0,
        configured: true,
      },
    ])
  })

  it("renders one compact entry per source family", () => {
    render(
      <MemoryRouter>
        <KnowledgebaseOnline payload={{ releases, summary: {} }} />
      </MemoryRouter>,
    )

    expect(screen.getAllByText("COSMIC")).toHaveLength(1)
    expect(screen.getAllByText("104")).toHaveLength(1)
    expect(screen.getByText("OncoKB")).toBeVisible()
    expect(screen.getByRole("link", { name: /details/i })).toHaveAttribute("href", "/knowledgebases")
  })
})
