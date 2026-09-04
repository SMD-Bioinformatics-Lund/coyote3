import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it } from "vitest"
import {
  CosmicKnowledgeBlock,
  KnowledgebaseExplorer,
  VariantKnowledgeBlock,
  VariantIdentifierLinks,
} from "./VariantKnowledgebase"

describe("variant knowledgebase presentation", () => {
  it("renders COSMIC evidence without source sample fields", () => {
    render(
      <CosmicKnowledgeBlock
        evidence={{
          kind: "small_variant",
          match_count: 1,
          records: [{ id: "COSV123", gene: "DNMT3A", hgvsp: "p.Arg1Trp" }],
          hallmarks: [],
          actionability: [],
        }}
      />,
    )

    expect(screen.getAllByText("COSMIC")).not.toHaveLength(0)
    expect(screen.getByRole("link", { name: "COSV123" })).toBeInTheDocument()
    expect(screen.getByText("DNMT3A · p.Arg1Trp")).toBeInTheDocument()
    expect(screen.getByText("Exact variant")).toBeInTheDocument()
    expect(screen.getByText(/Matched to the reported genomic allele/)).toBeInTheDocument()
  })

  it("shows identifiers stored on the variant as separate linked lists", () => {
    render(
      <VariantIdentifierLinks
        variant={{
          cosmic_ids: ["COSV1", "COSV2"],
          dbsnp_id: "rs123",
          pubmed_ids: ["12345", "67890"],
        }}
      />,
    )

    expect(screen.getByRole("heading", { name: "Stored identifiers" })).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "COSV1" })).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "rs123" })).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "12345" })).toBeInTheDocument()
  })

  it("does not infer absent source identifiers from knowledgebase evidence", () => {
    render(<VariantIdentifierLinks variant={{ cosmic_ids: [], pubmed_ids: [] }} />)

    expect(screen.getAllByText("Not available")).toHaveLength(3)
  })

  it("distinguishes an unavailable COSMIC product from a configured product with no match", () => {
    render(
      <CosmicKnowledgeBlock
        evidence={{
          records: [],
          hallmarks: [],
          actionability: [],
          availability: { mutation_census: false, targeted_variants: true },
        }}
      />,
    )

    expect(screen.getByText("Not configured: Cancer Mutation Census.")).toBeInTheDocument()
    expect(screen.queryByText(/Targeted Screens Mutants/)).not.toBeInTheDocument()
  })

  it("searches across COSMIC sections and splits actionability values into badges", async () => {
    const user = userEvent.setup()
    render(
      <KnowledgebaseExplorer>
        <CosmicKnowledgeBlock
          evidence={{
            kind: "small_variant",
            records: [
              { id: "COSV1", gene: "TP53", hgvsp: "p.Arg1Trp" },
              { id: "COSV2", gene: "DNMT3A", hgvsp: "p.Arg2Gly" },
            ],
            classifications: [{ cosmic_phenotype_id: "COSO1", primary_site: "lung" }],
            actionability: [{ disease: "AML, MDS", drug_combination: "Drug A; Drug B", development_status: "In trials" }],
          }}
        />
      </KnowledgebaseExplorer>,
    )

    expect(screen.getByText("AML")).toHaveClass("bg-muted", "text-muted-foreground")
    expect(screen.getByText("MDS")).toBeInTheDocument()
    expect(screen.getByText("Drug A")).toHaveClass("bg-muted", "text-muted-foreground")
    expect(screen.getByText("In trials")).toHaveClass("bg-muted", "text-muted-foreground")
    await user.type(screen.getByRole("textbox", { name: "Search all knowledgebase evidence" }), "DNMT3A")

    expect(screen.getByText("DNMT3A · p.Arg2Gly")).toBeInTheDocument()
    expect(screen.queryByText("TP53 · p.Arg1Trp")).not.toBeInTheDocument()
    expect(screen.getByText("1 matching row")).toBeInTheDocument()
  })

  it("searches evidence across knowledgebase sources", async () => {
    const user = userEvent.setup()
    render(
      <KnowledgebaseExplorer>
        <VariantKnowledgeBlock source="civic" title="CIViC" searchData={{ gene: "TP53" }} defaultOpen>
          <span>CIViC TP53 evidence</span>
        </VariantKnowledgeBlock>
        <VariantKnowledgeBlock source="oncokb" title="OncoKB" searchData={{ gene: "EGFR" }} defaultOpen>
          <span>OncoKB EGFR evidence</span>
        </VariantKnowledgeBlock>
      </KnowledgebaseExplorer>,
    )

    await user.type(screen.getByRole("textbox", { name: "Search all knowledgebase evidence" }), "TP53")

    expect(screen.getByText("CIViC TP53 evidence")).toBeInTheDocument()
    expect(screen.queryByText("OncoKB EGFR evidence")).not.toBeInTheDocument()
  })
})
