import { render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { useState } from "react"
import { describe, expect, it } from "vitest"
import { AdminManagedForm } from "./AdminManagedForm"
import { specs, type FormSpec } from "./resource-specs"

function AssayCapabilityForm() {
  const [values, setValues] = useState<Record<string, unknown>>({ asp_category: "dna", asp_family: "panel-dna", expected_files: ["vcf_files"], required_files: ["vcf_files"], supported_analyses: ["SNV"] })
  const form: FormSpec = { fields: {
    asp_category: { label: "Modality", display_type: "select", readonly: true, options: ["dna", "rna"], options_by_field: { field: "asp_family", values: { "panel-dna": ["dna"], "panel-rna": ["rna"] } } },
    asp_family: { label: "Family", display_type: "select", options: ["panel-dna", "panel-rna"] },
    expected_files: { label: "Expected files", display_type: "checkbox-group", options_by_field: { field: "asp_category", values: { dna: ["vcf_files"], rna: ["fusion_files"] } } },
    required_files: { label: "Required files", display_type: "checkbox-group", options_from_field: "expected_files" },
    supported_analyses: { label: "Analyses", display_type: "checkbox-group", options_by_field: { field: "asp_family", values: { "panel-dna": ["SNV"], "panel-rna": ["FUSION"] } }, options_require_inputs: { field: "expected_files", values: { SNV: ["vcf_files"], FUSION: ["fusion_files"] } } },
  } }
  return <><AdminManagedForm mode="create" spec={specs.asp} form={form} values={values} setValues={setValues} onSave={() => {}} onCancel={() => {}} isSaving={false} error="" /><output data-testid="values">{JSON.stringify(values)}</output></>
}

it("switches assay modality without retaining incompatible files or analyses", async () => {
  render(<AssayCapabilityForm />)
  const user = userEvent.setup()
  await user.selectOptions(screen.getByRole("combobox", { name: "Family" }), "panel-rna")
  expect(screen.getByRole("combobox", { name: "Modality" })).toHaveValue("rna")
  expect(screen.getByRole("combobox", { name: "Modality" })).toBeDisabled()
  expect(screen.getByRole("combobox", { name: "Family" })).toHaveValue("panel-rna")
  expect(screen.queryByRole("checkbox", { name: /vcf_files/ })).toBeNull()
  expect(screen.getByTestId("values")).toHaveTextContent('"required_files":[]')
  expect(screen.getByTestId("values")).toHaveTextContent('"supported_analyses":[]')
  await user.click(screen.getByRole("checkbox", { name: /Expected files fusion_files/ }))
  expect(screen.getByRole("checkbox", { name: /Required files fusion_files/ })).toBeVisible()
  expect(screen.getByRole("checkbox", { name: /Analyses FUSION/ })).toBeVisible()
})

function ScopedForm({ multiple = false }: { multiple?: boolean }) {
  const [values, setValues] = useState<Record<string, unknown>>(multiple
    ? { asp_groups: ["group-a"], asp_ids: ["assay-a"], diagnosis: ["panel-a"] }
    : { asp_id: "assay-a", diagnosis_id: "panel-a" })
  const field = { label: "Diagnosis", display_type: multiple ? "checkbox-group" : "select", default: "base",
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
    diagnosis_id: field,
  } } as FormSpec
  return <><AdminManagedForm mode="create" spec={multiple ? specs.genelists : specs.aspc} form={form}
    values={values} setValues={setValues} onSave={() => {}} onCancel={() => {}} isSaving={false} error="" />
    <output>{JSON.stringify(values)}</output></>
}

describe("assay-associated diagnosis choices", () => {
  it("shows only the chosen assay's diagnoses and resets to Base when changing assays", async () => {
    render(<ScopedForm />)
    const user = userEvent.setup()
    const diagnosis = screen.getByRole("combobox", { name: "Diagnosis" })
    expect(within(diagnosis).queryByRole("option", { name: "panel-b" })).toBeNull()
    expect(within(diagnosis).queryByRole("option", { name: "unrelated" })).toBeNull()
    await user.selectOptions(screen.getByRole("combobox", { name: "Assay" }), "assay-b")
    expect(diagnosis).toHaveValue("base")
    expect(within(diagnosis).queryByRole("option", { name: "panel-a" })).toBeNull()
    expect(within(diagnosis).getByRole("option", { name: "panel-b" })).toBeInTheDocument()
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
