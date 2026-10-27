import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import userEvent from "@testing-library/user-event"
import { useState } from "react"
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
  it("keeps commas while typing a numeric range and emits a numeric list", async () => {
    const changed = vi.fn()
    const fact: FactDefinition = { ...geneFact, path: "finding.case_vaf_percent", kind: "number", value_format: "number", operators: ["between", "exists"] }
    function Controlled() {
      const [value, setValue] = useState<Extract<Condition, { type: "predicate" }>>({ type: "predicate", fact: fact.path, operator: "between", value: [] })
      return <PredicateEditor facts={[fact]} controlledValues={{}} value={value} onChange={next => { if (next.type === "predicate") { setValue(next); changed(next) } }} />
    }
    render(<Controlled />)
    await userEvent.type(screen.getByLabelText("Condition value"), "5, 10")
    expect(screen.getByLabelText("Condition value")).toHaveValue("5, 10")
    expect(changed).toHaveBeenLastCalledWith({ type: "predicate", fact: fact.path, operator: "between", value: [5, 10] })
  })
  it("switches list availability conditions to a real boolean immediately", () => {
    const fact: FactDefinition = { ...geneFact, path: "gene_lists.snv.ids", kind: "string_list", operators: ["contains", "exists"] }
    const onChange = vi.fn()
    render(<PredicateEditor facts={[fact]} controlledValues={{}} value={{ type: "predicate", fact: fact.path, operator: "contains", value: "selected_list" }} onChange={onChange} />)
    fireEvent.change(screen.getByLabelText("Condition operator"), { target: { value: "exists" } })
    expect(onChange).toHaveBeenLastCalledWith({ type: "predicate", fact: fact.path, operator: "exists", value: true })
  })
  it("keeps a contains operand scalar when no configured flag choices exist", () => {
    const onChange = vi.fn()
    const fact: FactDefinition = {
      path: "finding.filter_flags", label: "VCF filter flags", group: "Finding", kind: "string_list",
      operators: ["contains"], scopes: ["each_finding"],
    }
    render(<PredicateEditor facts={[fact]} controlledValues={{}}
      value={{ type: "predicate", fact: fact.path, operator: "contains", value: "" }} onChange={onChange} />)
    fireEvent.change(screen.getByRole("textbox", { name: "Condition value" }), { target: { value: "PASS" } })
    expect(onChange).toHaveBeenLastCalledWith({ type: "predicate", fact: fact.path, operator: "contains", value: "PASS" })
  })
  it("selects configured raw flags for overlap conditions", async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    const fact: FactDefinition = {
      path: "finding.filter_flags", label: "VCF filter flags", group: "Finding", kind: "string_list",
      operators: ["contains", "overlaps"], scopes: ["each_finding"], value_options: ["PASS", "WARN_NOVAR"],
    }
    render(<PredicateEditor facts={[fact]} controlledValues={{}}
      value={{ type: "predicate", fact: fact.path, operator: "overlaps", value: [] }} onChange={onChange} />)
    await user.selectOptions(screen.getByRole("listbox", { name: "Condition value" }), "WARN_NOVAR")
    expect(onChange).toHaveBeenLastCalledWith({ type: "predicate", fact: fact.path, operator: "overlaps", value: ["WARN_NOVAR"] })
  })
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

  it("initializes an item-specific condition and a real count when changing collection controls", () => {
    const change = vi.fn()
    const value: Condition = { type: "collection_match", collection: "findings", quantifier: "any", where: { type: "predicate", fact: "item.kind", operator: "eq", value: "snv" } }
    const item: FactDefinition = { path: "item.selected_for", label: "Gene list selected analyses", group: "Current gene list", kind: "string_list", operators: ["contains"], scopes: ["each_item"] }
    render(<ConditionBuilder value={value} facts={[geneFact]} allFacts={[geneFact, item]} onChange={change} />)
    fireEvent.change(screen.getByLabelText("Collection"), { target: { value: "applied_gene_lists" } })
    expect(change).toHaveBeenLastCalledWith(expect.objectContaining({ collection: "applied_gene_lists", where: { type: "predicate", fact: "item.selected_for", operator: "contains", value: "" } }))
    fireEvent.change(screen.getByLabelText("Match"), { target: { value: "count" } })
    expect(change).toHaveBeenLastCalledWith(expect.objectContaining({ quantifier: "count", count: { operator: "gte", value: 1 } }))
  })
})
