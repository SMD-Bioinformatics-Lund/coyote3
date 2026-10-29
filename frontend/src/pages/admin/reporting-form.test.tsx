import { useState } from "react"
import { fireEvent, render, screen } from "@testing-library/react"
import { expect, it, vi } from "vitest"
import { AdminManagedForm } from "./AdminManagedForm"
import { formStateFromSpec, submitPayload } from "./resource-list"
import { specs, type FormSpec } from "./resource-specs"

const form: FormSpec = { fields: { reporting: { display_type: "reporting-structured", groups: [
  { title: "Report text", fields: [
    { key: "report_header", label: "Report header", type: "text", default: "Synthetic DNA report" },
    { key: "report_method", label: "Report method", type: "text", default: "Synthetic method" },
    { key: "plots_path", label: "Plots path", type: "text", default: "/tmp" },
    { key: "report_folder", label: "Report folder", type: "text", default: "reports" },
    { key: "report_sections", label: "Report sections", type: "checkbox-group", options: ["SNV"], default: ["SNV"] },
  ] },
] } } }

it("saves visible reporting defaults when only the method is edited, using either save button", () => {
  const saved = vi.fn()
  function Editor() {
    const [values, setValues] = useState(() => formStateFromSpec(form, {}))
    return <AdminManagedForm mode="create" spec={specs.aspc} form={form} values={values} setValues={setValues} isSaving={false} error="" onCancel={() => {}} onSave={() => saved(submitPayload(form, values, "create"))} />
  }
  render(<Editor />)
  fireEvent.change(screen.getByLabelText("Report method"), { target: { value: "Reviewed method" } })
  const buttons = screen.getAllByRole("button", { name: "Save" })
  expect(buttons).toHaveLength(2)
  for (const button of buttons) fireEvent.click(button)
  expect(saved).toHaveBeenCalledTimes(2)
  expect(saved).toHaveBeenLastCalledWith({ reporting: {
    report_header: "Synthetic DNA report", report_method: "Reviewed method",
    plots_path: "/tmp", report_folder: "reports", report_sections: ["SNV"],
  } })
})

it("preserves explicit reporting values and does not mutate the source or form defaults", () => {
  const source = { reporting: { report_header: "Reviewed header", report_sections: [], report_method: "", language: null } }
  const state = formStateFromSpec(form, source)
  expect(state.reporting).toMatchObject(source.reporting)
  state.reporting.report_sections.push("SNV")
  expect(source.reporting.report_sections).toEqual([])
  expect(form.fields.reporting.groups![0].fields.find(field => field.key === "report_sections")?.default).toEqual(["SNV"])
})
