import { useState } from "react"
import { fireEvent, render, screen, within } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { QueryConditionBuilder } from "./QueryConditionBuilder"
import type { QueryCondition, QueryConditionCatalog } from "./query-condition-types"

const catalog: QueryConditionCatalog = {
  fields: { fusion: [
    { path: "gene1", label: "Gene 1", kind: "string", operators: ["eq", "in", "exists", "regex"], value_role: "gene", filter_references: [{ key: "fusionlists", kind: "string_list", path: "sample.filters.somatic.fusion.fusionlists" }] },
    { path: "calls", label: "Calls", kind: "object_list", operators: ["exists", "size"] },
    { path: "calls.caller", label: "Caller", kind: "string", operators: ["eq", "in"], filter_references: [{ key: "fusion_callers", kind: "string_list", path: "sample.filters.somatic.fusion.fusion_callers" }] },
    { path: "calls.spanreads", label: "Spanning reads", kind: "integer", operators: ["eq", "gte", "in"] },
  ] }, operators: { eq: "Equals", gte: "At least", in: "Is one of", exists: "Exists", regex: "Pattern", size: "Length" },
  bson_types: ["string", "int", "array"], max_depth: 8, max_nodes: 100, max_list_values: 100,

}
const initial: QueryCondition = { type: "predicate", field: "gene1", operator: "eq", value: "BRAF" }
function Harness({ start = initial }: { start?: QueryCondition }) {
  const [value, setValue] = useState(start)
  return <><QueryConditionBuilder value={value} onChange={setValue} fields={catalog.fields.fusion} catalog={catalog} /><output data-testid="condition">{JSON.stringify(value)}</output></>
}
const current = () => JSON.parse(screen.getByTestId("condition").textContent ?? "{}")

describe("Query condition builder", () => {
  it("stores a sample filter key without copying genes, while retaining manual entry", () => {
    render(<Harness start={{ type: "predicate", field: "gene1", operator: "in", value: [] }} />)
    fireEvent.change(screen.getByLabelText("Condition value source"), { target: { value: "reference" } })
    expect(current().value).toEqual({ source: "sample.filters", key: "fusionlists" })
    expect(screen.queryByLabelText("Condition values")).not.toBeInTheDocument()
    expect(screen.queryByLabelText("Gene list values")).not.toBeInTheDocument()
    fireEvent.change(screen.getByLabelText("Condition value source"), { target: { value: "manual" } })
    fireEvent.change(screen.getByLabelText("Condition values"), { target: { value: "TP53, BRAF\nTP53" } })
    expect(current().value).toEqual(["TP53", "BRAF"])
  })

  it("uses a caller filter reference without populating literal callers", () => {
    render(<Harness start={{ type: "predicate", field: "calls.caller", operator: "in", value: [] }} />)
    fireEvent.change(screen.getByLabelText("Condition value source"), { target: { value: "reference" } })
    expect(current().value).toEqual({ source: "sample.filters", key: "fusion_callers" })
  })

  it("searches stored fields without silently switching the selected field", () => {
    render(<Harness />)
    fireEvent.change(screen.getByLabelText("Search condition fields"), { target: { value: "spanreads" } })
    expect(within(screen.getByLabelText("Condition field")).getAllByRole("option")).toHaveLength(2)
    expect(current().field).toBe("gene1")
  })
  it("keeps the existing predicate when wrapping it in nested OR and NOT", () => {
    render(<Harness />)
    fireEvent.change(screen.getByLabelText("Condition logic"), { target: { value: "any" } })
    expect(current()).toEqual({ type: "any", children: [initial] })
    fireEvent.click(screen.getByRole("button", { name: "Add condition" }))
    fireEvent.change(screen.getAllByLabelText("Condition logic")[2], { target: { value: "not" } })
    expect(current().children[1].type).toBe("not")
    expect(current().children[0]).toEqual(initial)
  })

  it("limits element conditions to the selected array", () => {
    render(<Harness />)
    fireEvent.change(screen.getByLabelText("Condition logic"), { target: { value: "elem_match" } })
    expect(screen.getByLabelText("Condition array")).toHaveValue("calls")
    const fields = within(screen.getByLabelText("Condition field")).getAllByRole("option")
    expect(fields.map(field => field.getAttribute("value"))).toEqual(["calls.caller", "calls.spanreads"])
    expect(current().condition.field).toBe("calls.caller")
  })

  it("offers numeric operators only on numeric fields and preserves multiline entry", () => {
    render(<Harness />)
    expect(within(screen.getByLabelText("Condition operator")).queryByText("At least ($gte)")).not.toBeInTheDocument()
    fireEvent.change(screen.getByLabelText("Condition field"), { target: { value: "calls.spanreads" } })
    fireEvent.change(screen.getByLabelText("Condition operator"), { target: { value: "in" } })
    fireEvent.change(screen.getByLabelText("Condition values"), { target: { value: "10\n" } })
    expect(screen.getByLabelText("Condition values")).toHaveValue("10\n")
    fireEvent.change(screen.getByLabelText("Condition values"), { target: { value: "10\n20" } })
    expect(current().value).toEqual([10, 20])
  })

  it("shows invalid integer values rather than converting them to zero", () => {
    render(<Harness start={{ type: "predicate", field: "calls.spanreads", operator: "gte", value: 5 }} />)
    fireEvent.change(screen.getByLabelText("Condition value"), { target: { value: "" } })
    expect(current().value).toBe("")
    expect(screen.getByRole("alert")).toHaveTextContent("Enter valid numbers")
  })

  it("duplicates and removes conditions without changing their sibling", () => {
    render(<Harness start={{ type: "all", children: [initial] }} />)
    fireEvent.click(screen.getByRole("button", { name: "Duplicate condition" }))
    fireEvent.change(screen.getAllByLabelText("Condition value")[1], { target: { value: "TP53" } })
    expect(current().children.map((child: { value: string }) => child.value)).toEqual(["BRAF", "TP53"])
    fireEvent.click(screen.getAllByRole("button", { name: "Remove condition" })[0])
    expect(current().children[0].value).toBe("TP53")
  })
})
