import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { SentenceOutputEditor } from "./SentenceOutputEditor"
import { parseSentence, sentenceTemplate } from "./rule-sentence"
import type { FactDefinition, OutputNode } from "./clinical-rules-types"

const facts: FactDefinition[] = [
  { path: "asp.display_name", label: "Assay full display name", kind: "string", group: "Assay", operators: ["eq"], scopes: ["once"] },
  { path: "asp.covered_genes_count", label: "Assay covered gene count", kind: "integer", group: "Assay", operators: ["eq"], scopes: ["once"] },
]

describe("Inline report sentences", () => {
  it("writes a complete sentence with multiple typed values", () => {
    const change = vi.fn()
    render(<SentenceOutputEditor nodes={[{ type: "text", value: "" }]} facts={facts} onChange={change} />)
    fireEvent.change(screen.getByLabelText("Report sentence"), { target: { value: "Panel {{asp.display_name}} covers {{asp.covered_genes_count}} genes." } })
    expect(change).toHaveBeenLastCalledWith([
      { type: "text", value: "Panel " },
      { type: "fact", path: "asp.display_name", formatter: "text", missing: "error" },
      { type: "text", value: " covers " },
      { type: "number", path: "asp.covered_genes_count", precision: 0, unit: "", missing: "error" },
      { type: "text", value: " genes." },
    ])
  })
  it("inserts at the cursor and preserves incomplete or unknown placeholders locally", () => {
    const change = vi.fn()
    render(<SentenceOutputEditor nodes={[{ type: "text", value: "Panel  genes" }]} facts={facts} onChange={change} />)
    const editor = screen.getByLabelText("Report sentence") as HTMLTextAreaElement
    editor.setSelectionRange(6, 6)
    fireEvent.click(screen.getByText("Insert value at cursor"))
    fireEvent.click(screen.getByRole("button", { name: "Assay covered gene count" }))
    expect(editor).toHaveValue("Panel {{asp.covered_genes_count}} genes")
    change.mockClear()
    fireEvent.change(editor, { target: { value: "Panel {{asp.unknown}}" } })
    expect(screen.getByRole("alert")).toHaveTextContent("Unknown placeholder")
    expect(editor).toHaveValue("Panel {{asp.unknown}}")
    expect(change).not.toHaveBeenCalled()
  })
  it("preserves existing formatting, repeated fact settings and structured outputs", () => {
    const nodes: OutputNode[] = [
      { type: "number", path: "asp.covered_genes_count", precision: 2, unit: "x", missing: "omit" },
      { type: "text", value: " / " },
      { type: "number", path: "asp.covered_genes_count", precision: 0, unit: "", missing: "error" },
      { type: "renderer", name: "tier_summary", source: "aggregates.tier_summaries" },
    ]
    const template = sentenceTemplate(nodes)
    expect(parseSentence(template.text, template.tokens, facts)).toEqual(nodes)
  })
})
