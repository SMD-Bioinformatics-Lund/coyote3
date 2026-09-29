import { useState } from "react"
import { render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it } from "vitest"
import { AdminManagedForm } from "./resource-form"
import { specs, type FormSpec } from "./resource-specs"

function ScopedForm({ multiple = false }: { multiple?: boolean }) {
  const [values, setValues] = useState<Record<string, unknown>>(multiple
    ? { asp_groups: ["group-a"], asp_ids: ["assay-a"], diagnosis: ["panel-a"] }
    : { asp_id: "assay-a", subpanel_id: "panel-a" })
  const field = { label: "Subpanel", display_type: multiple ? "checkbox-group" : "select", default: "base",
    options: ["unrelated"], options_by_field: { field: multiple ? "asp_ids" : "asp_id", values: {
      "assay-a": ["base", "panel-a"], "assay-b": ["base", "panel-b"],
    } } }
  const form = { fields: multiple ? {
    diagnosis: field,
    asp_ids: { label: "Assays", display_type: "checkbox-group", options_by_field: {
      field: "asp_groups", values: { "group-a": ["assay-a"], "group-b": ["assay-b"] },
    } },
    asp_groups: { label: "Groups", display_type: "checkbox-group", options: ["group-a", "group-b"] },
  } : {
    asp_id: { label: "Assay", display_type: "select", options: ["assay-a", "assay-b"] },
    subpanel_id: field,
  } } as FormSpec
  return <><AdminManagedForm mode="create" spec={multiple ? specs.genelists : specs.aspc} form={form}
    values={values} setValues={setValues} onSave={() => {}} onCancel={() => {}} isSaving={false} error="" />
    <output>{JSON.stringify(values)}</output></>
}

describe("assay-associated subpanel choices", () => {
  it("shows only the chosen assay's subpanels and resets to Base when changing assays", async () => {
    render(<ScopedForm />)
    const user = userEvent.setup()
    const subpanel = screen.getByRole("combobox", { name: "Subpanel" })
    expect(within(subpanel).queryByRole("option", { name: "panel-b" })).toBeNull()
    expect(within(subpanel).queryByRole("option", { name: "unrelated" })).toBeNull()
    await user.selectOptions(screen.getByRole("combobox", { name: "Assay" }), "assay-b")
    expect(subpanel).toHaveValue("base")
    expect(within(subpanel).queryByRole("option", { name: "panel-a" })).toBeNull()
    expect(within(subpanel).getByRole("option", { name: "panel-b" })).toBeInTheDocument()
  })

  it("clears gene-list diagnoses when a group change removes their associated assay", async () => {
    render(<ScopedForm multiple />)
    await userEvent.setup().click(screen.getByRole("checkbox", { name: /Groups group-a/ }))
    expect(screen.getByRole("status")).toHaveTextContent('"asp_ids":[]')
    expect(screen.getByRole("status")).toHaveTextContent('"diagnosis":[]')
    expect(screen.queryByRole("checkbox", { name: "panel-a" })).toBeNull()
  })
})

function FilterForm() {
  const [values, setValues] = useState<Record<string, unknown>>({ asp_id: "a", filters: {
    somatic: { snv: { snvlists: ["shared", "a-only"], min_depth: 100 }, cnv: { cnvlists: ["a-only"] } },
  } })
  const form: FormSpec = { fields: {
    asp_id: { label: "Assay", display_type: "select", options: ["a", "b"] },
    filters: { label: "Filters", display_type: "filters-structured", groups: [{ title: "Lists", fields: [
      { key: "somatic.snv.snvlists", label: "SNV lists", type: "checkbox-group", options_by_field: { field: "asp_id", values: { a: ["shared", "a-only"], b: ["shared", "b-only"] } } },
      { key: "somatic.cnv.cnvlists", label: "CNV lists", type: "checkbox-group", options_by_field: { field: "asp_id", values: { a: ["a-only"], b: ["b-only"] } } },
    ] }] },
  } }
  return <><AdminManagedForm mode="create" spec={specs.aspc} form={form} values={values} setValues={setValues} onSave={() => {}} onCancel={() => {}} isSaving={false} error="" /><output>{JSON.stringify(values)}</output></>
}

it("preserves allowed nested gene lists and clears incompatible arrays on assay change", async () => {
  render(<FilterForm />)
  await userEvent.setup().selectOptions(screen.getByRole("combobox", { name: "Assay" }), "b")
  const values = JSON.parse(screen.getByRole("status").textContent || "{}")
  expect(values.filters).toEqual({ somatic: { snv: { snvlists: ["shared"], min_depth: 100 }, cnv: { cnvlists: [] } } })
})
