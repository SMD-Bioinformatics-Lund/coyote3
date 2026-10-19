import { useState } from "react"
import { fireEvent, render, screen, within } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { CatalogAnalysisLists } from "./CatalogAnalysisLists"
import type { Category, SourceOptions } from "./catalog-types"

const sources: SourceOptions = {
  asps: [{ asp_id: "panel", label: "Panel", group: "solid" }], aspcs: [],
  gene_lists: [
    { isgl_id: "a", label: "List A", asp_ids: ["panel"], asp_groups: ["solid"], diagnosis: [], list_type: ["snv", "cnv"] },
    { isgl_id: "b", label: "List B", asp_ids: ["panel"], asp_groups: [], diagnosis: [], list_type: ["snv"] },
    { isgl_id: "other", label: "Other assay", asp_ids: ["other"], diagnosis: [] },
    { isgl_id: "wrong", label: "Other group", asp_ids: ["panel"], asp_groups: ["myeloid"], diagnosis: [] },
  ],
}
function Editor() {
  const [entry, setEntry] = useState<Category>({ asp_id: "panel", analysis: ["SNV", "CNV"] })
  return <><CatalogAnalysisLists entry={entry} sources={sources} onChange={setEntry} /><output data-testid="value">{JSON.stringify(entry)}</output></>
}
describe("Analysis gene-list assignments", () => {
  it("supports a general gene list when no analyses are defined", () => {
    function GeneralEditor() {
      const [entry, setEntry] = useState<Category>({ asp_id: "panel" })
      return <><CatalogAnalysisLists entry={entry} sources={sources} onChange={setEntry} /><output data-testid="general-value">{JSON.stringify(entry)}</output></>
    }
    render(<GeneralEditor />)
    fireEvent.click(within(screen.getByRole("group", { name: "General gene lists" })).getByRole("checkbox", { name: "List A" }))
    expect(screen.getByTestId("general-value")).toHaveTextContent('"analysis":[]')
    expect(screen.getByTestId("general-value")).toHaveTextContent('"isgl_id":"a"')
  })
  it("filters by assay and group and supports multiple lists independently per analysis", () => {
    render(<Editor />)
    expect(screen.queryByText("Other assay")).not.toBeInTheDocument()
    expect(screen.queryByText("Other group")).not.toBeInTheDocument()
    const snv = within(screen.getByRole("group", { name: "SNV" }))
    fireEvent.click(snv.getByRole("checkbox", { name: /List A/ }))
    fireEvent.click(snv.getByRole("checkbox", { name: /List B/ }))
    expect(snv.getByText("2 selected")).toBeVisible()
    const cnv = within(screen.getByRole("group", { name: "CNV" }))
    fireEvent.click(cnv.getByRole("checkbox", { name: /List A/ }))
    fireEvent.click(snv.getByRole("checkbox", { name: "No gene list for SNV" }))
    const entry = JSON.parse(screen.getByTestId("value").textContent!) as Category
    expect(entry.no_gene_list).toEqual(["SNV"])
    expect(entry.gene_lists).toHaveLength(1)
    expect(entry.gene_lists?.[0].analysis).toEqual(["CNV"])
    expect(cnv.getByRole("checkbox", { name: /List A/ })).toBeChecked()
  })
  it("searches without discarding selected assignments", () => {
    render(<Editor />)
    fireEvent.click(within(screen.getByRole("group", { name: "SNV" })).getByRole("checkbox", { name: /List A/ }))
    fireEvent.change(screen.getByRole("textbox", { name: "Search eligible gene lists" }), { target: { value: "List B" } })
    expect(screen.queryByText("List A")).not.toBeInTheDocument()
    expect(screen.getByTestId("value")).toHaveTextContent('"isgl_id":"a"')
  })
})
