// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

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
  { title: "Summary order", fields: [
    { key: "summary_text_order", label: "Summary text order", type: "list", default: [] },
    { key: "summary_table_order", label: "Summary table order", type: "list", default: [] },
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
    summary_text_order: [], summary_table_order: [],
  } })
})

it("edits and saves independent text and table priorities in ASPC reporting", () => {
  const saved = vi.fn()
  function Editor() {
    const [values, setValues] = useState(() => formStateFromSpec(form, {}))
    return <AdminManagedForm mode="create" spec={specs.aspc} form={form} values={values} setValues={setValues} isSaving={false} error="" onCancel={() => {}} onSave={() => saved(submitPayload(form, values, "create"))} />
  }
  render(<Editor />)
  fireEvent.change(screen.getByLabelText("Summary text order"), { target: { value: "CNV\nTRANSLOCATION\nSNV" } })
  fireEvent.change(screen.getByLabelText("Summary table order"), { target: { value: "SNV\nCNV" } })
  fireEvent.click(screen.getAllByRole("button", { name: "Save" })[0])
  expect(saved).toHaveBeenLastCalledWith(expect.objectContaining({ reporting: expect.objectContaining({
    summary_text_order: ["CNV", "TRANSLOCATION", "SNV"], summary_table_order: ["SNV", "CNV"],
  }) }))
  fireEvent.change(screen.getByLabelText("Summary text order"), { target: { value: "" } })
  fireEvent.click(screen.getAllByRole("button", { name: "Save" })[0])
  expect(saved).toHaveBeenLastCalledWith(expect.objectContaining({ reporting: expect.objectContaining({
    summary_text_order: [], summary_table_order: ["SNV", "CNV"],
  }) }))
})

it("preserves explicit reporting values and does not mutate the source or form defaults", () => {
  const source = { reporting: { report_header: "Reviewed header", report_sections: [], report_method: "", language: null } }
  const state = formStateFromSpec(form, source)
  expect(state.reporting).toMatchObject(source.reporting)
  state.reporting.report_sections.push("SNV")
  expect(source.reporting.report_sections).toEqual([])
  expect(form.fields.reporting.groups![0].fields.find(field => field.key === "report_sections")?.default).toEqual(["SNV"])
})
