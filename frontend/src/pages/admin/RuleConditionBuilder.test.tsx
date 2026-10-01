import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import type { Condition, FactDefinition } from "./clinical-rules-types"
import { ConditionBuilder, PredicateEditor } from "./RuleConditionBuilder"

const geneFact: FactDefinition = {
  path: "finding.gene",
  label: "Gene",
  group: "Finding",
  kind: "string",
  operators: ["eq", "in", "is_unknown"],
  scopes: ["each_finding"],
  value_format: "gene",
}

describe("clinical rule condition editor", () => {
  it("reports invalid gene symbols and emits a list for membership conditions", () => {
    const onChange = vi.fn()
    render(<PredicateEditor
      facts={[geneFact]}
      controlledValues={{}}
      value={{ type: "predicate", fact: geneFact.path, operator: "in", value: ["invalid gene"] }}
      onChange={onChange}
    />)
    const input = screen.getByRole("textbox", { name: "Condition value" })
    expect(input).toHaveAttribute("aria-invalid", "true")
    expect(screen.getByText(/Use HGNC gene symbols/)).toBeVisible()
    fireEvent.change(input, { target: { value: "TP53, BRCA1" } })
    expect(onChange).toHaveBeenCalledWith({
      type: "predicate", fact: geneFact.path, operator: "in", value: ["TP53", "BRCA1"],
    })
  })

  it("uses configured assay choices instead of a free-text field", () => {
    const fact: FactDefinition = {
      ...geneFact, path: "sample.asp_id", label: "Assay", value_format: "text",
    }
    const onChange = vi.fn()
    render(<PredicateEditor
      facts={[fact]}
      controlledValues={{ [fact.path]: ["demo_dna", "demo_rna"] }}
      value={{ type: "predicate", fact: fact.path, operator: "eq", value: "demo_dna" }}
      onChange={onChange}
    />)
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument()
    fireEvent.change(screen.getByDisplayValue("demo_dna"), { target: { value: "demo_rna" } })
    expect(onChange).toHaveBeenCalledWith({
      type: "predicate", fact: fact.path, operator: "eq", value: "demo_rna",
    })
  })

  it("does not request a value for an unknown-value condition", () => {
    render(<PredicateEditor
      facts={[geneFact]}
      controlledValues={{}}
      value={{ type: "predicate", fact: geneFact.path, operator: "is_unknown" }}
      onChange={vi.fn()}
    />)
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument()
    expect(screen.queryByText(/A value is required/)).not.toBeInTheDocument()
  })

  it("removes only the selected child of a grouped condition", () => {
    const first: Condition = {
      type: "predicate", fact: geneFact.path, operator: "eq", value: "TP53",
    }
    const second: Condition = { ...first, value: "BRCA1" }
    const onChange = vi.fn()
    render(<ConditionBuilder
      value={{ type: "any", children: [first, second] }}
      facts={[geneFact]}
      onChange={onChange}
    />)
    fireEvent.click(screen.getAllByTitle("Remove condition")[0])
    expect(onChange).toHaveBeenCalledWith({ type: "any", children: [second] })
    expect(first.value).toBe("TP53")
  })
})
