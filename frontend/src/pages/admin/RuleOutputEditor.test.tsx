import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { OutputEditor } from "./RuleOutputEditor"
import { RuleTerminologyEditor } from "./RuleTerminologyEditor"

describe("Report composition controls", () => {
  it("finds an assay value and inserts a typed numeric output", () => {
    const change = vi.fn()
    render(<OutputEditor nodes={[{ type: "text", value: "Genes: " }]} facts={[{ path: "asp.covered_genes_count", label: "Assay covered gene count", group: "Assay", kind: "integer", operators: ["eq"], scopes: ["once"] }]} onChange={change} />)
    fireEvent.click(screen.getByText(/Insert dynamic value/))
    fireEvent.change(screen.getByLabelText("Search report values"), { target: { value: "count" } })
    fireEvent.click(screen.getByRole("button", { name: "Assay covered gene count" }))
    expect(change).toHaveBeenCalledWith([{ type: "text", value: "Genes: " }, { type: "number", path: "asp.covered_genes_count", precision: 0, unit: "", missing: "error" }])
  })
  it("moves values between text fragments without changing their content", () => {
    const change = vi.fn()
    const nodes = [{ type: "text" as const, value: "before " }, { type: "text" as const, value: " after" }]
    render(<OutputEditor nodes={nodes} facts={[]} onChange={change} />)
    fireEvent.click(screen.getByLabelText("Move output part 2 up"))
    expect(change).toHaveBeenCalledWith([nodes[1], nodes[0]])
  })
  it("edits structured sentence fragments while preserving spacing and other phrases", () => {
    const change = vi.fn()
    render(<RuleTerminologyEditor value={{ base_text: "Original ", paired_text: "Control " }} change={change} />)
    fireEvent.change(screen.getByLabelText("Structured wording: base text"), { target: { value: "Updated " } })
    expect(change).toHaveBeenCalledWith({ base_text: "Updated ", paired_text: "Control " })
  })
})
